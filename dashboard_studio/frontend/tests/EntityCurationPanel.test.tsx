import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import {
  EntityCurationPanel,
  curatedViewsFromState,
  seedCurationState,
  type CurationState,
} from "../src/components/dashboard/EntityCurationPanel";
import type { ProposedView } from "../src/lib/apiClient";

function makeProposedViews(): ProposedView[] {
  return [
    {
      name: "Wohnzimmer",
      candidates: [
        { entity_id: "light.a", domain: "light", name: "Licht A", area_name: "Wohnzimmer", device_class: null },
        { entity_id: "light.b", domain: "light", name: "Licht B", area_name: "Wohnzimmer", device_class: null },
      ],
    },
    {
      name: "Küche",
      candidates: [
        { entity_id: "switch.c", domain: "switch", name: "Schalter C", area_name: "Küche", device_class: null },
      ],
    },
  ];
}

function ControlledPanel({ proposedViews }: { proposedViews: ProposedView[] }) {
  const [state, setState] = useState<CurationState>(() => seedCurationState(proposedViews));
  return <EntityCurationPanel proposedViews={proposedViews} value={state} onChange={setState} />;
}

describe("EntityCurationPanel", () => {
  it("renders every proposed view and candidate fully checked by default", () => {
    const proposedViews = makeProposedViews();
    render(<ControlledPanel proposedViews={proposedViews} />);

    expect(screen.getByLabelText("Wohnzimmer")).toBeChecked();
    expect(screen.getByLabelText("Küche")).toBeChecked();
    expect(screen.getByLabelText(/Licht A/)).toBeChecked();
    expect(screen.getByLabelText(/Licht B/)).toBeChecked();
    expect(screen.getByLabelText(/Schalter C/)).toBeChecked();
  });

  it("unchecking an entity unchecks it in the DOM", async () => {
    const user = userEvent.setup();
    const proposedViews = makeProposedViews();
    render(<ControlledPanel proposedViews={proposedViews} />);

    await user.click(screen.getByLabelText(/Licht A/));

    expect(screen.getByLabelText(/Licht A/)).not.toBeChecked();
    expect(screen.getByLabelText(/Licht B/)).toBeChecked();
  });

  it("unchecking 'Ansicht behalten' unchecks the view and disables its entities", async () => {
    const user = userEvent.setup();
    const proposedViews = makeProposedViews();
    render(<ControlledPanel proposedViews={proposedViews} />);

    await user.click(screen.getByLabelText("Küche"));

    expect(screen.getByLabelText("Küche")).not.toBeChecked();
    expect(screen.getByLabelText(/Schalter C/)).toBeDisabled();
  });

  it("'Alle auswählen' / 'Keine auswählen' select or clear every candidate in a view", async () => {
    const user = userEvent.setup();
    const proposedViews = makeProposedViews();
    render(<ControlledPanel proposedViews={proposedViews} />);

    await user.click(screen.getByLabelText(/Licht A/));
    await user.click(screen.getByLabelText(/Licht B/));
    expect(screen.getByLabelText(/Licht A/)).not.toBeChecked();
    expect(screen.getByLabelText(/Licht B/)).not.toBeChecked();

    const wohnzimmerCard = screen.getByLabelText("Wohnzimmer").closest("div.rounded") as HTMLElement;
    await user.click(within(wohnzimmerCard).getByText("Alle auswählen"));
    expect(screen.getByLabelText(/Licht A/)).toBeChecked();
    expect(screen.getByLabelText(/Licht B/)).toBeChecked();
  });
});

describe("seedCurationState / curatedViewsFromState (pure)", () => {
  it("seeds every view included and every candidate selected", () => {
    const proposedViews = makeProposedViews();
    const state = seedCurationState(proposedViews);

    expect(state.Wohnzimmer?.included).toBe(true);
    expect(state.Wohnzimmer?.selectedEntityIds.has("light.a")).toBe(true);
    expect(state.Wohnzimmer?.selectedEntityIds.has("light.b")).toBe(true);
    expect(state.Küche?.selectedEntityIds.has("switch.c")).toBe(true);
  });

  it("drops an unchecked entity from its view's curated candidates", () => {
    const proposedViews = makeProposedViews();
    const state = seedCurationState(proposedViews);
    state.Wohnzimmer?.selectedEntityIds.delete("light.a");

    const curated = curatedViewsFromState(proposedViews, state);
    const wohnzimmer = curated.find((v) => v.name === "Wohnzimmer");
    expect(wohnzimmer?.candidates.map((c) => c.entity_id)).toEqual(["light.b"]);
  });

  it("drops a view entirely when it is not included", () => {
    const proposedViews = makeProposedViews();
    const state = seedCurationState(proposedViews);
    state.Küche!.included = false;

    const curated = curatedViewsFromState(proposedViews, state);
    expect(curated.map((v) => v.name)).toEqual(["Wohnzimmer"]);
  });
});
