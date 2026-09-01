from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from dashboard_studio.api import routes_design
from dashboard_studio.api.deps import get_anthropic_client, get_db_session, get_upload_store
from dashboard_studio.db.models import Base
from dashboard_studio.design.anthropic_client import (
    DesignAnalysisAuthError,
    DesignAnalysisNotConfiguredError,
    DesignAnalysisRateLimitError,
    DesignAnalysisResult,
    DesignAnalysisUpstreamError,
)
from dashboard_studio.design.tokens import (
    CardStyleClassification,
    ColorPair,
    ColorPalette,
    Density,
    DensityMode,
    DesignTokenSet,
    FontSizeScale,
    FontWeights,
    Form,
    StyleFamily,
    Typography,
)
from dashboard_studio.design.uploads import DesignUploadStore


def make_token_set() -> DesignTokenSet:
    pair = ColorPair(light="#111111", dark="#eeeeee")
    return DesignTokenSet(
        colors=ColorPalette(
            primary=pair,
            accent=pair,
            background=pair,
            surface=pair,
            on_surface=pair,
            state_on=pair,
            state_off=pair,
            warn=pair,
            critical=pair,
        ),
        typography=Typography(
            font_family="Inter",
            sizes=FontSizeScale(xs="12px", sm="14px", md="16px", lg="20px", xl="24px"),
            weights=FontWeights(regular=400, medium=500, bold=700),
        ),
        form=Form(border_radius_px=8, shadow="none", border_width_px=1, style_family=StyleFamily.flat),
        density=Density(mode=DensityMode.comfortable, grid_gap_px=8, section_spacing_px=16),
        card_style=CardStyleClassification(primary_style="Tile-based", reasoning="test"),
    )


@dataclass
class FakeAnthropicClient:
    """Fakes the AnthropicDesignClient dependency, not the SDK -- this is a
    route-level test, the Anthropic SDK interaction itself is covered by
    test_anthropic_client.py.
    """

    result: DesignAnalysisResult | None = None
    error: Exception | None = None

    async def analyze_design(self, image_bytes: bytes, media_type: str) -> DesignAnalysisResult:
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


def make_app(
    session: AsyncSession, anthropic_client: FakeAnthropicClient, upload_store: DesignUploadStore
) -> FastAPI:
    app = FastAPI()
    app.include_router(routes_design.router)
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_anthropic_client] = lambda: anthropic_client
    app.dependency_overrides[get_upload_store] = lambda: upload_store
    return app


@pytest.fixture
def anon_client_factory(tmp_path: Path, db_session: AsyncSession):
    def factory(anthropic_client: FakeAnthropicClient | None = None) -> AsyncClient:
        upload_store = DesignUploadStore(tmp_path)
        app = make_app(db_session, anthropic_client or FakeAnthropicClient(), upload_store)
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    return factory


async def test_upload_then_analyze_happy_path(anon_client_factory) -> None:
    token_set = make_token_set()
    fake_client = FakeAnthropicClient(
        result=DesignAnalysisResult(
            tokens=token_set,
            input_tokens=1000,
            output_tokens=200,
            estimated_cost_usd=0.01,
            model="claude-sonnet-5",
        )
    )

    async with anon_client_factory(fake_client) as client:
        upload_response = await client.post(
            "/api/design/upload",
            files={"file": ("test.png", b"fake-png-bytes", "image/png")},
        )
        assert upload_response.status_code == 200
        upload_id = upload_response.json()["upload_id"]

        analyze_response = await client.post(
            "/api/design/analyze", json={"upload_id": upload_id}
        )

    assert analyze_response.status_code == 200
    body = analyze_response.json()
    assert body["tokens"]["card_style"]["primary_style"] == "Tile-based"
    assert body["usage"] == {
        "input_tokens": 1000,
        "output_tokens": 200,
        "estimated_cost_usd": 0.01,
        "model": "claude-sonnet-5",
    }


async def test_upload_rejects_disallowed_mime_type(anon_client_factory) -> None:
    async with anon_client_factory() as client:
        response = await client.post(
            "/api/design/upload",
            files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
        )
    assert response.status_code == 400


async def test_analyze_unknown_upload_id_returns_404(anon_client_factory) -> None:
    async with anon_client_factory() as client:
        response = await client.post(
            "/api/design/analyze",
            json={"upload_id": "00000000-0000-0000-0000-000000000000"},
        )
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (DesignAnalysisNotConfiguredError("no key"), 424),
        (DesignAnalysisAuthError("bad key"), 502),
        (DesignAnalysisUpstreamError("upstream down"), 502),
    ],
)
async def test_analyze_error_mapping(anon_client_factory, error: Exception, expected_status: int) -> None:
    fake_client = FakeAnthropicClient(error=error)

    async with anon_client_factory(fake_client) as client:
        upload_response = await client.post(
            "/api/design/upload",
            files={"file": ("test.png", b"fake-png-bytes", "image/png")},
        )
        upload_id = upload_response.json()["upload_id"]

        response = await client.post("/api/design/analyze", json={"upload_id": upload_id})

    assert response.status_code == expected_status


async def test_analyze_rate_limit_error_sets_retry_after_header(anon_client_factory) -> None:
    fake_client = FakeAnthropicClient(
        error=DesignAnalysisRateLimitError("rate limited", retry_after=30)
    )

    async with anon_client_factory(fake_client) as client:
        upload_response = await client.post(
            "/api/design/upload",
            files={"file": ("test.png", b"fake-png-bytes", "image/png")},
        )
        upload_id = upload_response.json()["upload_id"]

        response = await client.post("/api/design/analyze", json={"upload_id": upload_id})

    assert response.status_code == 429
    assert response.headers["retry-after"] == "30"


async def test_preset_crud_lifecycle(anon_client_factory) -> None:
    token_set = make_token_set()

    async with anon_client_factory() as client:
        empty = await client.get("/api/design/presets")
        assert empty.status_code == 200
        assert empty.json() == []

        created = await client.post(
            "/api/design/presets",
            json={"name": "My Preset", "tokens": token_set.model_dump(mode="json")},
        )
        assert created.status_code == 200
        preset_id = created.json()["id"]

        listed = await client.get("/api/design/presets")
        assert [p["id"] for p in listed.json()] == [preset_id]

        fetched = await client.get(f"/api/design/presets/{preset_id}")
        assert fetched.status_code == 200
        assert fetched.json()["tokens"]["card_style"]["primary_style"] == "Tile-based"

        deleted = await client.delete(f"/api/design/presets/{preset_id}")
        assert deleted.status_code == 200
        assert deleted.json() == {"deleted": True}

        after_delete = await client.get("/api/design/presets")
        assert after_delete.json() == []


async def test_create_preset_rejects_blank_name(anon_client_factory) -> None:
    token_set = make_token_set()

    async with anon_client_factory() as client:
        response = await client.post(
            "/api/design/presets",
            json={"name": "   ", "tokens": token_set.model_dump(mode="json")},
        )

    assert response.status_code == 400


async def test_get_and_delete_unknown_preset_return_404(anon_client_factory) -> None:
    async with anon_client_factory() as client:
        get_response = await client.get("/api/design/presets/does-not-exist")
        delete_response = await client.delete("/api/design/presets/does-not-exist")

    assert get_response.status_code == 404
    assert delete_response.status_code == 404


async def test_theme_export_returns_yaml_with_modes(anon_client_factory) -> None:
    token_set = make_token_set()

    async with anon_client_factory() as client:
        response = await client.post(
            "/api/design/theme-export",
            json={"theme_name": "My Theme", "tokens": token_set.model_dump(mode="json")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "my_theme.yaml"
    assert "modes:" in body["yaml"]
    assert "primary-color:" in body["yaml"]


async def test_theme_export_rejects_invalid_name(anon_client_factory) -> None:
    token_set = make_token_set()

    async with anon_client_factory() as client:
        response = await client.post(
            "/api/design/theme-export",
            json={"theme_name": "not/a valid name!", "tokens": token_set.model_dump(mode="json")},
        )

    assert response.status_code == 400
