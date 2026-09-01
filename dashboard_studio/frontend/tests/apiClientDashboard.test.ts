import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  api,
  type DashboardScopeRequest,
  type DashboardUsageInfo,
  type GenerateDashboardRequest,
  type GenerateDashboardResponse,
  type ProposeStructureResponse,
} from "../src/lib/apiClient";

function makeUsage(callCount = 1): DashboardUsageInfo {
  return {
    input_tokens: 300,
    output_tokens: 100,
    estimated_cost_usd: 0.01,
    model: "claude-sonnet-5",
    call_count: callCount,
  };
}

function makeProposeResponse(): ProposeStructureResponse {
  return {
    proposed_views: [
      {
        name: "Wohnzimmer",
        candidates: [
          {
            entity_id: "light.living_room",
            domain: "light",
            name: "Wohnzimmerlicht",
            area_name: "Wohnzimmer",
            device_class: null,
          },
        ],
      },
    ],
    available_custom_cards: {},
    style_hint: null,
    usage: makeUsage(1),
    notes: [],
  };
}

function makeGenerateResponse(): GenerateDashboardResponse {
  return {
    dashboard: {
      views: [
        {
          title: "Wohnzimmer",
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
    yaml: "views:\n- title: Wohnzimmer\n",
    validation: {
      removed_entity_refs: 0,
      removed_custom_types: 0,
      removed_cards: 0,
      removed_sections: 0,
      removed_views: 0,
      details: [],
    },
    usage: makeUsage(2),
    notes: [],
  };
}

const server = setupServer(
  http.post("/api/dashboard/propose-structure", () => HttpResponse.json(makeProposeResponse())),
  http.post("/api/dashboard/generate", () => HttpResponse.json(makeGenerateResponse())),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("dashboard api client", () => {
  it("proposeDashboardStructure posts the scope request and returns proposed views", async () => {
    let receivedBody: unknown = null;
    server.use(
      http.post("/api/dashboard/propose-structure", async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(makeProposeResponse());
      }),
    );

    const body: DashboardScopeRequest = { area_ids: ["living_room"], strategy: "by_area" };
    const result = await api.proposeDashboardStructure(body);

    expect(receivedBody).toEqual(body);
    expect(result.proposed_views[0]?.name).toBe("Wohnzimmer");
    expect(result.proposed_views[0]?.candidates[0]?.entity_id).toBe("light.living_room");
    expect(result.usage.call_count).toBe(1);
  });

  it("proposeDashboardStructure surfaces an ApiError on failure responses", async () => {
    server.use(
      http.post("/api/dashboard/propose-structure", () =>
        HttpResponse.json({ detail: "Bitte mindestens einen Bereich auswählen." }, { status: 400 }),
      ),
    );

    await expect(
      api.proposeDashboardStructure({ area_ids: [], strategy: "by_area" }),
    ).rejects.toMatchObject({ status: 400 });
  });

  it("generateDashboard posts the curated request body as JSON", async () => {
    let receivedBody: unknown = null;
    server.use(
      http.post("/api/dashboard/generate", async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(makeGenerateResponse());
      }),
    );

    const body: GenerateDashboardRequest = {
      area_ids: ["living_room"],
      curated_views: [
        {
          name: "Wohnzimmer",
          candidates: [
            {
              entity_id: "light.living_room",
              domain: "light",
              name: "Wohnzimmerlicht",
              area_name: "Wohnzimmer",
              device_class: null,
            },
          ],
        },
      ],
      available_custom_cards: {},
      phase1_usage: makeUsage(1),
    };
    const result = await api.generateDashboard(body);

    expect(receivedBody).toEqual(body);
    expect(result.dashboard.views[0]?.title).toBe("Wohnzimmer");
    expect(result.usage.model).toBe("claude-sonnet-5");
  });

  it("generateDashboard returns the yaml and validation report", async () => {
    const result = await api.generateDashboard({
      area_ids: ["living_room"],
      curated_views: [{ name: "Wohnzimmer", candidates: [] }],
      available_custom_cards: {},
      phase1_usage: makeUsage(1),
    });

    expect(result.yaml).toContain("Wohnzimmer");
    expect(result.validation.removed_cards).toBe(0);
    expect(result.notes).toEqual([]);
  });

  it("generateDashboard surfaces an ApiError on failure responses", async () => {
    server.use(
      http.post("/api/dashboard/generate", () =>
        HttpResponse.json({ detail: "Bitte mindestens eine Ansicht behalten." }, { status: 400 }),
      ),
    );

    await expect(
      api.generateDashboard({
        area_ids: ["living_room"],
        curated_views: [],
        available_custom_cards: {},
        phase1_usage: makeUsage(1),
      }),
    ).rejects.toMatchObject({ status: 400 });
  });
});
