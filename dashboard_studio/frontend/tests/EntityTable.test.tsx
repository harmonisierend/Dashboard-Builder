import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { EntityTable } from "../src/components/registry/EntityTable";
import type { EntityRecord } from "../src/lib/apiClient";

function makeEntity(overrides: Partial<EntityRecord> = {}): EntityRecord {
  return {
    entity_id: "light.test",
    domain: "light",
    name: "Test Light",
    platform: "demo",
    device_id: null,
    device_name: null,
    area_id: null,
    area_name: "Wohnzimmer",
    floor_id: null,
    floor_name: "EG",
    labels: [],
    entity_category: null,
    hidden_by: null,
    disabled_by: null,
    state: "on",
    available: true,
    attributes: {},
    ...overrides,
  };
}

function makeFixture(): EntityRecord[] {
  const entities: EntityRecord[] = [];
  for (let i = 0; i < 50; i += 1) {
    entities.push(
      makeEntity({
        entity_id: `light.lamp_${i}`,
        name: `Lampe ${i}`,
        area_name: i % 2 === 0 ? "Wohnzimmer" : "Küche",
        domain: "light",
      }),
    );
  }
  entities.push(
    makeEntity({
      entity_id: "switch.socket_1",
      name: "Steckdose",
      domain: "switch",
      area_name: "Küche",
    }),
  );
  return entities;
}

describe("EntityTable", () => {
  it("shows the full entity count in the select-all button initially", () => {
    render(<EntityTable entities={makeFixture()} />);
    expect(
      screen.getByRole("button", { name: /Alle sichtbaren auswählen \(51\)/ }),
    ).toBeInTheDocument();
  });

  it("filters by search text", async () => {
    const user = userEvent.setup();
    render(<EntityTable entities={makeFixture()} />);

    await user.type(screen.getByPlaceholderText("Suche nach Entity-ID oder Name…"), "Steckdose");

    expect(
      screen.getByRole("button", { name: /Alle sichtbaren auswählen \(1\)/ }),
    ).toBeInTheDocument();
  });

  it("filters by area", async () => {
    const user = userEvent.setup();
    render(<EntityTable entities={makeFixture()} />);

    await user.selectOptions(screen.getByLabelText("Nach Bereich filtern"), "Küche");

    // 25 lamps at odd indices + the one switch = 26
    expect(
      screen.getByRole("button", { name: /Alle sichtbaren auswählen \(26\)/ }),
    ).toBeInTheDocument();
  });

  it("filters by domain", async () => {
    const user = userEvent.setup();
    render(<EntityTable entities={makeFixture()} />);

    await user.selectOptions(screen.getByLabelText("Nach Domain filtern"), "switch");

    expect(
      screen.getByRole("button", { name: /Alle sichtbaren auswählen \(1\)/ }),
    ).toBeInTheDocument();
  });

  it("select-all-visible sets the selected count, and clear resets it", async () => {
    const user = userEvent.setup();
    render(<EntityTable entities={makeFixture()} />);

    await user.click(screen.getByRole("button", { name: /Alle sichtbaren auswählen/ }));
    expect(screen.getByText("51 ausgewählt")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Auswahl aufheben" }));
    expect(screen.getByText("0 ausgewählt")).toBeInTheDocument();
  });

  it("renders virtualized rows into the DOM", () => {
    render(<EntityTable entities={makeFixture()} />);
    const scrollContainer = screen.getByTestId("entity-table-scroll");
    expect(within(scrollContainer).getAllByRole("checkbox").length).toBeGreaterThan(0);
  });
});
