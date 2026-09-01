import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { TokenEditor } from "../src/components/design/TokenEditor";
import type { DesignTokenSet } from "../src/lib/apiClient";

function makeTokenSet(): DesignTokenSet {
  const pair = { light: "#111111", dark: "#eeeeee" };
  return {
    schema_version: 1,
    colors: {
      primary: pair,
      accent: pair,
      background: pair,
      surface: pair,
      on_surface: pair,
      state_on: pair,
      state_off: pair,
      warn: pair,
      critical: pair,
    },
    typography: {
      font_family: "Inter, sans-serif",
      sizes: { xs: "12px", sm: "14px", md: "16px", lg: "20px", xl: "24px" },
      weights: { regular: 400, medium: 500, bold: 700 },
    },
    form: {
      border_radius_px: 12,
      shadow: "0 2px 8px rgba(0,0,0,0.15)",
      border_width_px: 1,
      style_family: "flat",
    },
    density: { mode: "comfortable", grid_gap_px: 8, section_spacing_px: 16 },
    card_style: { primary_style: "Tile-based", reasoning: "grid of uniform tiles" },
  };
}

// TokenEditor is a fully controlled component with no internal state of
// its own -- typing a multi-character value only behaves like a real
// controlled input if the harness actually feeds each onChange back in as
// new props (React's controlled-input machinery reverts the DOM to the
// unchanged `value` prop between keystrokes otherwise, so a bare vi.fn()
// onChange only ever "sees" the last keystroke).
function ControlledTokenEditor({
  onChange,
}: {
  onChange: (tokens: DesignTokenSet) => void;
}) {
  const [tokens, setTokens] = useState(makeTokenSet());
  return (
    <TokenEditor
      tokens={tokens}
      onChange={(next) => {
        setTokens(next);
        onChange(next);
      }}
    />
  );
}

describe("TokenEditor", () => {
  it("renders German section labels", () => {
    render(<TokenEditor tokens={makeTokenSet()} onChange={vi.fn()} />);

    expect(screen.getByText("Farben")).toBeInTheDocument();
    expect(screen.getByText("Typografie")).toBeInTheDocument();
    expect(screen.getByText("Form")).toBeInTheDocument();
    expect(screen.getByText("Dichte")).toBeInTheDocument();
    expect(screen.getByText("Kartenstil")).toBeInTheDocument();
  });

  it("renders all nine color pair rows", () => {
    render(<TokenEditor tokens={makeTokenSet()} onChange={vi.fn()} />);

    for (const label of [
      "Primär",
      "Akzent",
      "Hintergrund",
      "Oberfläche",
      "Text auf Oberfläche",
      "Status „An“",
      "Status „Aus“",
      "Warnung",
      "Kritisch",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("editing a color hex field fires onChange with the updated token set", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ControlledTokenEditor onChange={onChange} />);

    const hexInput = screen.getByLabelText("Primär hell (Hex-Wert)");
    await user.clear(hexInput);
    await user.type(hexInput, "#abcdef");

    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls.at(-1)?.[0] as DesignTokenSet;
    expect(lastCall.colors.primary.light).toBe("#abcdef");
    // unrelated fields are untouched
    expect(lastCall.colors.accent).toEqual(makeTokenSet().colors.accent);
  });

  it("editing the card-style text input fires onChange", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ControlledTokenEditor onChange={onChange} />);

    const input = screen.getByDisplayValue("Tile-based");
    await user.clear(input);
    await user.type(input, "Custom Style");

    const lastCall = onChange.mock.calls.at(-1)?.[0] as DesignTokenSet;
    expect(lastCall.card_style.primary_style).toBe("Custom Style");
  });

  it("changing the style-family select fires onChange", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TokenEditor tokens={makeTokenSet()} onChange={onChange} />);

    await user.selectOptions(screen.getByDisplayValue("Flat"), "glass");

    const lastCall = onChange.mock.calls.at(-1)?.[0] as DesignTokenSet;
    expect(lastCall.form.style_family).toBe("glass");
  });
});
