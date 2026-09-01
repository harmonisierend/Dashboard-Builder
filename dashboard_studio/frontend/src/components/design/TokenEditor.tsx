import type { ReactNode } from "react";
import type {
  ColorPair,
  DensityMode,
  DesignTokenSet,
  StyleFamily,
} from "../../lib/apiClient";
import { ColorPairInput } from "./ColorPairInput";

interface TokenEditorProps {
  tokens: DesignTokenSet;
  onChange: (tokens: DesignTokenSet) => void;
}

const COLOR_LABELS: { key: keyof DesignTokenSet["colors"]; label: string }[] = [
  { key: "primary", label: "Primär" },
  { key: "accent", label: "Akzent" },
  { key: "background", label: "Hintergrund" },
  { key: "surface", label: "Oberfläche" },
  { key: "on_surface", label: "Text auf Oberfläche" },
  { key: "state_on", label: "Status „An“" },
  { key: "state_off", label: "Status „Aus“" },
  { key: "warn", label: "Warnung" },
  { key: "critical", label: "Kritisch" },
];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded border border-gray-200 bg-white p-3">
      <h3 className="mb-2 text-sm font-semibold text-gray-800">{title}</h3>
      {children}
    </section>
  );
}

export function TokenEditor({ tokens, onChange }: TokenEditorProps) {
  function setColor(key: keyof DesignTokenSet["colors"], value: ColorPair) {
    onChange({ ...tokens, colors: { ...tokens.colors, [key]: value } });
  }

  return (
    <div className="flex flex-col gap-4">
      <Section title="Farben">
        <div className="flex flex-col divide-y divide-gray-100">
          {COLOR_LABELS.map(({ key, label }) => (
            <ColorPairInput
              key={key}
              label={label}
              value={tokens.colors[key]}
              onChange={(value) => setColor(key, value)}
            />
          ))}
        </div>
      </Section>

      <Section title="Typografie">
        <div className="flex flex-col gap-2">
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            Schriftart
            <input
              type="text"
              value={tokens.typography.font_family}
              onChange={(event) =>
                onChange({
                  ...tokens,
                  typography: { ...tokens.typography, font_family: event.target.value },
                })
              }
              className="rounded border border-gray-300 px-2 py-1 text-sm"
            />
          </label>
          <div className="grid grid-cols-5 gap-2">
            {(["xs", "sm", "md", "lg", "xl"] as const).map((size) => (
              <label key={size} className="flex flex-col gap-1 text-xs text-gray-600">
                {size}
                <input
                  type="text"
                  value={tokens.typography.sizes[size]}
                  onChange={(event) =>
                    onChange({
                      ...tokens,
                      typography: {
                        ...tokens.typography,
                        sizes: { ...tokens.typography.sizes, [size]: event.target.value },
                      },
                    })
                  }
                  className="rounded border border-gray-300 px-1.5 py-1 text-xs"
                />
              </label>
            ))}
          </div>
          <div className="grid grid-cols-3 gap-2">
            {(["regular", "medium", "bold"] as const).map((weight) => (
              <label key={weight} className="flex flex-col gap-1 text-xs text-gray-600">
                {weight}
                <input
                  type="number"
                  value={tokens.typography.weights[weight]}
                  onChange={(event) =>
                    onChange({
                      ...tokens,
                      typography: {
                        ...tokens.typography,
                        weights: {
                          ...tokens.typography.weights,
                          [weight]: Number(event.target.value),
                        },
                      },
                    })
                  }
                  className="rounded border border-gray-300 px-1.5 py-1 text-xs"
                />
              </label>
            ))}
          </div>
        </div>
      </Section>

      <Section title="Form">
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            Eckenradius: {tokens.form.border_radius_px}px
            <input
              type="range"
              min={0}
              max={32}
              value={tokens.form.border_radius_px}
              onChange={(event) =>
                onChange({
                  ...tokens,
                  form: { ...tokens.form, border_radius_px: Number(event.target.value) },
                })
              }
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            Randstärke: {tokens.form.border_width_px}px
            <input
              type="range"
              min={0}
              max={8}
              value={tokens.form.border_width_px}
              onChange={(event) =>
                onChange({
                  ...tokens,
                  form: { ...tokens.form, border_width_px: Number(event.target.value) },
                })
              }
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            Schatten (CSS box-shadow)
            <input
              type="text"
              value={tokens.form.shadow}
              onChange={(event) =>
                onChange({ ...tokens, form: { ...tokens.form, shadow: event.target.value } })
              }
              className="rounded border border-gray-300 px-2 py-1 font-mono text-xs"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            Stilrichtung
            <select
              value={tokens.form.style_family}
              onChange={(event) =>
                onChange({
                  ...tokens,
                  form: { ...tokens.form, style_family: event.target.value as StyleFamily },
                })
              }
              className="rounded border border-gray-300 px-2 py-1 text-sm"
            >
              <option value="flat">Flat</option>
              <option value="glass">Glas</option>
              <option value="neumorphic">Neumorph</option>
            </select>
          </label>
        </div>
      </Section>

      <Section title="Dichte">
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            Modus
            <select
              value={tokens.density.mode}
              onChange={(event) =>
                onChange({
                  ...tokens,
                  density: { ...tokens.density, mode: event.target.value as DensityMode },
                })
              }
              className="rounded border border-gray-300 px-2 py-1 text-sm"
            >
              <option value="comfortable">Komfortabel</option>
              <option value="compact">Kompakt</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            Grid-Abstand: {tokens.density.grid_gap_px}px
            <input
              type="range"
              min={0}
              max={32}
              value={tokens.density.grid_gap_px}
              onChange={(event) =>
                onChange({
                  ...tokens,
                  density: { ...tokens.density, grid_gap_px: Number(event.target.value) },
                })
              }
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            Abschnittsabstand: {tokens.density.section_spacing_px}px
            <input
              type="range"
              min={0}
              max={64}
              value={tokens.density.section_spacing_px}
              onChange={(event) =>
                onChange({
                  ...tokens,
                  density: {
                    ...tokens.density,
                    section_spacing_px: Number(event.target.value),
                  },
                })
              }
            />
          </label>
        </div>
      </Section>

      <Section title="Kartenstil">
        <div className="flex flex-col gap-2">
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            Klassifikation
            <input
              type="text"
              value={tokens.card_style.primary_style}
              onChange={(event) =>
                onChange({
                  ...tokens,
                  card_style: { ...tokens.card_style, primary_style: event.target.value },
                })
              }
              className="rounded border border-gray-300 px-2 py-1 text-sm"
            />
          </label>
          <p className="text-xs text-gray-500" title={tokens.card_style.reasoning}>
            Begründung: {tokens.card_style.reasoning}
          </p>
        </div>
      </Section>
    </div>
  );
}
