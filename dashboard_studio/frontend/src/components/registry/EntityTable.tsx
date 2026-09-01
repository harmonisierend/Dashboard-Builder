import { useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { EntityRecord } from "../../lib/apiClient";

interface EntityTableProps {
  entities: EntityRecord[];
}

function useUniqueValues(
  entities: EntityRecord[],
  key: "area_name" | "floor_name" | "domain",
): string[] {
  return useMemo(() => {
    const values = new Set<string>();
    for (const entity of entities) {
      const value = entity[key];
      if (value) values.add(value);
    }
    return Array.from(values).sort();
  }, [entities, key]);
}

export function EntityTable({ entities }: EntityTableProps) {
  const [search, setSearch] = useState("");
  const [areaFilter, setAreaFilter] = useState("");
  const [floorFilter, setFloorFilter] = useState("");
  const [domainFilter, setDomainFilter] = useState("");
  const [labelFilter, setLabelFilter] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const areas = useUniqueValues(entities, "area_name");
  const floors = useUniqueValues(entities, "floor_name");
  const domains = useUniqueValues(entities, "domain");
  const labels = useMemo(() => {
    const values = new Set<string>();
    for (const entity of entities) {
      for (const label of entity.labels) values.add(label);
    }
    return Array.from(values).sort();
  }, [entities]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return entities.filter((entity) => {
      if (areaFilter && entity.area_name !== areaFilter) return false;
      if (floorFilter && entity.floor_name !== floorFilter) return false;
      if (domainFilter && entity.domain !== domainFilter) return false;
      if (labelFilter && !entity.labels.includes(labelFilter)) return false;
      if (query) {
        const haystack = `${entity.entity_id} ${entity.name}`.toLowerCase();
        if (!haystack.includes(query)) return false;
      }
      return true;
    });
  }, [entities, search, areaFilter, floorFilter, domainFilter, labelFilter]);

  const parentRef = useRef<HTMLDivElement>(null);
  const rowVirtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 36,
    overscan: 12,
  });

  function toggleSelected(entityId: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(entityId)) next.delete(entityId);
      else next.add(entityId);
      return next;
    });
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          placeholder="Suche nach Entity-ID oder Name…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="rounded border border-gray-300 px-2 py-1 text-sm"
        />
        <select
          value={areaFilter}
          onChange={(event) => setAreaFilter(event.target.value)}
          className="rounded border border-gray-300 px-2 py-1 text-sm"
          aria-label="Nach Bereich filtern"
        >
          <option value="">Alle Bereiche</option>
          {areas.map((area) => (
            <option key={area} value={area}>
              {area}
            </option>
          ))}
        </select>
        <select
          value={floorFilter}
          onChange={(event) => setFloorFilter(event.target.value)}
          className="rounded border border-gray-300 px-2 py-1 text-sm"
          aria-label="Nach Etage filtern"
        >
          <option value="">Alle Etagen</option>
          {floors.map((floor) => (
            <option key={floor} value={floor}>
              {floor}
            </option>
          ))}
        </select>
        <select
          value={domainFilter}
          onChange={(event) => setDomainFilter(event.target.value)}
          className="rounded border border-gray-300 px-2 py-1 text-sm"
          aria-label="Nach Domain filtern"
        >
          <option value="">Alle Domains</option>
          {domains.map((domain) => (
            <option key={domain} value={domain}>
              {domain}
            </option>
          ))}
        </select>
        <select
          value={labelFilter}
          onChange={(event) => setLabelFilter(event.target.value)}
          className="rounded border border-gray-300 px-2 py-1 text-sm"
          aria-label="Nach Label filtern"
        >
          <option value="">Alle Labels</option>
          {labels.map((label) => (
            <option key={label} value={label}>
              {label}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => setSelected(new Set(filtered.map((entity) => entity.entity_id)))}
          className="rounded bg-blue-600 px-2 py-1 text-sm text-white hover:bg-blue-700"
        >
          Alle sichtbaren auswählen ({filtered.length})
        </button>
        <button
          type="button"
          onClick={() => setSelected(new Set())}
          className="rounded border border-gray-300 px-2 py-1 text-sm hover:bg-gray-50"
        >
          Auswahl aufheben
        </button>
        <span className="text-sm text-gray-500">{selected.size} ausgewählt</span>
      </div>

      <div
        ref={parentRef}
        className="h-[600px] overflow-auto rounded border border-gray-200"
        data-testid="entity-table-scroll"
      >
        <div style={{ height: rowVirtualizer.getTotalSize(), position: "relative" }}>
          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
            const entity = filtered[virtualRow.index];
            return (
              <div
                key={entity.entity_id}
                data-index={virtualRow.index}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  height: virtualRow.size,
                  transform: `translateY(${virtualRow.start}px)`,
                }}
                className="flex items-center gap-3 border-b border-gray-100 px-2 text-sm"
              >
                <input
                  type="checkbox"
                  checked={selected.has(entity.entity_id)}
                  onChange={() => toggleSelected(entity.entity_id)}
                  aria-label={`${entity.entity_id} auswählen`}
                />
                <span className="w-64 truncate font-mono text-xs">{entity.entity_id}</span>
                <span className="flex-1 truncate">{entity.name}</span>
                <span className="w-32 truncate text-gray-500">{entity.area_name ?? "–"}</span>
                <span
                  className={`h-2 w-2 rounded-full ${entity.available ? "bg-green-500" : "bg-amber-500"}`}
                  aria-hidden="true"
                  title={entity.available ? "verfügbar" : "nicht verfügbar/unbekannt"}
                />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
