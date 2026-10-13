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

export type Enums = {
  shipping_routes: string[]
  stages: string[]
  air_statuses: string[]
  exit_statuses: string[]
}

export type SaveResult<T> = { item: T; warnings: Warning[] }
