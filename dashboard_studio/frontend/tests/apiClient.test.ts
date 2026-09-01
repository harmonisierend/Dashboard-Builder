import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { api, ApiError } from "../src/lib/apiClient";

const server = setupServer(
  http.get("/api/status", () =>
    HttpResponse.json({
      ha_connected: true,
      ha_connection_source: "supervisor",
      last_registry_refresh: "2026-09-01T00:00:00Z",
      entity_count: 2300,
      area_count: 24,
    }),
  ),
  http.get("/api/registry", () =>
    HttpResponse.json({
      fetched_at: "2026-09-01T00:00:00Z",
      entities: [],
      filtered_entities: [],
      areas: [],
      floors: [],
      labels: [],
      lovelace_resources: [],
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("api client", () => {
  it("getStatus returns the parsed status payload", async () => {
    const status = await api.getStatus();
    expect(status.ha_connected).toBe(true);
    expect(status.entity_count).toBe(2300);
  });

  it("getRegistry returns the parsed registry payload", async () => {
    const registry = await api.getRegistry();
    expect(registry.entities).toEqual([]);
  });

  it("throws ApiError with the server-provided detail on a non-2xx response", async () => {
    server.use(
      http.get("/api/registry", () =>
        HttpResponse.json({ detail: "not connected" }, { status: 503 }),
      ),
    );

    await expect(api.getRegistry()).rejects.toMatchObject(
      new ApiError(503, "not connected"),
    );
  });
});
