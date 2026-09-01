import type { GenerationStrategy } from "../../lib/apiClient";

interface StrategyPickerProps {
  value: GenerationStrategy;
  onChange: (value: GenerationStrategy) => void;
}

const OPTIONS: { value: GenerationStrategy; label: string }[] = [
  { value: "by_area", label: "Nach Bereichen" },
  { value: "by_domain", label: "Nach Domains" },
  { value: "automatic", label: "Automatisch" },
];

export function StrategyPicker({ value, onChange }: StrategyPickerProps) {
  return (
    <div className="flex flex-col gap-2 rounded border border-gray-200 bg-white p-3">
      <h3 className="text-sm font-semibold text-gray-800">Struktur der Ansichten</h3>
      <div className="flex flex-col gap-1">
        {OPTIONS.map((option) => (
          <label key={option.value} className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="generation-strategy"
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            {option.label}
          </label>
        ))}
      </div>
    </div>
  );
}
