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

// -- Design tokens (Milestone 2) --------------------------------------

export interface ColorPair {
  light: string;
  dark: string;
}

export interface ColorPalette {
  primary: ColorPair;
  accent: ColorPair;
  background: ColorPair;
  surface: ColorPair;
  on_surface: ColorPair;
  state_on: ColorPair;
  state_off: ColorPair;
  warn: ColorPair;
  critical: ColorPair;
}

export interface FontSizeScale {
  xs: string;
  sm: string;
  md: string;
  lg: string;
  xl: string;
}

export interface FontWeights {
  regular: number;
  medium: number;
  bold: number;
}

export interface Typography {
  font_family: string;
  sizes: FontSizeScale;
  weights: FontWeights;
}

export type StyleFamily = "glass" | "flat" | "neumorphic";

export interface Form {
  border_radius_px: number;
  shadow: string;
  border_width_px: number;
  style_family: StyleFamily;
}

export type DensityMode = "compact" | "comfortable";

export interface Density {
  mode: DensityMode;
  grid_gap_px: number;
  section_spacing_px: number;
}

export interface CardStyleClassification {
  primary_style: string;
  reasoning: string;
}

export interface DesignTokenSet {
  schema_version: number;
  colors: ColorPalette;
  typography: Typography;
  form: Form;
  density: Density;
  card_style: CardStyleClassification;
}

export interface UploadResponse {
  upload_id: string;
  media_type: string;
  size_bytes: number;
}

export interface UsageInfo {
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number | null;
  model: string;
}

export interface AnalyzeResponse {
  tokens: DesignTokenSet;
  usage: UsageInfo;
}

export interface TokenPresetSummary {
  id: string;
  name: string;
  created_at: string;
}

export interface TokenPresetDetail {
  id: string;
  name: string;
  created_at: string;
  tokens: DesignTokenSet;
}

export interface ThemeExportResponse {
  filename: string;
  yaml: string;
}

// -- Dashboard generation (Milestone 3) --------------------------------

export type NativeCardType =
  | "tile"
  | "heading"
  | "entities"
  | "thermostat"
  | "history-graph"
  | "weather-forecast"
  | "light"
  | "media-control";

export interface CardConfig {
  card_type: NativeCardType;
  custom_type: string | null;
  entity: string | null;
  entities: string[] | null;
  name: string | null;
  title: string | null;
  heading: string | null;
  icon: string | null;
  color: string | null;
  features: string[] | null;
  hours_to_show: number | null;
}

export interface GridSection {
  column_span: number | null;
  row_span: number | null;
  cards: CardConfig[];
}

export interface SectionsView {
  title: string;
  max_columns: number | null;
  dense_section_placement: boolean | null;
  sections: GridSection[];
}

export interface GeneratedDashboard {
  views: SectionsView[];
}

export type GenerationStrategy = "by_area" | "by_domain" | "automatic";

export interface DashboardScopeRequest {
  area_ids?: string[];
  floor_ids?: string[];
  strategy: GenerationStrategy;
  token_preset_id?: string | null;
  tokens?: DesignTokenSet | null;
  include_diagnostic?: boolean;
}

export interface ValidationReportResponse {
  removed_entity_refs: number;
  removed_custom_types: number;
  removed_cards: number;
  removed_sections: number;
  removed_views: number;
  details: string[];
}

export interface DashboardUsageInfo {
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number | null;
  model: string;
  call_count: number;
}

// -- Per-entity curation (Milestone 4) ----------------------------------

export interface CandidateEntitySummary {
  entity_id: string;
  domain: string;
  name: string;
  area_name: string | null;
  device_class: string | null;
}

export interface StyleHint {
  density_mode: DensityMode;
  card_style: string;
  style_family: StyleFamily;
}

export interface ProposedView {
  name: string;
  candidates: CandidateEntitySummary[];
}

export interface ProposeStructureResponse {
  proposed_views: ProposedView[];
  available_custom_cards: Record<string, Record<string, string>>;
  style_hint: StyleHint | null;
  usage: DashboardUsageInfo;
  notes: string[];
}

export interface CuratedViewRequest {
  name: string;
  candidates: CandidateEntitySummary[];
}

export interface GenerateDashboardRequest {
  area_ids?: string[];
  floor_ids?: string[];
  include_diagnostic?: boolean;
  curated_views: CuratedViewRequest[];
  available_custom_cards: Record<string, Record<string, string>>;
  style_hint?: StyleHint | null;
  phase1_usage: DashboardUsageInfo;
}

export interface GenerateDashboardResponse {
  dashboard: GeneratedDashboard;
  yaml: string;
  validation: ValidationReportResponse;
  usage: DashboardUsageInfo;
  notes: string[];
}

const JSON_HEADERS = { "Content-Type": "application/json" };

export const api = {
  getStatus: (): Promise<StatusResponse> => request<StatusResponse>("api/status"),
  getRegistry: (includeDiagnostic = false): Promise<RegistryResponse> =>
    request<RegistryResponse>(`api/registry?include_diagnostic=${includeDiagnostic}`),
  refreshRegistry: (includeDiagnostic = false): Promise<RegistryResponse> =>
    request<RegistryResponse>(`api/registry/refresh?include_diagnostic=${includeDiagnostic}`, {
      method: "POST",
    }),

  uploadDesignImage: (file: File): Promise<UploadResponse> => {
    const form = new FormData();
    form.append("file", file);
    return request<UploadResponse>("api/design/upload", { method: "POST", body: form });
  },
  analyzeDesign: (uploadId: string): Promise<AnalyzeResponse> =>
    request<AnalyzeResponse>("api/design/analyze", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ upload_id: uploadId }),
    }),
  listTokenPresets: (): Promise<TokenPresetSummary[]> =>
    request<TokenPresetSummary[]>("api/design/presets"),
  getTokenPreset: (id: string): Promise<TokenPresetDetail> =>
    request<TokenPresetDetail>(`api/design/presets/${id}`),
  saveTokenPreset: (name: string, tokens: DesignTokenSet): Promise<TokenPresetDetail> =>
    request<TokenPresetDetail>("api/design/presets", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ name, tokens }),
    }),
  deleteTokenPreset: (id: string): Promise<{ deleted: boolean }> =>
    request<{ deleted: boolean }>(`api/design/presets/${id}`, { method: "DELETE" }),
  exportThemeYaml: (themeName: string, tokens: DesignTokenSet): Promise<ThemeExportResponse> =>
    request<ThemeExportResponse>("api/design/theme-export", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ theme_name: themeName, tokens }),
    }),

  proposeDashboardStructure: (body: DashboardScopeRequest): Promise<ProposeStructureResponse> =>
    request<ProposeStructureResponse>("api/dashboard/propose-structure", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  generateDashboard: (body: GenerateDashboardRequest): Promise<GenerateDashboardResponse> =>
    request<GenerateDashboardResponse>("api/dashboard/generate", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
};
