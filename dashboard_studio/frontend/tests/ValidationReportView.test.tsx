import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ValidationReportView } from "../src/components/dashboard/ValidationReportView";
import type { ValidationReportResponse } from "../src/lib/apiClient";

describe("ValidationReportView", () => {
  it("shows a quiet 'no problems' state when all counts are zero", () => {
    const validation: ValidationReportResponse = {
      removed_entity_refs: 0,
      removed_custom_types: 0,
      removed_cards: 0,
      removed_sections: 0,
      removed_views: 0,
      details: [],
    };

    render(<ValidationReportView validation={validation} />);

    expect(
      screen.getByText("Keine Probleme gefunden -- alle Entitäten und Kartentypen sind gültig."),
    ).toBeInTheDocument();
  });

  it("shows removal counts and details when something was removed", () => {
    const validation: ValidationReportResponse = {
      removed_entity_refs: 2,
      removed_custom_types: 1,
      removed_cards: 1,
      removed_sections: 0,
      removed_views: 0,
      details: ["Karte in Ansicht 'V' entfernt: Entität 'light.ghost' nicht im Registry-Snapshot."],
    };

    render(<ValidationReportView validation={validation} />);

    expect(screen.getByText("Entfernte Entitätsreferenzen: 2")).toBeInTheDocument();
    expect(screen.getByText("Entfernte Karten: 1")).toBeInTheDocument();
    expect(
      screen.getByText("Karte in Ansicht 'V' entfernt: Entität 'light.ghost' nicht im Registry-Snapshot."),
    ).toBeInTheDocument();
  });
});
