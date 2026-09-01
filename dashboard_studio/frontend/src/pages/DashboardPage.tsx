import { useEffect, useState } from "react";
import {
  EntityCurationPanel,
  curatedViewsFromState,
  seedCurationState,
  type CurationState,
} from "../components/dashboard/EntityCurationPanel";
import { DashboardResultView } from "../components/dashboard/DashboardResultView";
import { DashboardYamlDownloadButton } from "../components/dashboard/DashboardYamlDownloadButton";
import { ScopeSelector } from "../components/dashboard/ScopeSelector";
import { StrategyPicker } from "../components/dashboard/StrategyPicker";
import { ValidationReportView } from "../components/dashboard/ValidationReportView";
import { useRegistrySnapshot } from "../hooks/useRegistrySnapshot";
import {
  api,
  ApiError,
  type GenerateDashboardResponse,
  type GenerationStrategy,
  type ProposeStructureResponse,
  type TokenPresetSummary,
} from "../lib/apiClient";

export function DashboardPage() {
  const { data: registry } = useRegistrySnapshot();

  const [selectedAreaIds, setSelectedAreaIds] = useState<string[]>([]);
  const [selectedFloorIds, setSelectedFloorIds] = useState<string[]>([]);
  const [strategy, setStrategy] = useState<GenerationStrategy>("automatic");

  const [presets, setPresets] = useState<TokenPresetSummary[]>([]);
  const [presetId, setPresetId] = useState<string>("");

  const [proposal, setProposal] = useState<ProposeStructureResponse | null>(null);
  const [curation, setCuration] = useState<CurationState>({});
  const [proposing, setProposing] = useState(false);
  const [proposeError, setProposeError] = useState<string | null>(null);

  const [result, setResult] = useState<GenerateDashboardResponse | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  useEffect(() => {
    void api.listTokenPresets().then(setPresets, () => setPresets([]));
  }, []);

  async function handlePropose() {
    setProposal(null);
    setCuration({});
    setResult(null);
    setGenerateError(null);
    setProposeError(null);
    setProposing(true);
    try {
      const response = await api.proposeDashboardStructure({
        area_ids: selectedAreaIds,
        floor_ids: selectedFloorIds,
        strategy,
        token_preset_id: presetId || null,
      });
      setProposal(response);
      setCuration(seedCurationState(response.proposed_views));
    } catch (err) {
      setProposeError(
        err instanceof ApiError
          ? err.message
          : "Struktur-Vorschlag fehlgeschlagen. Bitte erneut versuchen.",
      );
    } finally {
      setProposing(false);
    }
  }

  async function handleGenerate() {
    if (!proposal) return;
    setResult(null);
    setGenerateError(null);
    setGenerating(true);
    try {
      const curatedViews = curatedViewsFromState(proposal.proposed_views, curation);
      const response = await api.generateDashboard({
        area_ids: selectedAreaIds,
        floor_ids: selectedFloorIds,
        curated_views: curatedViews,
        available_custom_cards: proposal.available_custom_cards,
        style_hint: proposal.style_hint,
        phase1_usage: proposal.usage,
      });
      setResult(response);
    } catch (err) {
      setGenerateError(
        err instanceof ApiError
          ? err.message
          : "Dashboard-Generierung fehlgeschlagen. Bitte erneut versuchen.",
      );
    } finally {
      setGenerating(false);
    }
  }

  function handleBack() {
    setProposal(null);
    setCuration({});
    setResult(null);
    setProposeError(null);
    setGenerateError(null);
  }

  const canPropose = selectedAreaIds.length > 0 || selectedFloorIds.length > 0;
  const includedViewCount = Object.values(curation).filter((v) => v.included).length;

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-base font-medium">Dashboard generieren</h2>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-3">
          {!proposal ? (
            <>
              <ScopeSelector
                areas={registry?.areas ?? []}
                floors={registry?.floors ?? []}
                selectedAreaIds={selectedAreaIds}
                selectedFloorIds={selectedFloorIds}
                onChange={(areaIds, floorIds) => {
                  setSelectedAreaIds(areaIds);
                  setSelectedFloorIds(floorIds);
                }}
              />

              <StrategyPicker value={strategy} onChange={setStrategy} />

              <div className="flex flex-col gap-2 rounded border border-gray-200 bg-white p-3">
                <h3 className="text-sm font-semibold text-gray-800">Design-Token-Preset (optional)</h3>
                <select
                  value={presetId}
                  onChange={(event) => setPresetId(event.target.value)}
                  className="rounded border border-gray-300 px-2 py-1 text-sm"
                >
                  <option value="">Kein Preset</option>
                  {presets.map((preset) => (
                    <option key={preset.id} value={preset.id}>
                      {preset.name}
                    </option>
                  ))}
                </select>
              </div>

              <button
                type="button"
                onClick={() => void handlePropose()}
                disabled={!canPropose || proposing}
                className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {proposing ? "Schlägt vor…" : "Struktur vorschlagen"}
              </button>

              {proposeError && <p className="text-sm text-red-600">{proposeError}</p>}
            </>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-800">Entitäten kuratieren</h3>
                <button type="button" onClick={handleBack} className="text-xs text-blue-600 hover:underline">
                  Zurück
                </button>
              </div>

              {proposal.notes.length > 0 && (
                <div className="rounded border border-yellow-200 bg-yellow-50 p-3">
                  <ul className="flex flex-col gap-0.5 text-xs text-yellow-800">
                    {proposal.notes.map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </ul>
                </div>
              )}

              <EntityCurationPanel
                proposedViews={proposal.proposed_views}
                value={curation}
                onChange={setCuration}
              />

              <button
                type="button"
                onClick={() => void handleGenerate()}
                disabled={includedViewCount === 0 || generating}
                className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {generating ? "Generiert…" : "Dashboard generieren"}
              </button>

              {generateError && <p className="text-sm text-red-600">{generateError}</p>}
              <p className="text-xs text-gray-400">
                Modell: {proposal.usage.model} ·{" "}
                {proposal.usage.input_tokens + proposal.usage.output_tokens} Tokens
                {proposal.usage.estimated_cost_usd !== null &&
                  ` · ~$${proposal.usage.estimated_cost_usd.toFixed(4)}`}
              </p>
            </>
          )}
        </div>

        <div className="flex flex-col gap-4">
          {result ? (
            <>
              <DashboardResultView dashboard={result.dashboard} />
              <ValidationReportView validation={result.validation} />
              {result.notes.length > 0 && (
                <div className="rounded border border-yellow-200 bg-yellow-50 p-3">
                  <ul className="flex flex-col gap-0.5 text-xs text-yellow-800">
                    {result.notes.map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </ul>
                </div>
              )}
              <DashboardYamlDownloadButton yaml={result.yaml} />
              <p className="text-xs text-gray-400">
                Modell: {result.usage.model} · {result.usage.input_tokens + result.usage.output_tokens}{" "}
                Tokens
                {result.usage.estimated_cost_usd !== null &&
                  ` · ~$${result.usage.estimated_cost_usd.toFixed(4)}`}
              </p>
            </>
          ) : (
            <p className="text-sm text-gray-500">
              Wähle Bereiche/Etagen und eine Strategie aus, schlage eine Struktur vor, wähle dann
              Ansichten und Entitäten individuell aus, bevor das Dashboard generiert wird. Es wird noch
              nichts in Home Assistant gespeichert.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
