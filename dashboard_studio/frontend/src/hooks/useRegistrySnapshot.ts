import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type RegistryResponse } from "../lib/apiClient";

interface UseRegistrySnapshotResult {
  data: RegistryResponse | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useRegistrySnapshot(): UseRegistrySnapshotResult {
  const [data, setData] = useState<RegistryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (fetcher: () => Promise<RegistryResponse>) => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetcher();
      setData(result);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Unbekannter Fehler beim Laden der Entitäten.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Fetch-on-mount via a custom hook is the pattern React's own docs
    // recommend in place of a raw effect (see "You Might Not Need an
    // Effect"); the setLoading(true)/setError(null) reset at the top of
    // `load` is the intentional, synchronous "start loading" state change,
    // not an accidental cascade.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(() => api.getRegistry());
  }, [load]);

  const refresh = useCallback(() => load(() => api.refreshRegistry()), [load]);

  return { data, loading, error, refresh };
}
