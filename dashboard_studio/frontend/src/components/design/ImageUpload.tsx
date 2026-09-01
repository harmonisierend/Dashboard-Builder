import { useRef, useState } from "react";
import { api, ApiError } from "../../lib/apiClient";

// Kept in sync with dashboard_studio/design/uploads.py (ALLOWED_MEDIA_TYPES,
// MAX_UPLOAD_BYTES) so obviously-invalid files are rejected before a
// network round-trip -- the backend re-validates independently regardless.
const ALLOWED_MEDIA_TYPES = ["image/png", "image/jpeg", "image/webp"];
const MAX_UPLOAD_BYTES = 6_000_000;

interface ImageUploadProps {
  onUploaded: (uploadId: string, previewUrl: string) => void;
}

export function ImageUpload({ onUploaded }: ImageUploadProps) {
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function validate(file: File): string | null {
    if (!ALLOWED_MEDIA_TYPES.includes(file.type)) {
      return "Nicht unterstützter Dateityp. Erlaubt sind PNG, JPEG und WebP.";
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      return `Datei ist zu groß (Limit: ${(MAX_UPLOAD_BYTES / 1_000_000).toFixed(1)} MB).`;
    }
    return null;
  }

  async function handleFile(file: File) {
    const validationError = validate(file);
    if (validationError) {
      setError(validationError);
      return;
    }
    setError(null);
    setUploading(true);
    try {
      const response = await api.uploadDesignImage(file);
      const previewUrl = URL.createObjectURL(file);
      onUploaded(response.upload_id, previewUrl);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload fehlgeschlagen.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragOver(false);
          const file = event.dataTransfer.files[0];
          if (file) void handleFile(file);
        }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded border-2 border-dashed p-8 text-center text-sm ${
          dragOver ? "border-blue-500 bg-blue-50" : "border-gray-300 bg-gray-50"
        }`}
      >
        <span>
          {uploading
            ? "Wird hochgeladen…"
            : "Design-Referenz hierher ziehen oder klicken zum Auswählen"}
        </span>
        <span className="text-xs text-gray-400">PNG, JPEG oder WebP, max. 6 MB</span>
        <input
          ref={inputRef}
          type="file"
          accept={ALLOWED_MEDIA_TYPES.join(",")}
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void handleFile(file);
            event.target.value = "";
          }}
        />
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <p className="text-xs text-gray-500">
        Die Referenz dient nur der Ableitung abstrakter Design-Token (Farben, Abstände,
        Dichte, Stilrichtung) — es findet kein Nachbau des Layouts oder urheberrechtlich
        geschützter Inhalte der Referenz statt.
      </p>
    </div>
  );
}
