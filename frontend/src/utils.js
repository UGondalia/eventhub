export const CATEGORIES = [
  'Technology', 'Music', 'Business', 'Sports',
  'Arts', 'Food', 'Education', 'Community',
]

export const money = (n) => (n ? `₹${Number(n).toLocaleString('en-IN')}` : 'Free')

export const fmtDate = (iso) =>
  new Date(iso).toLocaleDateString('en-IN', {
    weekday: 'short', day: 'numeric', month: 'long', year: 'numeric',
  })

export const fmtShortDate = (iso) =>
  new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })

export const fmtTime = (iso) =>
  new Date(iso).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })

export const dateParts = (iso) => {
  const d = new Date(iso)
  return {
    day: d.toLocaleDateString('en-IN', { day: '2-digit' }),
    month: d.toLocaleDateString('en-IN', { month: 'short' }),
  }
}

export function countdown(iso, nowMs = Date.now()) {
  const diff = Math.max(0, new Date(iso).getTime() - nowMs)
  return {
    days: Math.floor(diff / 86400000),
    hours: Math.floor((diff % 86400000) / 3600000),
    minutes: Math.floor((diff % 3600000) / 60000),
  }
}

const pad = (n) => String(n).padStart(2, '0')

// <input type="datetime-local"> works in local time; the API stores UTC ISO strings.
export const toLocalInput = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export const fromLocalInput = (value) => (value ? new Date(value).toISOString() : '')

export function seatsLabel(event) {
  if (event.sold_out) return 'Sold out'
  if (event.seats_left <= Math.max(5, event.capacity * 0.15)) return `Only ${event.seats_left} left`
  return `${event.seats_left} seats left`
}
