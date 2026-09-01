import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { DashboardPage } from "../src/pages/DashboardPage";
import type { GenerateDashboardResponse, ProposeStructureResponse } from "../src/lib/apiClient";

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

function makeProposeResponse(): ProposeStructureResponse {
  return {
    proposed_views: [
      {
        name: "Living Room",
        candidates: [
          {
            entity_id: "light.living_room",
            domain: "light",
            name: "Living Room Light",
            area_name: "Living Room",
            device_class: null,
          },
          {
            entity_id: "light.living_room_lamp",
            domain: "light",
            name: "Living Room Lamp",
            area_name: "Living Room",
            device_class: null,
          },
        ],
      },
    ],
    available_custom_cards: {},
    style_hint: null,
    usage: {
      input_tokens: 300,
      output_tokens: 100,
      estimated_cost_usd: 0.008,
      model: "claude-sonnet-5",
      call_count: 1,
    },
    notes: [],
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
      estimated_cost_usd: 0.016,
      model: "claude-sonnet-5",
      call_count: 2,
    },
    notes: [],
  };
}

const server = setupServer(
  http.get("/api/registry", () => HttpResponse.json(makeRegistryResponse())),
  http.get("/api/design/presets", () => HttpResponse.json([])),
  http.post("/api/dashboard/propose-structure", () => HttpResponse.json(makeProposeResponse())),
  http.post("/api/dashboard/generate", () => HttpResponse.json(makeGenerateResponse())),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("DashboardPage", () => {
  it("proposes a structure, curates entities, generates, and offers a YAML download", async () => {
    const user = userEvent.setup();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    let receivedGenerateBody: { curated_views: { name: string; candidates: { entity_id: string }[] }[] } | null =
      null;
    server.use(
      http.post("/api/dashboard/generate", async ({ request }) => {
        receivedGenerateBody = (await request.json()) as typeof receivedGenerateBody;
        return HttpResponse.json(makeGenerateResponse());
      }),
    );

    render(<DashboardPage />);

    await user.click(await screen.findByLabelText("Living Room"));
    await user.click(screen.getByRole("button", { name: "Struktur vorschlagen" }));

    // Curation panel appears, fully checked by default.
    await screen.findByText("Entitäten kuratieren");
    expect(screen.getByLabelText(/Living Room Light/)).toBeChecked();
    expect(screen.getByLabelText(/Living Room Lamp/)).toBeChecked();

    // Uncheck one entity before generating.
    await user.click(screen.getByLabelText(/Living Room Lamp/));

    await user.click(screen.getByRole("button", { name: "Dashboard generieren" }));

    await screen.findByText("Living Room", { selector: "h4" });
    expect(screen.getByText("tile: light.living_room")).toBeInTheDocument();
    expect(
      screen.getByText("Keine Probleme gefunden -- alle Entitäten und Kartentypen sind gültig."),
    ).toBeInTheDocument();
    // Both the curation step's phase-1 usage line and the result step's
    // combined usage line show "Modell: claude-sonnet-5" -- the combined
    // total (550 tokens) is the one unique to the final result.
    expect(screen.getByText(/550 Tokens/)).toBeInTheDocument();

    expect(receivedGenerateBody).not.toBeNull();
    const sent = receivedGenerateBody!.curated_views[0]!.candidates.map((c) => c.entity_id);
    expect(sent).toEqual(["light.living_room"]);

    await user.click(screen.getByRole("button", { name: "dashboard.yaml herunterladen" }));
    await waitFor(() => expect(clickSpy).toHaveBeenCalled());

    clickSpy.mockRestore();
  });

  it("disables the propose button until a scope is selected", async () => {
    render(<DashboardPage />);
    await screen.findByLabelText("Living Room");

    expect(screen.getByRole("button", { name: "Struktur vorschlagen" })).toBeDisabled();
  });

  it("shows an error message when the structure proposal fails", async () => {
    server.use(
      http.post("/api/dashboard/propose-structure", () =>
        HttpResponse.json({ detail: "Kein Anthropic-API-Key konfiguriert." }, { status: 424 }),
      ),
    );
    const user = userEvent.setup();
    render(<DashboardPage />);

    await user.click(await screen.findByLabelText("Living Room"));
    await user.click(screen.getByRole("button", { name: "Struktur vorschlagen" }));

    expect(await screen.findByText("Kein Anthropic-API-Key konfiguriert.")).toBeInTheDocument();
  });

  it("'Zurück' returns to the scope step and clears the proposal", async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);

    await user.click(await screen.findByLabelText("Living Room"));
    await user.click(screen.getByRole("button", { name: "Struktur vorschlagen" }));
    await screen.findByText("Entitäten kuratieren");

    await user.click(screen.getByRole("button", { name: "Zurück" }));

    expect(screen.getByRole("button", { name: "Struktur vorschlagen" })).toBeInTheDocument();
    expect(screen.queryByText("Entitäten kuratieren")).not.toBeInTheDocument();
  });
});
