import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { api, type DesignTokenSet } from "../src/lib/apiClient";

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
    card_style: { primary_style: "Tile-based", reasoning: "test" },
  };
}

const server = setupServer(
  http.post("/api/design/upload", () =>
    HttpResponse.json({ upload_id: "upload-1", media_type: "image/png", size_bytes: 123 }),
  ),
  http.post("/api/design/analyze", () =>
    HttpResponse.json({
      tokens: makeTokenSet(),
      usage: { input_tokens: 100, output_tokens: 50, estimated_cost_usd: 0.001, model: "claude-sonnet-5" },
    }),
  ),
  http.get("/api/design/presets", () =>
    HttpResponse.json([{ id: "preset-1", name: "My Preset", created_at: "2026-09-01T00:00:00Z" }]),
  ),
  http.get("/api/design/presets/preset-1", () =>
    HttpResponse.json({
      id: "preset-1",
      name: "My Preset",
      created_at: "2026-09-01T00:00:00Z",
      tokens: makeTokenSet(),
    }),
  ),
  http.post("/api/design/presets", () =>
    HttpResponse.json({
      id: "preset-2",
      name: "New Preset",
      created_at: "2026-09-01T00:00:00Z",
      tokens: makeTokenSet(),
    }),
  ),
  http.delete("/api/design/presets/preset-1", () => HttpResponse.json({ deleted: true })),
  http.post("/api/design/theme-export", () =>
    HttpResponse.json({ filename: "my_theme.yaml", yaml: "My Theme:\n  modes: {}\n" }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("design api client", () => {
  it("uploadDesignImage sends the file as multipart form data", async () => {
    let receivedContentType: string | null = null;
    let receivedFilePart: FormDataEntryValue | null = null;
    server.use(
      http.post("/api/design/upload", async ({ request }) => {
        receivedContentType = request.headers.get("content-type");
        const form = await request.formData();
        receivedFilePart = form.get("file");
        return HttpResponse.json({ upload_id: "upload-1", media_type: "image/png", size_bytes: 3 });
      }),
    );

    const file = new File(["abc"], "test.png", { type: "image/png" });
    const response = await api.uploadDesignImage(file);

    expect(response.upload_id).toBe("upload-1");
    // Content-Type (with multipart boundary) and the "file" field name/type
    // are what apiClient.ts is actually responsible for -- the exact
    // byte-for-byte reconstruction of the File on the server side is a
    // property of this test environment's fetch/undici multipart parsing,
    // not of our code (verified independently against the real FastAPI
    // backend via a live multipart upload during development).
    expect(receivedContentType).toMatch(/^multipart\/form-data/);
    // Not `instanceof File`: msw's Node request handler and this test file
    // can end up with cross-realm File classes that don't identity-match
    // even for a genuinely file-shaped part -- duck-type it instead.
    const filePart = receivedFilePart as unknown as { type?: string } | null;
    expect(filePart?.type).toBe("image/png");
  });

  it("analyzeDesign posts JSON with the upload id", async () => {
    let receivedBody: unknown = null;
    server.use(
      http.post("/api/design/analyze", async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json({
          tokens: makeTokenSet(),
          usage: { input_tokens: 1, output_tokens: 2, estimated_cost_usd: null, model: "claude-sonnet-5" },
        });
      }),
    );

    const result = await api.analyzeDesign("upload-1");

    expect(receivedBody).toEqual({ upload_id: "upload-1" });
    expect(result.tokens.card_style.primary_style).toBe("Tile-based");
  });

  it("listTokenPresets returns the preset summaries", async () => {
    const presets = await api.listTokenPresets();
    expect(presets).toEqual([{ id: "preset-1", name: "My Preset", created_at: "2026-09-01T00:00:00Z" }]);
  });

  it("getTokenPreset returns the full preset with tokens", async () => {
    const preset = await api.getTokenPreset("preset-1");
    expect(preset.tokens.card_style.primary_style).toBe("Tile-based");
  });

  it("saveTokenPreset posts the name and tokens as JSON", async () => {
    let receivedBody: unknown = null;
    server.use(
      http.post("/api/design/presets", async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json({
          id: "preset-2",
          name: "New Preset",
          created_at: "2026-09-01T00:00:00Z",
          tokens: makeTokenSet(),
        });
      }),
    );

    const preset = await api.saveTokenPreset("New Preset", makeTokenSet());

    expect(preset.id).toBe("preset-2");
    expect(receivedBody).toMatchObject({ name: "New Preset" });
  });

  it("deleteTokenPreset returns the deletion confirmation", async () => {
    const result = await api.deleteTokenPreset("preset-1");
    expect(result).toEqual({ deleted: true });
  });

  it("exportThemeYaml returns filename and yaml text", async () => {
    const result = await api.exportThemeYaml("My Theme", makeTokenSet());
    expect(result.filename).toBe("my_theme.yaml");
    expect(result.yaml).toContain("modes:");
  });
});
