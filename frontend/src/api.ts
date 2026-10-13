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

export function showValue(value: unknown) {
  if (value == null || value === "") return "—"
  if (typeof value === "boolean") return value ? "yes" : "no"
  return String(value)
}
