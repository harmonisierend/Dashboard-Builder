import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { DashboardPage } from "../src/pages/DashboardPage";
import type { GenerateDashboardResponse } from "../src/lib/apiClient";

function makeRegistryResponse() {
  return {
    fetched_at: "2026-09-01T00:00:00Z",
    entities: [],
    filtered_entities: [],
    areas: [{ area_id: "living_room", name: "Living Room", floor_id: null, labels: [] }],
    floors: [{ floor_id: "ground", name: "Ground Floor", level: 0 }],
    labels: [],
    lovelace_resources: [],
  };
}

function makeGenerateResponse(): GenerateDashboardResponse {
  return {
    dashboard: {
      views: [
        {
          title: "Living Room",
          max_columns: null,
          dense_section_placement: null,
          sections: [
            {
              column_span: null,
              row_span: null,
              cards: [
                {
                  card_type: "tile",
                  custom_type: null,
                  entity: "light.living_room",
                  entities: null,
                  name: null,
                  title: null,
                  heading: null,
                  icon: null,
                  color: null,
                  features: null,
                  hours_to_show: null,
                },
              ],
            },
          ],
        },
      ],
    },
    yaml: "views:\n- title: Living Room\n",
    validation: {
      removed_entity_refs: 0,
      removed_custom_types: 0,
      removed_cards: 0,
      removed_sections: 0,
      removed_views: 0,
      details: [],
    },
    usage: {
      input_tokens: 400,
      output_tokens: 150,
      estimated_cost_usd: 0.008,
      model: "claude-sonnet-5",
      call_count: 2,
    },
    notes: [],
  };
}

const server = setupServer(
  http.get("/api/registry", () => HttpResponse.json(makeRegistryResponse())),
  http.get("/api/design/presets", () => HttpResponse.json([])),
  http.post("/api/dashboard/generate", () => HttpResponse.json(makeGenerateResponse())),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("DashboardPage", () => {
  it("selects a scope, generates a dashboard, and offers a YAML download", async () => {
    const user = userEvent.setup();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    render(<DashboardPage />);

    await user.click(await screen.findByLabelText("Living Room"));
    await user.click(screen.getByRole("button", { name: "Dashboard generieren" }));

    await screen.findByText("Living Room", { selector: "h4" });
    expect(screen.getByText("tile: light.living_room")).toBeInTheDocument();
    expect(
      screen.getByText("Keine Probleme gefunden -- alle Entitäten und Kartentypen sind gültig."),
    ).toBeInTheDocument();
    expect(screen.getByText(/Modell: claude-sonnet-5/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "dashboard.yaml herunterladen" }));
    await waitFor(() => expect(clickSpy).toHaveBeenCalled());

    clickSpy.mockRestore();
  });

  it("disables the generate button until a scope is selected", async () => {
    render(<DashboardPage />);
    await screen.findByLabelText("Living Room");

    expect(screen.getByRole("button", { name: "Dashboard generieren" })).toBeDisabled();
  });

  it("shows an error message when generation fails", async () => {
    server.use(
      http.post("/api/dashboard/generate", () =>
        HttpResponse.json({ detail: "Kein Anthropic-API-Key konfiguriert." }, { status: 424 }),
      ),
    );
    const user = userEvent.setup();
    render(<DashboardPage />);

    await user.click(await screen.findByLabelText("Living Room"));
    await user.click(screen.getByRole("button", { name: "Dashboard generieren" }));

    expect(await screen.findByText("Kein Anthropic-API-Key konfiguriert.")).toBeInTheDocument();
  });
});
