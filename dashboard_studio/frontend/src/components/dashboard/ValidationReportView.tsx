import type { ValidationReportResponse } from "../../lib/apiClient";

interface ValidationReportViewProps {
  validation: ValidationReportResponse;
}

export function ValidationReportView({ validation }: ValidationReportViewProps) {
  const totalRemovals =
    validation.removed_entity_refs +
    validation.removed_custom_types +
    validation.removed_cards +
    validation.removed_sections +
    validation.removed_views;

  return (
    <div className="flex flex-col gap-2 rounded border border-gray-200 bg-white p-3">
      <h3 className="text-sm font-semibold text-gray-800">Validierung</h3>
      {totalRemovals === 0 ? (
        <p className="text-sm text-green-700">
          Keine Probleme gefunden -- alle Entitäten und Kartentypen sind gültig.
        </p>
      ) : (
        <>
          <ul className="text-sm text-gray-700">
            <li>Entfernte Entitätsreferenzen: {validation.removed_entity_refs}</li>
            <li>Nicht verfügbare Kartentypen (auf native Karten zurückgesetzt): {validation.removed_custom_types}</li>
            <li>Entfernte Karten: {validation.removed_cards}</li>
            <li>Entfernte Sections: {validation.removed_sections}</li>
            <li>Entfernte Ansichten: {validation.removed_views}</li>
          </ul>
          {validation.details.length > 0 && (
            <ul className="flex flex-col gap-0.5 text-xs text-gray-500">
              {validation.details.map((detail) => (
                <li key={detail}>{detail}</li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
