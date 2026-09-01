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
from dashboard_studio.dashboard.orchestrator import generate_dashboard
from dashboard_studio.dashboard.scope import (
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


def call_result(output: Any, *, input_tokens: int = 100, output_tokens: int = 50, cost: float | None = 0.001) -> GenerationCallResult[Any]:
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


async def test_happy_path_assembles_all_views() -> None:
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
    fake = FakeGenerationClient(
        structure_result=call_result(structure),
        view_results={
            "Living Room": call_result(sections_with_card("light.living")),
            "Kitchen": call_result(sections_with_card("light.kitchen")),
        },
    )

    outcome = await generate_dashboard(
        client=as_client(fake),
        scoped_entities=entities,
        lovelace_resources=[],
        strategy=GenerationStrategy.by_area,
        tokens=None,
    )

    assert [v.title for v in outcome.dashboard.views] == ["Living Room", "Kitchen"]
    assert outcome.validation.removed_cards == 0
    assert set(fake.calls) == {"Living Room", "Kitchen"}


async def test_one_view_failure_is_isolated_with_a_note() -> None:
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
    fake = FakeGenerationClient(
        structure_result=call_result(structure),
        view_results={
            "Living Room": call_result(sections_with_card("light.living")),
            "Kitchen": DashboardGenerationUpstreamError("boom"),
        },
    )

    outcome = await generate_dashboard(
        client=as_client(fake),
        scoped_entities=entities,
        lovelace_resources=[],
        strategy=GenerationStrategy.by_area,
        tokens=None,
    )

    assert [v.title for v in outcome.dashboard.views] == ["Living Room"]
    assert any("Kitchen" in note for note in outcome.notes)


async def test_hallucinated_entity_is_stripped_by_validation_gate() -> None:
    entities = [make_entity(entity_id="light.real", area_id="living_room")]
    structure = ViewStructureProposal(
        views=[ViewProposal(name="Living Room", selector=ViewProposalEntitySelector(area_ids=["living_room"]))]
    )
    fake = FakeGenerationClient(
        structure_result=call_result(structure),
        view_results={"Living Room": call_result(sections_with_card("light.hallucinated"))},
    )

    outcome = await generate_dashboard(
        client=as_client(fake),
        scoped_entities=entities,
        lovelace_resources=[],
        strategy=GenerationStrategy.by_area,
        tokens=None,
    )

    dumped = outcome.dashboard.model_dump_json()
    assert "light.hallucinated" not in dumped
    assert outcome.validation.removed_entity_refs >= 1


async def test_more_than_max_proposed_views_is_truncated_with_note() -> None:
    entities = [make_entity(entity_id=f"light.{i}", area_id=f"area_{i}") for i in range(10)]
    structure = ViewStructureProposal(
        views=[
            ViewProposal(name=f"View {i}", selector=ViewProposalEntitySelector(area_ids=[f"area_{i}"]))
            for i in range(10)
        ]
    )
    fake = FakeGenerationClient(
        structure_result=call_result(structure),
        view_results={
            f"View {i}": call_result(sections_with_card(f"light.{i}")) for i in range(8)
        },
    )

    outcome = await generate_dashboard(
        client=as_client(fake),
        scoped_entities=entities,
        lovelace_resources=[],
        strategy=GenerationStrategy.automatic,
        tokens=None,
    )

    assert len(outcome.dashboard.views) == 8
    assert any("begrenzt" in note for note in outcome.notes)
    assert "View 8" not in fake.calls
    assert "View 9" not in fake.calls


async def test_zero_proposed_views_raises_upstream_error() -> None:
    structure = ViewStructureProposal(views=[])
    fake = FakeGenerationClient(structure_result=call_result(structure))

    with pytest.raises(DashboardGenerationUpstreamError):
        await generate_dashboard(
            client=as_client(fake),
            scoped_entities=[make_entity()],
            lovelace_resources=[],
            strategy=GenerationStrategy.automatic,
            tokens=None,
        )


async def test_selector_with_zero_candidates_skips_without_calling_llm() -> None:
    entities = [make_entity(entity_id="light.real", area_id="living_room")]
    structure = ViewStructureProposal(
        views=[
            ViewProposal(name="Empty View", selector=ViewProposalEntitySelector(area_ids=["nonexistent"]))
        ]
    )
    fake = FakeGenerationClient(structure_result=call_result(structure), view_results={})

    outcome = await generate_dashboard(
        client=as_client(fake),
        scoped_entities=entities,
        lovelace_resources=[],
        strategy=GenerationStrategy.by_area,
        tokens=None,
    )

    assert outcome.dashboard.views == []
    assert fake.calls == []
    assert any("Empty View" in note for note in outcome.notes)


async def test_usage_totals_sum_across_calls() -> None:
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
    fake = FakeGenerationClient(
        structure_result=call_result(structure, input_tokens=300, output_tokens=100, cost=0.01),
        view_results={
            "Living Room": call_result(
                sections_with_card("light.living"), input_tokens=200, output_tokens=80, cost=0.005
            ),
            "Kitchen": call_result(
                sections_with_card("light.kitchen"), input_tokens=150, output_tokens=60, cost=0.004
            ),
        },
    )

    outcome = await generate_dashboard(
        client=as_client(fake),
        scoped_entities=entities,
        lovelace_resources=[],
        strategy=GenerationStrategy.by_area,
        tokens=None,
    )

    assert outcome.usage.call_count == 3
    assert outcome.usage.input_tokens == 300 + 200 + 150
    assert outcome.usage.output_tokens == 100 + 80 + 60
    assert outcome.usage.estimated_cost_usd == pytest.approx(0.01 + 0.005 + 0.004)


async def test_one_unrecognized_model_call_poisons_total_cost_to_none() -> None:
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
    fake = FakeGenerationClient(
        structure_result=call_result(structure, cost=0.01),
        view_results={
            "Living Room": call_result(sections_with_card("light.living"), cost=0.005),
            "Kitchen": call_result(sections_with_card("light.kitchen"), cost=None),
        },
    )

    outcome = await generate_dashboard(
        client=as_client(fake),
        scoped_entities=entities,
        lovelace_resources=[],
        strategy=GenerationStrategy.by_area,
        tokens=None,
    )

    assert outcome.usage.estimated_cost_usd is None


async def test_detected_family_without_catalog_entry_notes_but_does_not_crash() -> None:
    entities = [make_entity(entity_id="light.real", area_id="living_room")]
    structure = ViewStructureProposal(
        views=[ViewProposal(name="V", selector=ViewProposalEntitySelector(area_ids=["living_room"]))]
    )
    fake = FakeGenerationClient(
        structure_result=call_result(structure),
        view_results={"V": call_result(sections_with_card("light.real"))},
    )
    resources = [LovelaceResource(id="1", type="module", url="/hacsfiles/card-mod/card-mod.js")]

    outcome = await generate_dashboard(
        client=as_client(fake),
        scoped_entities=entities,
        lovelace_resources=resources,
        strategy=GenerationStrategy.by_area,
        tokens=None,
    )

    assert any("card-mod" in note for note in outcome.notes)
