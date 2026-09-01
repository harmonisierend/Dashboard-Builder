import { useState } from "react";
import { api, ApiError, type DesignTokenSet } from "../../lib/apiClient";

interface ThemeExportButtonProps {
  tokens: DesignTokenSet | null;
}

export function ThemeExportButton({ tokens }: ThemeExportButtonProps) {
  const [themeName, setThemeName] = useState("Mein Theme");
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  async function handleExport() {
    if (!tokens) return;
    setExporting(true);
    setError(null);
    try {
      const { filename, yaml } = await api.exportThemeYaml(themeName, tokens);
      const blob = new Blob([yaml], { type: "application/x-yaml" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Export fehlgeschlagen.");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded border border-gray-200 bg-white p-3">
      <h3 className="text-sm font-semibold text-gray-800">Als HA-Theme exportieren</h3>
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={themeName}
          onChange={(event) => setThemeName(event.target.value)}
          className="flex-1 rounded border border-gray-300 px-2 py-1 text-sm"
        />
        <button
          type="button"
          onClick={() => void handleExport()}
          disabled={!tokens || !themeName.trim() || exporting}
          className="rounded border border-gray-300 px-3 py-1 text-sm hover:bg-gray-50 disabled:opacity-50"
        >
          themes.yaml exportieren
        </button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <p className="text-xs text-gray-500">
        Nach dem Import in Home Assistant ist ein Theme-Reload nötig, damit die Änderung
        sichtbar wird.
      </p>
    </div>
  );
}
