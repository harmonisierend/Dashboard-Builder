import { useEffect, useState } from "react";
import { api, ApiError, type DesignTokenSet, type TokenPresetSummary } from "../../lib/apiClient";

interface PresetManagerProps {
  currentTokens: DesignTokenSet | null;
  onLoad: (tokens: DesignTokenSet) => void;
}

export function PresetManager({ currentTokens, onLoad }: PresetManagerProps) {
  const [presets, setPresets] = useState<TokenPresetSummary[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function loadPresets() {
    try {
      setPresets(await api.listTokenPresets());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Presets konnten nicht geladen werden.");
    }
  }

  useEffect(() => {
    // Fetch-on-mount via a custom hook/effect -- see the same justification
    // in useRegistrySnapshot.ts.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadPresets();
  }, []);

  async function handleSave() {
    if (!currentTokens || !name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await api.saveTokenPreset(name.trim(), currentTokens);
      setName("");
      await loadPresets();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Preset konnte nicht gespeichert werden.");
    } finally {
      setSaving(false);
    }
  }

  async function handleLoad(id: string) {
    try {
      const detail = await api.getTokenPreset(id);
      onLoad(detail.tokens);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Preset konnte nicht geladen werden.");
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.deleteTokenPreset(id);
      await loadPresets();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Preset konnte nicht gelöscht werden.");
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded border border-gray-200 bg-white p-3">
      <h3 className="text-sm font-semibold text-gray-800">Presets</h3>

      <div className="flex items-center gap-2">
        <input
          type="text"
          placeholder="Preset-Name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          className="flex-1 rounded border border-gray-300 px-2 py-1 text-sm"
        />
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={!currentTokens || !name.trim() || saving}
          className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Als Preset speichern
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {presets.length === 0 ? (
        <p className="text-xs text-gray-400">Noch keine Presets gespeichert.</p>
      ) : (
        <ul className="flex flex-col divide-y divide-gray-100">
          {presets.map((preset) => (
            <li key={preset.id} className="flex items-center justify-between py-1.5 text-sm">
              <span>{preset.name}</span>
              <span className="flex gap-2">
                <button
                  type="button"
                  onClick={() => void handleLoad(preset.id)}
                  className="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-50"
                >
                  Laden
                </button>
                <button
                  type="button"
                  onClick={() => void handleDelete(preset.id)}
                  className="rounded border border-gray-300 px-2 py-0.5 text-xs text-red-600 hover:bg-red-50"
                >
                  Löschen
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
