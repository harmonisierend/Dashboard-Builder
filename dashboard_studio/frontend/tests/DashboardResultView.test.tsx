import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DashboardResultView } from "../src/components/dashboard/DashboardResultView";
import type { GeneratedDashboard } from "../src/lib/apiClient";

function emptyCard(overrides: Partial<GeneratedDashboard["views"][number]["sections"][number]["cards"][number]>) {
  return {
    card_type: "tile" as const,
    custom_type: null,
    entity: null,
    entities: null,
    name: null,
    title: null,
    heading: null,
    icon: null,
    color: null,
    features: null,
    hours_to_show: null,
    ...overrides,
  };
}

describe("DashboardResultView", () => {
  it("shows a placeholder when there are no views", () => {
    render(<DashboardResultView dashboard={{ views: [] }} />);
    expect(screen.getByText("Keine Ansichten generiert.")).toBeInTheDocument();
  });

  it("renders view titles and card labels", () => {
    const dashboard: GeneratedDashboard = {
      views: [
        {
          title: "Wohnzimmer",
          max_columns: null,
          dense_section_placement: null,
          sections: [
            {
              column_span: null,
              row_span: null,
              cards: [emptyCard({ entity: "light.living_room" })],
            },
          ],
        },
      ],
    };

    render(<DashboardResultView dashboard={dashboard} />);

    expect(screen.getByText("Wohnzimmer")).toBeInTheDocument();
    expect(screen.getByText("tile: light.living_room")).toBeInTheDocument();
  });

  it("prefers custom_type over card_type in the label", () => {
    const dashboard: GeneratedDashboard = {
      views: [
        {
          title: "V",
          max_columns: null,
          dense_section_placement: null,
          sections: [
            {
              column_span: null,
              row_span: null,
              cards: [
                emptyCard({ entity: "light.a", custom_type: "custom:mushroom-light-card" }),
              ],
            },
          ],
        },
      ],
    };

    render(<DashboardResultView dashboard={dashboard} />);

    expect(screen.getByText("custom:mushroom-light-card: light.a")).toBeInTheDocument();
  });
});
