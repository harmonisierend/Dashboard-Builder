import type { ProposedView } from "../../lib/apiClient";

export interface ViewCurationState {
  included: boolean;
  selectedEntityIds: Set<string>;
}

export type CurationState = Record<string, ViewCurationState>;

interface EntityCurationPanelProps {
  proposedViews: ProposedView[];
  value: CurationState;
  onChange: (next: CurationState) => void;
}

export function seedCurationState(proposedViews: ProposedView[]): CurationState {
  const state: CurationState = {};
  for (const view of proposedViews) {
    state[view.name] = {
      included: true,
      selectedEntityIds: new Set(view.candidates.map((c) => c.entity_id)),
    };
  }
  return state;
}

export function curatedViewsFromState(
  proposedViews: ProposedView[],
  state: CurationState,
): ProposedView[] {
  return proposedViews
    .filter((view) => state[view.name]?.included)
    .map((view) => ({
      name: view.name,
      candidates: view.candidates.filter((c) => state[view.name]?.selectedEntityIds.has(c.entity_id)),
    }));
}

export function EntityCurationPanel({ proposedViews, value, onChange }: EntityCurationPanelProps) {
  function toggleViewIncluded(viewName: string) {
    const current = value[viewName];
    if (!current) return;
    onChange({ ...value, [viewName]: { ...current, included: !current.included } });
  }

  function toggleEntity(viewName: string, entityId: string) {
    const current = value[viewName];
    if (!current) return;
    const next = new Set(current.selectedEntityIds);
    if (next.has(entityId)) {
      next.delete(entityId);
    } else {
      next.add(entityId);
    }
    onChange({ ...value, [viewName]: { ...current, selectedEntityIds: next } });
  }

  function selectAll(viewName: string, entityIds: string[]) {
    const current = value[viewName];
    if (!current) return;
    onChange({ ...value, [viewName]: { ...current, selectedEntityIds: new Set(entityIds) } });
  }

  function selectNone(viewName: string) {
    const current = value[viewName];
    if (!current) return;
    onChange({ ...value, [viewName]: { ...current, selectedEntityIds: new Set() } });
  }

  return (
    <div className="flex flex-col gap-3">
      {proposedViews.map((view) => {
        const state = value[view.name];
        const included = state?.included ?? true;
        const selected = state?.selectedEntityIds ?? new Set<string>();

        return (
          <div key={view.name} className="rounded border border-gray-200 bg-white p-3">
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-sm font-semibold text-gray-800">
                <input
                  type="checkbox"
                  checked={included}
                  onChange={() => toggleViewIncluded(view.name)}
                />
                {view.name}
              </label>
              {included && (
                <span className="flex gap-2 text-xs text-blue-600">
                  <button
                    type="button"
                    onClick={() => selectAll(view.name, view.candidates.map((c) => c.entity_id))}
                    className="hover:underline"
                  >
                    Alle auswählen
                  </button>
                  <button type="button" onClick={() => selectNone(view.name)} className="hover:underline">
                    Keine auswählen
                  </button>
                </span>
              )}
            </div>

            <ul className={`mt-2 flex flex-col gap-1 ${included ? "" : "opacity-40"}`}>
              {view.candidates.map((candidate) => (
                <li key={candidate.entity_id}>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={selected.has(candidate.entity_id)}
                      disabled={!included}
                      onChange={() => toggleEntity(view.name, candidate.entity_id)}
                    />
                    <span>{candidate.name}</span>
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500">
                      {candidate.domain}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
