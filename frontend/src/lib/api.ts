/* ----------------------------------------------------------------
   HTTP API client — thin wrapper around fetch
   ---------------------------------------------------------------- */

import { toast } from 'vue-sonner'

const BASE_URL = '/api/v1'

class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body: unknown,
  ) {
    super(`API Error ${status}: ${statusText}`)
    this.name = 'ApiError'
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  params?: Record<string, string | number | boolean | undefined>,
): Promise<T> {
  // Build URL with query params
  let url = `${BASE_URL}${path}`
  if (params) {
    const searchParams = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.set(key, String(value))
      }
    }
    const qs = searchParams.toString()
    if (qs) url += `?${qs}`
  }

  const headers: Record<string, string> = {}
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  const response = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  // 204 No Content
  if (response.status === 204) {
    return undefined as T
  }

  const data = await response.json().catch(() => null)

  if (!response.ok) {
    const detail =
      (data as Record<string, unknown>)?.detail ??
      (data as Record<string, unknown>)?.message ??
      response.statusText
    toast.error('Erreur serveur', {
      description: `${response.status} — ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`,
    })
    throw new ApiError(response.status, response.statusText, data)
  }

  return data as T
}

// Convenience methods
export const api = {
  get: <T>(path: string, params?: Record<string, string | number | boolean | undefined>) =>
    request<T>('GET', path, undefined, params),

  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),

  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),

  delete: <T>(path: string) => request<T>('DELETE', path),
}

export { ApiError }
