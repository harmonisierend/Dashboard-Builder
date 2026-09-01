import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { DesignPage } from "../src/pages/DesignPage";
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
      font_family: "Inter",
      sizes: { xs: "12px", sm: "14px", md: "16px", lg: "20px", xl: "24px" },
      weights: { regular: 400, medium: 500, bold: 700 },
    },
    form: { border_radius_px: 8, shadow: "none", border_width_px: 1, style_family: "flat" },
    density: { mode: "comfortable", grid_gap_px: 8, section_spacing_px: 16 },
    card_style: { primary_style: "Tile-based", reasoning: "grid of uniform tiles" },
  };
}

const server = setupServer(
  http.post("/api/design/upload", () =>
    HttpResponse.json({ upload_id: "upload-1", media_type: "image/png", size_bytes: 3 }),
  ),
  http.post("/api/design/analyze", () =>
    HttpResponse.json({
      tokens: makeTokenSet(),
      usage: { input_tokens: 100, output_tokens: 50, estimated_cost_usd: 0.0012, model: "claude-sonnet-5" },
    }),
  ),
  http.get("/api/design/presets", () => HttpResponse.json([])),
  http.post("/api/design/theme-export", () =>
    HttpResponse.json({ filename: "my_theme.yaml", yaml: "Mein Theme:\n  modes: {}\n" }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function getFileInput(): HTMLInputElement {
  return document.querySelector('input[type="file"]') as HTMLInputElement;
}

describe("DesignPage", () => {
  it("uploads, analyzes, shows the token editor, and exports a theme YAML download", async () => {
    const user = userEvent.setup();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    render(<DesignPage />);

    const file = new File(["fake-png-bytes"], "test.png", { type: "image/png" });
    await user.upload(getFileInput(), file);

    // preview appears
    await screen.findByAltText("Vorschau der hochgeladenen Design-Referenz");

    // analysis completes and the token editor renders
    await screen.findByText("Farben");
    expect(screen.getByText(/Modell: claude-sonnet-5/)).toBeInTheDocument();

    // export the theme
    await user.click(screen.getByRole("button", { name: "themes.yaml exportieren" }));

    await waitFor(() => expect(clickSpy).toHaveBeenCalled());

    clickSpy.mockRestore();
  });

  it("shows an error message when analysis fails", async () => {
    server.use(
      http.post("/api/design/analyze", () =>
        HttpResponse.json({ detail: "Kein Anthropic-API-Key konfiguriert." }, { status: 424 }),
      ),
    );
    const user = userEvent.setup();
    render(<DesignPage />);

    const file = new File(["fake-png-bytes"], "test.png", { type: "image/png" });
    await user.upload(getFileInput(), file);

    expect(await screen.findByText("Kein Anthropic-API-Key konfiguriert.")).toBeInTheDocument();
  });
});
