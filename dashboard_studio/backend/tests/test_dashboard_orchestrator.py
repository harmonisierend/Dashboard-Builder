from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from dashboard_studio.dashboard.config import (
    CardConfig,
    GenerationStrategy,
    GridSection,
    NativeCardType,
)
from dashboard_studio.dashboard.generation_client import (
    DashboardGenerationClient,
    DashboardGenerationUpstreamError,
    GenerationCallResult,
)
from dashboard_studio.dashboard.orchestrator import GenerationUsageTotals as Usage
from dashboard_studio.dashboard.orchestrator import (
    ProposedView,
    combine_usage_totals,
    generate_from_curated_views,
    propose_structure,
)
from dashboard_studio.dashboard.scope import (
    CandidateEntitySummary,
    GeneratedViewSections,
    ScopeSummary,
    ViewProposal,
    ViewProposalEntitySelector,
    ViewStructureProposal,
)
from dashboard_studio.ha.models import LovelaceResource
from dashboard_studio.registry.snapshot import EntityRecord


def make_entity(**overrides: Any) -> EntityRecord:
    defaults: dict[str, Any] = {
        "entity_id": "light.test",
        "domain": "light",
        "name": "Test Light",
        "available": True,
    }
    defaults.update(overrides)
    return EntityRecord(**defaults)


def call_result(
    output: Any, *, input_tokens: int = 100, output_tokens: int = 50, cost: float | None = 0.001
) -> GenerationCallResult[Any]:
    return GenerationCallResult(
        output=output,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=cost,
        model="claude-sonnet-5",
    )


@dataclass
class FakeGenerationClient:
    """Fakes DashboardGenerationClient's two public methods directly -- one
    layer above the SDK fake in test_dashboard_generation_client.py, matching
    how test_routes_design.py fakes AnthropicDesignClient above the SDK
    fake in test_anthropic_client.py.
    """

    structure_result: GenerationCallResult[ViewStructureProposal] | Exception
    view_results: dict[str, GenerationCallResult[GeneratedViewSections] | Exception] = field(
        default_factory=dict
    )
    calls: list[str] = field(default_factory=list)

    async def propose_view_structure(
        self, scope_summary: ScopeSummary, strategy: GenerationStrategy
    ) -> GenerationCallResult[ViewStructureProposal]:
        if isinstance(self.structure_result, Exception):
            raise self.structure_result
        return self.structure_result

    async def generate_view_cards(
        self,
        view_name: str,
        candidates: list[Any],
        available_custom_cards: dict[str, dict[str, str]],
        style_hint: Any,
    ) -> GenerationCallResult[GeneratedViewSections]:
        self.calls.append(view_name)
        result = self.view_results[view_name]
        if isinstance(result, Exception):
            raise result
        return result


def as_client(fake: FakeGenerationClient) -> DashboardGenerationClient:
    return fake  # type: ignore[return-value]


def sections_with_card(entity_id: str) -> GeneratedViewSections:
    return GeneratedViewSections(
        sections=[GridSection(cards=[CardConfig(card_type=NativeCardType.tile, entity=entity_id)])]
    )


def make_candidate(entity_id: str) -> CandidateEntitySummary:
    return CandidateEntitySummary(
        entity_id=entity_id, domain=entity_id.split(".")[0], name=entity_id, area_name=None, device_class=None
    )


# -- propose_structure --------------------------------------------------


async def test_propose_structure_returns_per_view_candidates() -> None:
    entities = [
        make_entity(entity_id="light.living", area_id="living_room"),
        make_entity(entity_id="light.kitchen", area_id="kitchen"),
    ]
    structure = ViewStructureProposal(
        views=[
            ViewProposal(name="Living Room", selector=ViewProposalEntitySelector(area_ids=["living_room"])),
            ViewProposal(name="Kitchen", selector=ViewProposalEntitySelector(area_ids=["kitchen"])),
        ]
    )
    fake = FakeGenerationClient(structure_result=call_result(structure))

    outcome = await propose_structure(
        client=as_client(fake),
        scoped_entities=entities,
        lovelace_resources=[],
        strategy=GenerationStrategy.by_area,
        tokens=None,
    )

    assert [v.name for v in outcome.proposed_views] == ["Living Room", "Kitchen"]
    assert [c.entity_id for c in outcome.proposed_views[0].candidates] == ["light.living"]
    assert [c.entity_id for c in outcome.proposed_views[1].candidates] == ["light.kitchen"]
    assert outcome.usage.call_count == 1
    assert fake.calls == []  # no phase-2 calls made


async def test_propose_structure_truncates_to_max_proposed_views() -> None:
    entities = [make_entity(entity_id=f"light.{i}", area_id=f"area_{i}") for i in range(10)]
    structure = ViewStructureProposal(
        views=[
            ViewProposal(name=f"View {i}", selector=ViewProposalEntitySelector(area_ids=[f"area_{i}"]))
            for i in range(10)
        ]
    )
    fake = FakeGenerationClient(structure_result=call_result(structure))

    outcome = await propose_structure(
        client=as_client(fake),
        scoped_entities=entities,
        lovelace_resources=[],
        strategy=GenerationStrategy.automatic,
        tokens=None,
    )

    assert len(outcome.proposed_views) == 8
    assert any("begrenzt" in note for note in outcome.notes)


async def test_propose_structure_zero_proposed_views_raises() -> None:
    structure = ViewStructureProposal(views=[])
    fake = FakeGenerationClient(structure_result=call_result(structure))

    with pytest.raises(DashboardGenerationUpstreamError):
        await propose_structure(
            client=as_client(fake),
            scoped_entities=[make_entity()],
            lovelace_resources=[],
            strategy=GenerationStrategy.automatic,
            tokens=None,
        )


async def test_propose_structure_selector_with_zero_candidates_is_omitted_with_note() -> None:
    entities = [make_entity(entity_id="light.real", area_id="living_room")]
    structure = ViewStructureProposal(
        views=[
            ViewProposal(name="Empty View", selector=ViewProposalEntitySelector(area_ids=["nonexistent"]))
        ]
    )
    fake = FakeGenerationClient(structure_result=call_result(structure))

    outcome = await propose_structure(
        client=as_client(fake),
        scoped_entities=entities,
        lovelace_resources=[],
        strategy=GenerationStrategy.by_area,
        tokens=None,
    )

    assert outcome.proposed_views == []
    assert any("Empty View" in note for note in outcome.notes)


async def test_propose_structure_detected_family_without_catalog_entry_notes_but_does_not_crash() -> None:
    entities = [make_entity(entity_id="light.real", area_id="living_room")]
    structure = ViewStructureProposal(
        views=[ViewProposal(name="V", selector=ViewProposalEntitySelector(area_ids=["living_room"]))]
    )
    fake = FakeGenerationClient(structure_result=call_result(structure))
    resources = [LovelaceResource(id="1", type="module", url="/hacsfiles/card-mod/card-mod.js")]

    outcome = await propose_structure(
        client=as_client(fake),
        scoped_entities=entities,
        lovelace_resources=resources,
        strategy=GenerationStrategy.by_area,
        tokens=None,
    )

    assert any("card-mod" in note for note in outcome.notes)


# -- generate_from_curated_views -----------------------------------------


async def test_generate_from_curated_views_happy_path() -> None:
    fake = FakeGenerationClient(
        structure_result=call_result(ViewStructureProposal(views=[])),  # unused
        view_results={
            "Living Room": call_result(sections_with_card("light.living")),
            "Kitchen": call_result(sections_with_card("light.kitchen")),
        },
    )
    curated = [
        ProposedView(name="Living Room", candidates=[make_candidate("light.living")]),
        ProposedView(name="Kitchen", candidates=[make_candidate("light.kitchen")]),
    ]

    outcome = await generate_from_curated_views(
        client=as_client(fake),
        curated_views=curated,
        available_custom_cards={},
        style_hint=None,
        valid_entity_ids={"light.living", "light.kitchen"},
    )

    assert [v.title for v in outcome.dashboard.views] == ["Living Room", "Kitchen"]
    assert outcome.validation.removed_cards == 0
    assert set(fake.calls) == {"Living Room", "Kitchen"}


async def test_generate_from_curated_views_one_view_failure_is_isolated_with_a_note() -> None:
    fake = FakeGenerationClient(
        structure_result=call_result(ViewStructureProposal(views=[])),
        view_results={
            "Living Room": call_result(sections_with_card("light.living")),
            "Kitchen": DashboardGenerationUpstreamError("boom"),
        },
    )
    curated = [
        ProposedView(name="Living Room", candidates=[make_candidate("light.living")]),
        ProposedView(name="Kitchen", candidates=[make_candidate("light.kitchen")]),
    ]

    outcome = await generate_from_curated_views(
        client=as_client(fake),
        curated_views=curated,
        available_custom_cards={},
        style_hint=None,
        valid_entity_ids={"light.living", "light.kitchen"},
    )

    assert [v.title for v in outcome.dashboard.views] == ["Living Room"]
    assert any("Kitchen" in note for note in outcome.notes)


async def test_generate_from_curated_views_hallucinated_entity_is_stripped() -> None:
    fake = FakeGenerationClient(
        structure_result=call_result(ViewStructureProposal(views=[])),
        view_results={"Living Room": call_result(sections_with_card("light.hallucinated"))},
    )
    curated = [ProposedView(name="Living Room", candidates=[make_candidate("light.real")])]

    outcome = await generate_from_curated_views(
        client=as_client(fake),
        curated_views=curated,
        available_custom_cards={},
        style_hint=None,
        valid_entity_ids={"light.real"},
    )

    dumped = outcome.dashboard.model_dump_json()
    assert "light.hallucinated" not in dumped
    assert outcome.validation.removed_entity_refs >= 1


async def test_generate_from_curated_views_kept_view_with_no_candidates_is_skipped_without_llm_call() -> None:
    fake = FakeGenerationClient(structure_result=call_result(ViewStructureProposal(views=[])))
    curated = [ProposedView(name="Emptied Out", candidates=[])]

    outcome = await generate_from_curated_views(
        client=as_client(fake),
        curated_views=curated,
        available_custom_cards={},
        style_hint=None,
        valid_entity_ids=set(),
    )

    assert outcome.dashboard.views == []
    assert fake.calls == []
    assert any("Emptied Out" in note for note in outcome.notes)


async def test_generate_from_curated_views_zero_call_count_has_empty_model() -> None:
    fake = FakeGenerationClient(structure_result=call_result(ViewStructureProposal(views=[])))
    curated = [ProposedView(name="Emptied Out", candidates=[])]

    outcome = await generate_from_curated_views(
        client=as_client(fake),
        curated_views=curated,
        available_custom_cards={},
        style_hint=None,
        valid_entity_ids=set(),
    )

    assert outcome.usage.call_count == 0
    assert outcome.usage.estimated_cost_usd == 0.0


# -- combine_usage_totals -------------------------------------------------


def test_combine_usage_totals_sums_when_both_costs_known() -> None:
    phase1 = Usage(input_tokens=100, output_tokens=50, estimated_cost_usd=0.01, model="claude-sonnet-5", call_count=1)
    phase2 = Usage(input_tokens=200, output_tokens=80, estimated_cost_usd=0.02, model="", call_count=2)

    combined = combine_usage_totals(phase1, phase2)

    assert combined.input_tokens == 300
    assert combined.output_tokens == 130
    assert combined.estimated_cost_usd == pytest.approx(0.03)
    assert combined.call_count == 3
    assert combined.model == "claude-sonnet-5"


def test_combine_usage_totals_one_unknown_cost_poisons_total() -> None:
    phase1 = Usage(input_tokens=100, output_tokens=50, estimated_cost_usd=0.01, model="claude-sonnet-5", call_count=1)
    phase2 = Usage(input_tokens=200, output_tokens=80, estimated_cost_usd=None, model="", call_count=0)

    combined = combine_usage_totals(phase1, phase2)

    assert combined.estimated_cost_usd is None
    assert combined.model == "claude-sonnet-5"
