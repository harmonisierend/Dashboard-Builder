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
from dashboard_studio.dashboard.generation_client import (
    DashboardGenerationAuthError,
    DashboardGenerationNotConfiguredError,
    DashboardGenerationRateLimitError,
    DashboardGenerationUpstreamError,
)
from dashboard_studio.dashboard.orchestrator import (
    DashboardGenerationOutcome,
    GenerationUsageTotals,
    ProposedView,
    StructureProposalOutcome,
)
from dashboard_studio.dashboard.scope import CandidateEntitySummary
from dashboard_studio.dashboard.validation import ValidationReport
from dashboard_studio.db.models import Base
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


def make_candidate(entity_id: str, area_name: str | None = "Living Room") -> CandidateEntitySummary:
    return CandidateEntitySummary(
        entity_id=entity_id,
        domain=entity_id.split(".")[0],
        name=entity_id,
        area_name=area_name,
        device_class=None,
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

    propose_outcome: StructureProposalOutcome | None = None
    generate_outcome: DashboardGenerationOutcome | None = None
    error: Exception | None = None


def make_usage(call_count: int = 1) -> GenerationUsageTotals:
    return GenerationUsageTotals(
        input_tokens=300, output_tokens=100, estimated_cost_usd=0.01, model="claude-sonnet-5",
        call_count=call_count,
    )


def make_propose_outcome() -> StructureProposalOutcome:
    return StructureProposalOutcome(
        proposed_views=[
            ProposedView(
                name="Living Room",
                candidates=[make_candidate("light.living_a"), make_candidate("light.living_b")],
            )
        ],
        available_custom_cards={},
        style_hint=None,
        usage=make_usage(call_count=1),
        notes=[],
    )


def make_generate_outcome() -> DashboardGenerationOutcome:
    from dashboard_studio.dashboard.config import (
        CardConfig,
        GeneratedDashboard,
        GridSection,
        NativeCardType,
        SectionsView,
    )

    dashboard = GeneratedDashboard(
        views=[
            SectionsView(
                title="Living Room",
                sections=[
                    GridSection(cards=[CardConfig(card_type=NativeCardType.tile, entity="light.living_a")])
                ],
            )
        ]
    )
    return DashboardGenerationOutcome(
        dashboard=dashboard,
        validation=ValidationReport(),
        usage=GenerationUsageTotals(
            input_tokens=200, output_tokens=80, estimated_cost_usd=0.005, model="claude-sonnet-5", call_count=1
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


async def _fake_propose_structure(*, client: Any, **_kwargs: Any) -> StructureProposalOutcome:
    if client.error is not None:
        raise client.error
    assert client.propose_outcome is not None
    return client.propose_outcome


async def _fake_generate_from_curated_views(*, client: Any, **_kwargs: Any) -> DashboardGenerationOutcome:
    if client.error is not None:
        raise client.error
    assert client.generate_outcome is not None
    return client.generate_outcome


def make_app(
    session: AsyncSession,
    registry_cache: FakeRegistryCache,
    generation_client: FakeDashboardGenerationClient,
    monkeypatch: pytest.MonkeyPatch,
) -> FastAPI:
    monkeypatch.setattr(routes_dashboard, "propose_structure", _fake_propose_structure)
    monkeypatch.setattr(routes_dashboard, "generate_from_curated_views", _fake_generate_from_curated_views)
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
            generation_client
            or FakeDashboardGenerationClient(
                propose_outcome=make_propose_outcome(), generate_outcome=make_generate_outcome()
            ),
            monkeypatch,
        )
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    return factory


def usage_payload(call_count: int = 1) -> dict[str, Any]:
    return {
        "input_tokens": 300,
        "output_tokens": 100,
        "estimated_cost_usd": 0.01,
        "model": "claude-sonnet-5",
        "call_count": call_count,
    }


# -- /propose-structure ----------------------------------------------------


async def test_propose_rejects_empty_scope_selection(anon_client_factory) -> None:
    async with anon_client_factory() as client:
        response = await client.post("/api/dashboard/propose-structure", json={"strategy": "by_area"})
    assert response.status_code == 400


async def test_propose_rejects_both_preset_and_tokens(anon_client_factory) -> None:
    tokens = {
        "colors": {
            k: {"light": "#000", "dark": "#fff"}
            for k in [
                "primary", "accent", "background", "surface", "on_surface",
                "state_on", "state_off", "warn", "critical",
            ]
        },
        "typography": {
            "font_family": "Inter",
            "sizes": {"xs": "12px", "sm": "14px", "md": "16px", "lg": "20px", "xl": "24px"},
            "weights": {"regular": 400, "medium": 500, "bold": 700},
        },
        "form": {"border_radius_px": 8, "shadow": "none", "border_width_px": 1, "style_family": "flat"},
        "density": {"mode": "comfortable", "grid_gap_px": 8, "section_spacing_px": 16},
        "card_style": {"primary_style": "Tile-based", "reasoning": "test"},
    }
    async with anon_client_factory() as client:
        response = await client.post(
            "/api/dashboard/propose-structure",
            json={
                "area_ids": ["living_room"],
                "strategy": "by_area",
                "token_preset_id": "some-id",
                "tokens": tokens,
            },
        )
    assert response.status_code == 400


async def test_propose_unknown_preset_returns_404(anon_client_factory) -> None:
    async with anon_client_factory() as client:
        response = await client.post(
            "/api/dashboard/propose-structure",
            json={"area_ids": ["living_room"], "strategy": "by_area", "token_preset_id": "does-not-exist"},
        )
    assert response.status_code == 404


async def test_propose_ha_error_returns_503(anon_client_factory) -> None:
    registry_cache = FakeRegistryCache(error=HAWebSocketError("not connected"))
    async with anon_client_factory(registry_cache=registry_cache) as client:
        response = await client.post(
            "/api/dashboard/propose-structure", json={"area_ids": ["living_room"], "strategy": "by_area"}
        )
    assert response.status_code == 503


async def test_propose_empty_resolved_scope_returns_400(anon_client_factory) -> None:
    async with anon_client_factory() as client:
        response = await client.post(
            "/api/dashboard/propose-structure",
            json={"area_ids": ["nonexistent_area"], "strategy": "by_area"},
        )
    assert response.status_code == 400


async def test_propose_happy_path_returns_candidates_from_fixture(anon_client_factory) -> None:
    async with anon_client_factory() as client:
        response = await client.post(
            "/api/dashboard/propose-structure", json={"area_ids": ["living_room"], "strategy": "by_area"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["proposed_views"][0]["name"] == "Living Room"
    candidate_ids = {c["entity_id"] for c in body["proposed_views"][0]["candidates"]}
    assert candidate_ids == {"light.living_a", "light.living_b"}
    assert body["usage"]["call_count"] == 1


async def test_propose_with_valid_preset(anon_client_factory, db_session: AsyncSession) -> None:
    from dashboard_studio.db.models import TokenPreset

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
            "/api/dashboard/propose-structure",
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
async def test_propose_error_mapping(anon_client_factory, error: Exception, expected_status: int) -> None:
    generation_client = FakeDashboardGenerationClient(error=error)
    async with anon_client_factory(generation_client=generation_client) as client:
        response = await client.post(
            "/api/dashboard/propose-structure", json={"area_ids": ["living_room"], "strategy": "by_area"}
        )
    assert response.status_code == expected_status


async def test_propose_rate_limit_error_sets_retry_after_header(anon_client_factory) -> None:
    generation_client = FakeDashboardGenerationClient(
        error=DashboardGenerationRateLimitError("rate limited", retry_after=30)
    )
    async with anon_client_factory(generation_client=generation_client) as client:
        response = await client.post(
            "/api/dashboard/propose-structure", json={"area_ids": ["living_room"], "strategy": "by_area"}
        )
    assert response.status_code == 429
    assert response.headers["retry-after"] == "30"


# -- /generate ---------------------------------------------------------------


async def test_generate_rejects_empty_curated_views(anon_client_factory) -> None:
    async with anon_client_factory() as client:
        response = await client.post(
            "/api/dashboard/generate",
            json={
                "area_ids": ["living_room"],
                "curated_views": [],
                "available_custom_cards": {},
                "phase1_usage": usage_payload(),
            },
        )
    assert response.status_code == 400


async def test_generate_happy_path_with_curated_subset(anon_client_factory) -> None:
    async with anon_client_factory() as client:
        response = await client.post(
            "/api/dashboard/generate",
            json={
                "area_ids": ["living_room"],
                "curated_views": [
                    {
                        "name": "Living Room",
                        "candidates": [make_candidate("light.living_a").model_dump()],
                    }
                ],
                "available_custom_cards": {},
                "phase1_usage": usage_payload(),
            },
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

    # usage combines the client-echoed phase1_usage with the fake phase-2 outcome's usage
    assert body["usage"]["input_tokens"] == 300 + 200
    assert body["usage"]["output_tokens"] == 100 + 80
    assert body["usage"]["call_count"] == 1 + 1
    assert body["usage"]["model"] == "claude-sonnet-5"


async def test_generate_strips_a_tampered_entity_id_never_in_the_response(db_session: AsyncSession) -> None:
    """Defense-in-depth: even if a client echoes back an entity_id that was
    never actually resolved as a real candidate (or was tampered with), the
    /generate route re-derives valid_entity_ids from the live registry and
    the REAL validate_and_strip() removes it -- the hard entity-ID guarantee
    from M3 doesn't depend on trusting the client's echoed candidate list.

    Unlike the other /generate tests, this one does NOT monkeypatch
    generate_from_curated_views -- it fakes one level lower (the SDK-facing
    DashboardGenerationClient, like test_dashboard_orchestrator.py's
    FakeGenerationClient) so the real orchestrator function and its
    validate_and_strip() call actually run.
    """
    from dashboard_studio.dashboard.config import CardConfig, GridSection, NativeCardType
    from dashboard_studio.dashboard.scope import GeneratedViewSections

    @dataclass
    class FakeSDKLevelClient:
        async def propose_view_structure(self, *_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("propose_view_structure should not be called by /generate")

        async def generate_view_cards(self, *_args: Any, **_kwargs: Any) -> Any:
            from dashboard_studio.dashboard.generation_client import GenerationCallResult

            return GenerationCallResult(
                output=GeneratedViewSections(
                    sections=[
                        GridSection(
                            cards=[
                                CardConfig(card_type=NativeCardType.tile, entity="light.living_a"),
                                CardConfig(card_type=NativeCardType.tile, entity="light.does_not_exist"),
                            ]
                        )
                    ]
                ),
                input_tokens=1,
                output_tokens=1,
                estimated_cost_usd=0.0,
                model="claude-sonnet-5",
            )

    app = FastAPI()
    app.include_router(routes_dashboard.router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[get_registry_cache] = lambda: FakeRegistryCache(snapshot=make_snapshot())
    app.dependency_overrides[get_dashboard_generation_client] = lambda: FakeSDKLevelClient()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/dashboard/generate",
            json={
                "area_ids": ["living_room"],
                "curated_views": [
                    {
                        "name": "Living Room",
                        "candidates": [make_candidate("light.does_not_exist").model_dump()],
                    }
                ],
                "available_custom_cards": {},
                "phase1_usage": usage_payload(),
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert "light.does_not_exist" not in body["yaml"]
    assert body["validation"]["removed_entity_refs"] >= 1


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
            "/api/dashboard/generate",
            json={
                "area_ids": ["living_room"],
                "curated_views": [{"name": "V", "candidates": []}],
                "available_custom_cards": {},
                "phase1_usage": usage_payload(),
            },
        )
    assert response.status_code == expected_status
