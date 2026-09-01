import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { api, type GenerateDashboardRequest, type GenerateDashboardResponse } from "../src/lib/apiClient";

function makeResponse(): GenerateDashboardResponse {
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
    usage: {
      input_tokens: 500,
      output_tokens: 200,
      estimated_cost_usd: 0.01,
      model: "claude-sonnet-5",
      call_count: 2,
    },
    notes: [],
  };
}

const server = setupServer(
  http.post("/api/dashboard/generate", () => HttpResponse.json(makeResponse())),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("dashboard api client", () => {
  it("generateDashboard posts the request body as JSON", async () => {
    let receivedBody: unknown = null;
    server.use(
      http.post("/api/dashboard/generate", async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(makeResponse());
      }),
    );

    const body: GenerateDashboardRequest = {
      area_ids: ["living_room"],
      strategy: "by_area",
    };
    const result = await api.generateDashboard(body);

    expect(receivedBody).toEqual(body);
    expect(result.dashboard.views[0]?.title).toBe("Wohnzimmer");
    expect(result.usage.model).toBe("claude-sonnet-5");
  });

  it("generateDashboard returns the yaml and validation report", async () => {
    const result = await api.generateDashboard({ area_ids: ["living_room"], strategy: "automatic" });

    expect(result.yaml).toContain("Wohnzimmer");
    expect(result.validation.removed_cards).toBe(0);
    expect(result.notes).toEqual([]);
  });

  it("generateDashboard surfaces an ApiError on failure responses", async () => {
    server.use(
      http.post("/api/dashboard/generate", () =>
        HttpResponse.json({ detail: "Bitte mindestens einen Bereich auswählen." }, { status: 400 }),
      ),
    );

    await expect(
      api.generateDashboard({ area_ids: [], strategy: "by_area" }),
    ).rejects.toMatchObject({ status: 400 });
  });
});
