export type Role = "admin" | "operator"

export type User = {
  id: number
  email: string
  role: Role
  is_active: boolean
  created_at?: string
}

export type Warning = { code: string; field: string; message: string }
export type Issue = { field: string; message: string; raw?: string }

export type ApiError = {
  field_errors?: Record<string, string>
  warnings?: Warning[]
  code?: string
  proposed?: Record<string, string>
  message?: string
  row_errors?: RowError[]
}

export type RowError = {
  index: number
  field_errors: Record<string, string>
  warnings: Warning[]
  code?: string | null
  proposed?: Record<string, string>
}

export type Cargo = {
  id: number
  legacy: boolean
  needs_review: boolean
  issues: Issue[]
  date_received: string | null
  customer_code: string | null
  company_name: string | null
  cartons: number | null
  gross_weight_kg: number | null
  gross_is_no_pallet: boolean
  net_weight_kg: number | null
  system_code: string | null
  shipment_number: string | null
  shipping_route?: string | null
  stage?: string | null
  status?: string | null
  file_count?: number
  created_at: string
  created_by: number | null
  updated_at: string | null
  updated_by: number | null
  deleted_at: string | null
  deleted_by: number | null
}

export type ExitRow = {
  id: number
  legacy: boolean
  needs_review: boolean
  issues: Issue[]
  no: number
  mark: string | null
  supplier: string | null
  invoice_no: string | null
  invoice_numbers: string[]
  cartons: number | null
  date_of_submission: string | null
  status: string | null
  created_at: string
  updated_at: string | null
  deleted_at: string | null
  deleted_by: number | null
}

export type Page<T> = { items: T[]; total: number }

export type AuditEntry = {
  id: number
  actor_user_id: number | null
  actor_email: string | null
  action: string
  entity_type: string | null
  entity_id: string | null
  before_json: unknown
  after_json: unknown
  changed_fields: { field: string; old: unknown; new: unknown }[]
  ip: string | null
  user_agent: string | null
  created_at: string
}

export type AgentStep = {
  name: string
  at: string
  duration_ms?: number | null
  input: unknown
  output: unknown
  error: string | null
}

export type AgentRun = {
  id: number
  agent_name: string
  status: string
  provider: string | null
  model: string | null
  actor_user_id: number | null
  actor_email: string | null
  entity_type: string | null
  entity_id: string | null
  error_message: string | null
  step_count: number
  duration_ms: number | null
  started_at: string
  finished_at: string | null
  input_json?: unknown
  steps_json?: AgentStep[]
  output_json?: unknown
  error_stack?: string | null
}

export type RequestLog = {
  id: number
  method: string
  path: string
  query: string | null
  status_code: number
  duration_ms: number
  actor_user_id: number | null
  actor_email: string | null
  ip: string | null
  user_agent: string | null
  error_message: string | null
  created_at: string
}

export type Enums = {
  shipping_routes: string[]
  stages: string[]
  air_statuses: string[]
  exit_statuses: string[]
  container_stages: string[]
}

export type SaveResult<T> = { item: T; warnings: Warning[] }

export type Breakdown = { label: string; count: number }

export type SheetSummary = {
  rows: number
  needs_review: number
  cartons: number
  breakdown: Breakdown[]
}

export type Dashboard = {
  sea: SheetSummary
  air: SheetSummary
  exit: SheetSummary
}

export type Shipment = {
  kind: "sea" | "air"
  id: number
  date_received: string | null
  customer_code: string | null
  company_name: string | null
  cartons: number | null
  system_code: string | null
  shipment_number: string | null
  shipping_route: string | null
  progress: string | null
  needs_review: boolean
}

export type AppSettings = {
  llm_model: string
  llm_timeout_sec: string
}

export type PromptSummary = {
  key: string
  label: string
  active_version: number | null
  latest_version: number | null
  body: string
  updated_at: string | null
}

export type PromptVersionRow = {
  id: number
  version: number
  body: string
  note: string | null
  created_by_user_id: number | null
  created_by_email: string | null
  created_at: string | null
  is_active: boolean
}

export type PromptDetail = {
  key: string
  label: string
  active_version: number | null
  versions: PromptVersionRow[]
}
