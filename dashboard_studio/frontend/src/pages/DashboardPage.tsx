import { useEffect, useState } from "react";
import { DashboardResultView } from "../components/dashboard/DashboardResultView";
import { DashboardYamlDownloadButton } from "../components/dashboard/DashboardYamlDownloadButton";
import { ScopeSelector } from "../components/dashboard/ScopeSelector";
import { StrategyPicker } from "../components/dashboard/StrategyPicker";
import { ValidationReportView } from "../components/dashboard/ValidationReportView";
import { useRegistrySnapshot } from "../hooks/useRegistrySnapshot";
import {
  api,
  ApiError,
  type DashboardUsageInfo,
  type GenerateDashboardResponse,
  type GenerationStrategy,
  type TokenPresetSummary,
} from "../lib/apiClient";

export function DashboardPage() {
  const { data: registry } = useRegistrySnapshot();

  const [selectedAreaIds, setSelectedAreaIds] = useState<string[]>([]);
  const [selectedFloorIds, setSelectedFloorIds] = useState<string[]>([]);
  const [strategy, setStrategy] = useState<GenerationStrategy>("automatic");

  const [presets, setPresets] = useState<TokenPresetSummary[]>([]);
  const [presetId, setPresetId] = useState<string>("");

  const [result, setResult] = useState<GenerateDashboardResponse | null>(null);
  const [usage, setUsage] = useState<DashboardUsageInfo | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api.listTokenPresets().then(setPresets, () => setPresets([]));
  }, []);

  async function handleGenerate() {
    setResult(null);
    setUsage(null);
    setError(null);
    setGenerating(true);
    try {
      const response = await api.generateDashboard({
        area_ids: selectedAreaIds,
        floor_ids: selectedFloorIds,
        strategy,
        token_preset_id: presetId || null,
      });
      setResult(response);
      setUsage(response.usage);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Dashboard-Generierung fehlgeschlagen. Bitte erneut versuchen.",
      );
    } finally {
      setGenerating(false);
    }
  }

  const canGenerate = selectedAreaIds.length > 0 || selectedFloorIds.length > 0;

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-base font-medium">Dashboard generieren</h2>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-3">
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
            onClick={() => void handleGenerate()}
            disabled={!canGenerate || generating}
            className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {generating ? "Generiert…" : "Dashboard generieren"}
          </button>

          {error && <p className="text-sm text-red-600">{error}</p>}
          {usage && (
            <p className="text-xs text-gray-400">
              Modell: {usage.model} · {usage.input_tokens + usage.output_tokens} Tokens
              {usage.estimated_cost_usd !== null && ` · ~$${usage.estimated_cost_usd.toFixed(4)}`}
            </p>
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
            </>
          ) : (
            <p className="text-sm text-gray-500">
              Wähle Bereiche/Etagen und eine Strategie aus und generiere einen
              Dashboard-Vorschlag. Es wird noch nichts in Home Assistant gespeichert.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
