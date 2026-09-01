from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
import yaml
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from dashboard_studio.api import routes_dashboard
from dashboard_studio.api.deps import (
    get_dashboard_generation_client,
    get_db_session,
    get_registry_cache,
)
from dashboard_studio.dashboard.config import CardConfig, GridSection, NativeCardType
from dashboard_studio.dashboard.generation_client import (
    DashboardGenerationAuthError,
    DashboardGenerationNotConfiguredError,
    DashboardGenerationRateLimitError,
    DashboardGenerationUpstreamError,
)
from dashboard_studio.dashboard.orchestrator import (
    DashboardGenerationOutcome,
    GenerationUsageTotals,
)
from dashboard_studio.dashboard.validation import ValidationReport
from dashboard_studio.db.models import Base, TokenPreset
from dashboard_studio.ha.ws_client import HAWebSocketError
from dashboard_studio.registry.snapshot import EntityRecord, RegistrySnapshot


def make_entity(**overrides: Any) -> EntityRecord:
    defaults: dict[str, Any] = {
        "entity_id": "light.test",
        "domain": "light",
        "name": "Test Light",
        "available": True,
    }
    defaults.update(overrides)
    return EntityRecord(**defaults)


def make_snapshot() -> RegistrySnapshot:
    return RegistrySnapshot(
        fetched_at=datetime.now(UTC),
        entities=[
            make_entity(entity_id="light.living_a", area_id="living_room", area_name="Living Room"),
            make_entity(entity_id="light.living_b", area_id="living_room", area_name="Living Room"),
            make_entity(
                entity_id="switch.kitchen_a",
                domain="switch",
                area_id="kitchen",
                area_name="Kitchen",
            ),
        ],
        areas=[],
        floors=[],
        labels=[],
        lovelace_resources=[],
    )


@dataclass
class FakeRegistryCache:
    snapshot: RegistrySnapshot | None = None
    error: Exception | None = None

    async def get(self, force_refresh: bool = False) -> RegistrySnapshot:
        if self.error is not None:
            raise self.error
        assert self.snapshot is not None
        return self.snapshot


@dataclass
class FakeDashboardGenerationClient:
    """Route-level fake -- the orchestrator and generation client themselves
    are covered by test_dashboard_orchestrator.py / test_dashboard_generation_client.py.
    """

    outcome: DashboardGenerationOutcome | None = None
    error: Exception | None = None


def make_outcome() -> DashboardGenerationOutcome:
    from dashboard_studio.dashboard.config import GeneratedDashboard, SectionsView

    dashboard = GeneratedDashboard(
        views=[
            SectionsView(
                title="Living Room",
                sections=[
                    GridSection(
                        cards=[CardConfig(card_type=NativeCardType.tile, entity="light.living_a")]
                    )
                ],
            )
        ]
    )
    return DashboardGenerationOutcome(
        dashboard=dashboard,
        validation=ValidationReport(),
        usage=GenerationUsageTotals(
            input_tokens=500, output_tokens=200, estimated_cost_usd=0.01, model="claude-sonnet-5", call_count=2
        ),
        notes=[],
    )


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


async def _fake_generate_dashboard(*, client: Any, **_kwargs: Any) -> DashboardGenerationOutcome:
    if client.error is not None:
        raise client.error
    assert client.outcome is not None
    return client.outcome


def make_app(
    session: AsyncSession,
    registry_cache: FakeRegistryCache,
    generation_client: FakeDashboardGenerationClient,
    monkeypatch: pytest.MonkeyPatch,
) -> FastAPI:
    monkeypatch.setattr(routes_dashboard, "generate_dashboard", _fake_generate_dashboard)
    app = FastAPI()
    app.include_router(routes_dashboard.router)
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_registry_cache] = lambda: registry_cache
    app.dependency_overrides[get_dashboard_generation_client] = lambda: generation_client
    return app


@pytest.fixture
def anon_client_factory(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    def factory(
        registry_cache: FakeRegistryCache | None = None,
        generation_client: FakeDashboardGenerationClient | None = None,
    ) -> AsyncClient:
        app = make_app(
            db_session,
            registry_cache or FakeRegistryCache(snapshot=make_snapshot()),
            generation_client or FakeDashboardGenerationClient(outcome=make_outcome()),
            monkeypatch,
        )
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    return factory


async def test_generate_rejects_empty_scope_selection(anon_client_factory) -> None:
    async with anon_client_factory() as client:
        response = await client.post("/api/dashboard/generate", json={"strategy": "by_area"})
    assert response.status_code == 400


async def test_generate_rejects_both_preset_and_tokens(anon_client_factory) -> None:
    async with anon_client_factory() as client:
        response = await client.post(
            "/api/dashboard/generate",
            json={
                "area_ids": ["living_room"],
                "strategy": "by_area",
                "token_preset_id": "some-id",
                "tokens": {
                    "colors": {
                        "primary": {"light": "#000", "dark": "#fff"},
                        "accent": {"light": "#000", "dark": "#fff"},
                        "background": {"light": "#000", "dark": "#fff"},
                        "surface": {"light": "#000", "dark": "#fff"},
                        "on_surface": {"light": "#000", "dark": "#fff"},
                        "state_on": {"light": "#000", "dark": "#fff"},
                        "state_off": {"light": "#000", "dark": "#fff"},
                        "warn": {"light": "#000", "dark": "#fff"},
                        "critical": {"light": "#000", "dark": "#fff"},
                    },
                    "typography": {
                        "font_family": "Inter",
                        "sizes": {"xs": "12px", "sm": "14px", "md": "16px", "lg": "20px", "xl": "24px"},
                        "weights": {"regular": 400, "medium": 500, "bold": 700},
                    },
                    "form": {
                        "border_radius_px": 8,
                        "shadow": "none",
                        "border_width_px": 1,
                        "style_family": "flat",
                    },
                    "density": {"mode": "comfortable", "grid_gap_px": 8, "section_spacing_px": 16},
                    "card_style": {"primary_style": "Tile-based", "reasoning": "test"},
                },
            },
        )
    assert response.status_code == 400


async def test_generate_unknown_preset_returns_404(anon_client_factory) -> None:
    async with anon_client_factory() as client:
        response = await client.post(
            "/api/dashboard/generate",
            json={"area_ids": ["living_room"], "strategy": "by_area", "token_preset_id": "does-not-exist"},
        )
    assert response.status_code == 404


async def test_generate_ha_error_returns_503(anon_client_factory) -> None:
    registry_cache = FakeRegistryCache(error=HAWebSocketError("not connected"))
    async with anon_client_factory(registry_cache=registry_cache) as client:
        response = await client.post(
            "/api/dashboard/generate", json={"area_ids": ["living_room"], "strategy": "by_area"}
        )
    assert response.status_code == 503


async def test_generate_empty_resolved_scope_returns_400(anon_client_factory) -> None:
    registry_cache = FakeRegistryCache(snapshot=make_snapshot())
    async with anon_client_factory(registry_cache=registry_cache) as client:
        response = await client.post(
            "/api/dashboard/generate", json={"area_ids": ["nonexistent_area"], "strategy": "by_area"}
        )
    assert response.status_code == 400


async def test_generate_happy_path_yaml_round_trips_and_only_uses_known_entities(anon_client_factory) -> None:
    async with anon_client_factory() as client:
        response = await client.post(
            "/api/dashboard/generate", json={"area_ids": ["living_room"], "strategy": "by_area"}
        )
    assert response.status_code == 200
    body = response.json()

    parsed = yaml.safe_load(body["yaml"])
    assert set(parsed.keys()) == {"views"}

    known_ids = {e["entity_id"] for e in make_snapshot().model_dump()["entities"]}
    for view in parsed["views"]:
        for section in view["sections"]:
            for card in section["cards"]:
                if "entity" in card:
                    assert card["entity"] in known_ids
                for entity_id in card.get("entities", []):
                    assert entity_id in known_ids

    assert body["usage"]["model"] == "claude-sonnet-5"
    assert body["usage"]["call_count"] == 2


async def test_generate_with_valid_preset(anon_client_factory, db_session: AsyncSession) -> None:
    preset = TokenPreset(
        name="My Preset",
        token_json='{"schema_version":1,"colors":{"primary":{"light":"#000","dark":"#fff"},'
        '"accent":{"light":"#000","dark":"#fff"},"background":{"light":"#000","dark":"#fff"},'
        '"surface":{"light":"#000","dark":"#fff"},"on_surface":{"light":"#000","dark":"#fff"},'
        '"state_on":{"light":"#000","dark":"#fff"},"state_off":{"light":"#000","dark":"#fff"},'
        '"warn":{"light":"#000","dark":"#fff"},"critical":{"light":"#000","dark":"#fff"}},'
        '"typography":{"font_family":"Inter","sizes":{"xs":"12px","sm":"14px","md":"16px",'
        '"lg":"20px","xl":"24px"},"weights":{"regular":400,"medium":500,"bold":700}},'
        '"form":{"border_radius_px":8,"shadow":"none","border_width_px":1,"style_family":"flat"},'
        '"density":{"mode":"comfortable","grid_gap_px":8,"section_spacing_px":16},'
        '"card_style":{"primary_style":"Tile-based","reasoning":"test"}}',
        token_schema_version=1,
    )
    db_session.add(preset)
    await db_session.commit()
    await db_session.refresh(preset)

    async with anon_client_factory() as client:
        response = await client.post(
            "/api/dashboard/generate",
            json={"area_ids": ["living_room"], "strategy": "by_area", "token_preset_id": preset.id},
        )
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (DashboardGenerationNotConfiguredError("no key"), 424),
        (DashboardGenerationAuthError("bad key"), 502),
        (DashboardGenerationUpstreamError("upstream down"), 502),
    ],
)
async def test_generate_error_mapping(anon_client_factory, error: Exception, expected_status: int) -> None:
    generation_client = FakeDashboardGenerationClient(error=error)
    async with anon_client_factory(generation_client=generation_client) as client:
        response = await client.post(
            "/api/dashboard/generate", json={"area_ids": ["living_room"], "strategy": "by_area"}
        )
    assert response.status_code == expected_status


async def test_generate_rate_limit_error_sets_retry_after_header(anon_client_factory) -> None:
    generation_client = FakeDashboardGenerationClient(
        error=DashboardGenerationRateLimitError("rate limited", retry_after=30)
    )
    async with anon_client_factory(generation_client=generation_client) as client:
        response = await client.post(
            "/api/dashboard/generate", json={"area_ids": ["living_room"], "strategy": "by_area"}
        )
    assert response.status_code == 429
    assert response.headers["retry-after"] == "30"
