import type { CardConfig, GeneratedDashboard } from "../../lib/apiClient";

interface DashboardResultViewProps {
  dashboard: GeneratedDashboard;
}

function cardLabel(card: CardConfig): string {
  const type = card.custom_type ?? card.card_type;
  const label = card.name ?? card.title ?? card.heading ?? card.entity ?? card.entities?.join(", ");
  return label ? `${type}: ${label}` : type;
}

// Read-only nested rendering of the generated structure -- not a visual
// Lovelace preview (that's M5), just enough for the user to review what
// was proposed before downloading the YAML.
export function DashboardResultView({ dashboard }: DashboardResultViewProps) {
  if (dashboard.views.length === 0) {
    return <p className="text-sm text-gray-500">Keine Ansichten generiert.</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      {dashboard.views.map((view) => (
        <div key={view.title} className="rounded border border-gray-200 bg-white p-3">
          <h4 className="text-sm font-semibold text-gray-800">{view.title}</h4>
          <div className="mt-2 flex flex-col gap-2">
            {view.sections.map((section, sectionIndex) => (
              <div key={sectionIndex} className="rounded border border-gray-100 bg-gray-50 p-2">
                <ul className="flex flex-col gap-1 text-xs text-gray-700">
                  {section.cards.map((card, cardIndex) => (
                    <li key={cardIndex}>{cardLabel(card)}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
