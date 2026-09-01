"""Scope resolution for dashboard generation: which entities are in play,
and how they're summarized/filtered for the two generation calls.

Full per-entity curation is Milestone 4 -- this module only resolves a
coarse Area/Floor pre-selection (`GenerationScope`) down to entities, then
further narrows per proposed view via `resolve_view_entities`.
"""

from __future__ import annotations

from pydantic import BaseModel

from dashboard_studio.dashboard.config import GridSection
from dashboard_studio.registry.filters import filter_entities
from dashboard_studio.registry.snapshot import EntityRecord

# Safety cap: a large multi-floor scope could otherwise cause the model to
# propose enough views to trigger many phase-2 calls, ballooning latency
# and cost unboundedly. Extras are truncated with a note by the
# orchestrator, not rejected outright.
MAX_PROPOSED_VIEWS = 8


class GenerationScope(BaseModel):
    area_ids: list[str] = []
    floor_ids: list[str] = []


def entities_in_scope(
    entities: list[EntityRecord], scope: GenerationScope, include_diagnostic: bool = False
) -> list[EntityRecord]:
    filtered = filter_entities(entities, include_diagnostic)
    area_ids = set(scope.area_ids)
    floor_ids = set(scope.floor_ids)
    return [
        entity
        for entity in filtered
        if (entity.area_id in area_ids) or (entity.floor_id in floor_ids)
    ]


class DomainCount(BaseModel):
    domain: str
    count: int


class AreaSummary(BaseModel):
    area_id: str | None
    area_name: str | None
    floor_name: str | None
    domain_counts: list[DomainCount]


class ScopeSummary(BaseModel):
    total_entities: int
    areas: list[AreaSummary]


def summarize_scope(entities: list[EntityRecord]) -> ScopeSummary:
    """Groups scoped entities by area, counting per domain within each
    area. This summary -- never the full entity list -- is phase 1's
    entire input, keeping the structure-proposal call cheap regardless of
    how many entities are actually in scope.
    """
    by_area: dict[str | None, list[EntityRecord]] = {}
    for entity in entities:
        by_area.setdefault(entity.area_id, []).append(entity)

    areas: list[AreaSummary] = []
    for area_id, area_entities in by_area.items():
        domain_totals: dict[str, int] = {}
        for entity in area_entities:
            domain_totals[entity.domain] = domain_totals.get(entity.domain, 0) + 1
        areas.append(
            AreaSummary(
                area_id=area_id,
                area_name=area_entities[0].area_name,
                floor_name=area_entities[0].floor_name,
                domain_counts=[
                    DomainCount(domain=domain, count=count)
                    for domain, count in sorted(domain_totals.items())
                ],
            )
        )

    return ScopeSummary(total_entities=len(entities), areas=areas)


class ViewProposalEntitySelector(BaseModel):
    area_ids: list[str] = []
    domains: list[str] = []


class ViewProposal(BaseModel):
    name: str
    selector: ViewProposalEntitySelector


class ViewStructureProposal(BaseModel):
    views: list[ViewProposal]


def resolve_view_entities(
    scoped_entities: list[EntityRecord], selector: ViewProposalEntitySelector
) -> list[EntityRecord]:
    """AND between the area/domain dimensions, OR within each dimension.
    An empty list on either side means "no filter on that dimension" -- a
    selector naming an area/domain that doesn't actually exist in scope
    degrades gracefully to zero candidates, never an error.
    """
    area_ids = set(selector.area_ids)
    domains = set(selector.domains)
    return [
        entity
        for entity in scoped_entities
        if (not area_ids or entity.area_id in area_ids) and (not domains or entity.domain in domains)
    ]


class CandidateEntitySummary(BaseModel):
    entity_id: str
    domain: str
    name: str
    area_name: str | None
    device_class: str | None


def to_candidate_summary(entity: EntityRecord) -> CandidateEntitySummary:
    device_class = entity.attributes.get("device_class")
    return CandidateEntitySummary(
        entity_id=entity.entity_id,
        domain=entity.domain,
        name=entity.name,
        area_name=entity.area_name,
        device_class=str(device_class) if device_class is not None else None,
    )


class GeneratedViewSections(BaseModel):
    """Phase 2's output_format -- just the sections; the orchestrator
    wraps this into a full SectionsView using the proposal's own name.
    """

    sections: list[GridSection] = []
