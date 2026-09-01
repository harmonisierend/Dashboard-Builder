import { useState } from "react";
import { ImageUpload } from "../components/design/ImageUpload";
import { PresetManager } from "../components/design/PresetManager";
import { ThemeExportButton } from "../components/design/ThemeExportButton";
import { TokenEditor } from "../components/design/TokenEditor";
import { api, ApiError, type DesignTokenSet, type UsageInfo } from "../lib/apiClient";

export function DesignPage() {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [tokens, setTokens] = useState<DesignTokenSet | null>(null);
  const [usage, setUsage] = useState<UsageInfo | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleUploaded(uploadId: string, newPreviewUrl: string) {
    setPreviewUrl(newPreviewUrl);
    setTokens(null);
    setUsage(null);
    setError(null);
    setAnalyzing(true);
    try {
      const result = await api.analyzeDesign(uploadId);
      setTokens(result.tokens);
      setUsage(result.usage);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Design-Analyse fehlgeschlagen. Bitte erneut versuchen.",
      );
    } finally {
      setAnalyzing(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-base font-medium">Design-Analyse</h2>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-3">
          <ImageUpload onUploaded={(id, url) => void handleUploaded(id, url)} />
          {previewUrl && (
            <img
              src={previewUrl}
              alt="Vorschau der hochgeladenen Design-Referenz"
              className="max-h-64 rounded border border-gray-200 object-contain"
            />
          )}
          {analyzing && <p className="text-sm text-gray-500">Design wird analysiert…</p>}
          {error && <p className="text-sm text-red-600">{error}</p>}
          {usage && (
            <p className="text-xs text-gray-400">
              Modell: {usage.model} · {usage.input_tokens + usage.output_tokens} Tokens
              {usage.estimated_cost_usd !== null &&
                ` · ~$${usage.estimated_cost_usd.toFixed(4)}`}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-4">
          {tokens ? (
            <>
              <TokenEditor tokens={tokens} onChange={setTokens} />
              <ThemeExportButton tokens={tokens} />
            </>
          ) : (
            <p className="text-sm text-gray-500">
              Lade eine Design-Referenz hoch, um Design-Token zu erzeugen, oder lade ein
              gespeichertes Preset.
            </p>
          )}
          <PresetManager currentTokens={tokens} onLoad={setTokens} />
        </div>
      </div>
    </div>
  );
}
