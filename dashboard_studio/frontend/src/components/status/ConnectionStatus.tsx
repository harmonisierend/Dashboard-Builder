import { useEffect, useState } from "react";
import { api, type StatusResponse } from "../../lib/apiClient";

export function ConnectionStatus() {
  const [status, setStatus] = useState<StatusResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getStatus()
      .then((result) => {
        if (!cancelled) setStatus(result);
      })
      .catch(() => {
        if (!cancelled) setStatus(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!status) {
    return <span className="text-sm text-gray-500">Status wird geladen…</span>;
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      <span
        className={`h-2 w-2 rounded-full ${status.ha_connected ? "bg-green-500" : "bg-red-500"}`}
        aria-hidden="true"
      />
      <span>
        {status.ha_connected
          ? `Verbunden mit Home Assistant (${status.entity_count ?? "?"} Entitäten, ${status.area_count ?? "?"} Bereiche)`
          : "Keine Verbindung zu Home Assistant"}
      </span>
    </div>
  );
}
