import type { AreaRegistryEntry, FloorRegistryEntry } from "../../lib/apiClient";

interface ScopeSelectorProps {
  areas: AreaRegistryEntry[];
  floors: FloorRegistryEntry[];
  selectedAreaIds: string[];
  selectedFloorIds: string[];
  onChange: (areaIds: string[], floorIds: string[]) => void;
}

export function ScopeSelector({
  areas,
  floors,
  selectedAreaIds,
  selectedFloorIds,
  onChange,
}: ScopeSelectorProps) {
  function toggleArea(areaId: string) {
    const next = selectedAreaIds.includes(areaId)
      ? selectedAreaIds.filter((id) => id !== areaId)
      : [...selectedAreaIds, areaId];
    onChange(next, selectedFloorIds);
  }

  function toggleFloor(floorId: string) {
    const next = selectedFloorIds.includes(floorId)
      ? selectedFloorIds.filter((id) => id !== floorId)
      : [...selectedFloorIds, floorId];
    onChange(selectedAreaIds, next);
  }

  return (
    <div className="flex flex-col gap-3 rounded border border-gray-200 bg-white p-3">
      <h3 className="text-sm font-semibold text-gray-800">Bereich auswählen</h3>

      <div>
        <p className="mb-1 text-xs font-medium text-gray-500">Bereiche</p>
        {areas.length === 0 ? (
          <p className="text-xs text-gray-400">Keine Bereiche gefunden.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {areas.map((area) => (
              <li key={area.area_id}>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selectedAreaIds.includes(area.area_id)}
                    onChange={() => toggleArea(area.area_id)}
                  />
                  {area.name}
                </label>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <p className="mb-1 text-xs font-medium text-gray-500">Etagen</p>
        {floors.length === 0 ? (
          <p className="text-xs text-gray-400">Keine Etagen gefunden.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {floors.map((floor) => (
              <li key={floor.floor_id}>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selectedFloorIds.includes(floor.floor_id)}
                    onChange={() => toggleFloor(floor.floor_id)}
                  />
                  {floor.name}
                </label>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
