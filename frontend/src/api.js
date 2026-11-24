import { enabled as cognitoEnabled, getIdToken } from './cognito'

// API client. Locally requests go to /api (proxied by Vite to the Python server).
// On AWS, build with VITE_API_URL=https://<id>.execute-api.<region>.amazonaws.com/<stage>
const BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')

const TOKEN_KEY = 'eventhub_token'
export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (token) =>
  token ? localStorage.setItem(TOKEN_KEY, token) : localStorage.removeItem(TOKEN_KEY)

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function request(path, { method = 'GET', body, query } = {}) {
  const qs = query
    ? '?' + new URLSearchParams(Object.entries(query).filter(([, v]) => v)).toString()
    : ''
  const headers = { 'Content-Type': 'application/json' }
  const token = cognitoEnabled ? await getIdToken() : getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let res
  try {
    res = await fetch(`${BASE}${path}${qs}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError('Cannot reach the server. Is the backend running?', 0)
  }
  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(data?.error || `Request failed (${res.status})`, res.status)
  return data
}

export const api = {
  signup: (body) => request('/auth/signup', { method: 'POST', body }),
  login: (body) => request('/auth/login', { method: 'POST', body }),
  me: () => request('/auth/me'),

  listEvents: (query) => request('/events', { query }),
  adminEvents: () => request('/admin/events'),
  getEvent: (id) => request(`/events/${id}`),
  createEvent: (body) => request('/events', { method: 'POST', body }),
  updateEvent: (id, body) => request(`/events/${id}`, { method: 'PUT', body }),
  deleteEvent: (id) => request(`/events/${id}`, { method: 'DELETE' }),

  register: (id) => request(`/events/${id}/register`, { method: 'POST' }),
  cancelRegistration: (id) => request(`/registrations/${id}`, { method: 'DELETE' }),
  myRegistrations: () => request('/registrations/me'),
  eventRegistrations: (id) => request(`/events/${id}/registrations`),

  stats: () => request('/admin/stats'),
  runReminders: (hours) => request('/admin/reminders/run', { method: 'POST', body: { hours } }),
  notifications: () => request('/admin/notifications'),
}
