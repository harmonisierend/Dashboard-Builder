import { apiUrl } from "./ingressBase";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), init);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? detail;
    } catch {
      // Response body wasn't JSON -- keep statusText.
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export interface StatusResponse {
  ha_connected: boolean;
  ha_connection_source: string | null;
  last_registry_refresh: string | null;
  entity_count: number | null;
  area_count: number | null;
}

export interface EntityRecord {
  entity_id: string;
  domain: string;
  name: string;
  platform: string | null;
  device_id: string | null;
  device_name: string | null;
  area_id: string | null;
  area_name: string | null;
  floor_id: string | null;
  floor_name: string | null;
  labels: string[];
  entity_category: string | null;
  hidden_by: string | null;
  disabled_by: string | null;
  state: string | null;
  available: boolean;
  attributes: Record<string, unknown>;
}

export interface AreaRegistryEntry {
  area_id: string;
  name: string;
  floor_id: string | null;
  labels: string[];
}

export interface FloorRegistryEntry {
  floor_id: string;
  name: string;
  level: number | null;
}

export interface LabelRegistryEntry {
  label_id: string;
  name: string;
  color: string | null;
}

export interface LovelaceResource {
  id: string;
  type: string;
  url: string;
}

export interface RegistryResponse {
  fetched_at: string;
  entities: EntityRecord[];
  filtered_entities: EntityRecord[];
  areas: AreaRegistryEntry[];
  floors: FloorRegistryEntry[];
  labels: LabelRegistryEntry[];
  lovelace_resources: LovelaceResource[];
}

export const api = {
  getStatus: (): Promise<StatusResponse> => request<StatusResponse>("api/status"),
  getRegistry: (includeDiagnostic = false): Promise<RegistryResponse> =>
    request<RegistryResponse>(`api/registry?include_diagnostic=${includeDiagnostic}`),
  refreshRegistry: (includeDiagnostic = false): Promise<RegistryResponse> =>
    request<RegistryResponse>(`api/registry/refresh?include_diagnostic=${includeDiagnostic}`, {
      method: "POST",
    }),
};
