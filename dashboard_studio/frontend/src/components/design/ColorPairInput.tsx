import type { ColorPair } from "../../lib/apiClient";

interface ColorPairInputProps {
  label: string;
  value: ColorPair;
  onChange: (value: ColorPair) => void;
}

function OneColorInput({
  value,
  onChange,
  ariaLabel,
}: {
  value: string;
  onChange: (value: string) => void;
  ariaLabel: string;
}) {
  return (
    <div className="flex items-center gap-1">
      <input
        type="color"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label={ariaLabel}
        className="h-7 w-7 cursor-pointer rounded border border-gray-300"
      />
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label={`${ariaLabel} (Hex-Wert)`}
        className="w-20 rounded border border-gray-300 px-1.5 py-1 font-mono text-xs"
      />
    </div>
  );
}

export function ColorPairInput({ label, value, onChange }: ColorPairInputProps) {
  return (
    <div className="flex items-center justify-between gap-4 py-1">
      <span className="text-sm text-gray-700">{label}</span>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-gray-400">Hell</span>
          <OneColorInput
            value={value.light}
            onChange={(light) => onChange({ ...value, light })}
            ariaLabel={`${label} hell`}
          />
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-gray-400">Dunkel</span>
          <OneColorInput
            value={value.dark}
            onChange={(dark) => onChange({ ...value, dark })}
            ariaLabel={`${label} dunkel`}
          />
        </div>
      </div>
    </div>
  );
}
