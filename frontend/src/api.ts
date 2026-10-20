import type { ApiError } from "./types"

export async function api(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json")
  }
  const response = await fetch(path, { ...init, headers, credentials: "include" })
  if (response.status === 401 && !path.startsWith("/api/auth/")) {
    window.dispatchEvent(new Event("auth:lost"))
  }
  return response
}

export async function readError(response: Response): Promise<ApiError> {
  try {
    return (await response.json()) as ApiError
  } catch {
    return { message: response.statusText }
  }
}

export function showValue(value: unknown): string {
  if (value == null || value === "") return "—"
  if (typeof value === "boolean") return value ? "yes" : "no"
  if (Array.isArray(value)) {
    if (!value.length) return "—"
    return value
      .map((item) => {
        if (item && typeof item === "object" && "filename" in item) {
          return String((item as { filename?: string }).filename || "")
        }
        return showValue(item)
      })
      .filter(Boolean)
      .join(", ")
  }
  if (typeof value === "object") {
    const record = value as Record<string, unknown>
    if (typeof record.filename === "string") return record.filename
    if (typeof record.file_name === "string") return record.file_name
    if (Array.isArray(record.files)) return showValue(record.files)
    if (Array.isArray(record.photos)) return showValue(record.photos)
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }
  return String(value)
}

export type AuditChange = { field: string; old: unknown; new: unknown }

/** Normalize audit changed_fields (objects or legacy string tags) into readable rows. */
export function normalizeAuditChanges(
  changed: unknown,
  after: unknown,
  before: unknown,
): AuditChange[] {
  const afterObj = after && typeof after === "object" ? (after as Record<string, unknown>) : null
  const beforeObj = before && typeof before === "object" ? (before as Record<string, unknown>) : null
  const list = Array.isArray(changed) ? changed : []

  const normalized: AuditChange[] = list.map((item) => {
    if (typeof item === "string") {
      const key = item === "files" ? "photos" : item
      const newValue =
        afterObj?.[key] ??
        afterObj?.files ??
        afterObj?.photos ??
        afterObj?.file_name ??
        afterObj?.[item] ??
        null
      const oldValue =
        beforeObj?.[key] ??
        beforeObj?.files ??
        beforeObj?.photos ??
        beforeObj?.file_name ??
        beforeObj?.[item] ??
        null
      return { field: key, old: oldValue, new: newValue }
    }
    if (item && typeof item === "object" && "field" in item) {
      const change = item as AuditChange
      return {
        field: change.field === "files" ? "photos" : String(change.field || "change"),
        old: change.old,
        new: change.new,
      }
    }
    return { field: "change", old: null, new: item }
  })

  if (
    normalized.length === 1 &&
    (normalized[0].old == null || normalized[0].old === "") &&
    (normalized[0].new == null || normalized[0].new === "")
  ) {
    const photos = afterObj?.photos ?? afterObj?.files
    if (photos != null) {
      return [{ field: "photos", old: null, new: photos }]
    }
  }
  return normalized
}

export function friendlyAction(action: string) {
  const labels: Record<string, string> = {
    create: "Created",
    update: "Updated",
    delete: "Deleted",
    restore: "Restored",
    upload_photo: "Uploaded photo",
    delete_photo: "Deleted photo",
    restore_photo: "Restored photo",
    summarize: "Summarized receipts",
    extract_photo: "Extracted photo marks",
    update_extract: "Edited photo marks",
    check_plan: "Checked loading plan",
    upload_plan: "Uploaded loading plan",
    clear_plan: "Cleared loading plan",
    container_loading_upload: "Uploaded photo",
    container_loading_file_delete: "Deleted photo",
    container_loading_file_restore: "Restored photo",
    cargo_files_upload: "Uploaded files",
  }
  return labels[action] || action.replaceAll("_", " ")
}

export function friendlyEntity(entityType: string | null, entityId: string | null) {
  if (!entityType) return "—"
  const labels: Record<string, string> = {
    container_loading: "Container loading",
    container_row: "Container",
    expense: "Expense",
    air_shipment_picture: "Air shipment picture",
    sea_cargo: "Sea",
    air_cargo: "Air",
    exit_record: "Exit",
  }
  const name = labels[entityType] || entityType.replaceAll("_", " ")
  return entityId ? `${name} #${entityId}` : name
}
