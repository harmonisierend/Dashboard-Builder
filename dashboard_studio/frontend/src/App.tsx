import { HashRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { EntityTable } from "./components/registry/EntityTable";
import { useRegistrySnapshot } from "./hooks/useRegistrySnapshot";

function RegistryPage() {
  const { data, loading, error, refresh } = useRegistrySnapshot();

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-medium">Entity-Bestand</h2>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading}
          className="rounded border border-gray-300 px-3 py-1 text-sm hover:bg-gray-50 disabled:opacity-50"
        >
          {loading ? "Lädt…" : "Aktualisieren"}
        </button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {data ? (
        <EntityTable entities={data.filtered_entities} />
      ) : (
        !error && <p className="text-sm text-gray-500">Entitäten werden geladen…</p>
      )}
    </div>
  );
}

export function App() {
  return (
    // HashRouter, not BrowserRouter: HA serves this app under a dynamic,
    // per-installation Ingress path prefix. Routing state in the URL
    // fragment never interacts with that prefix, so no basename needs to
    // be computed or guessed at runtime -- the same rule as relative API
    // and asset URLs, applied to routing.
    <HashRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<RegistryPage />} />
        </Routes>
      </AppShell>
    </HashRouter>
  );
}
