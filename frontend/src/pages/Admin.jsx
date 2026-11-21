import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BellRing, Pencil, Plus, Trash2 } from 'lucide-react'
import { api } from '../api'
import { useToast } from '../toast'
import Modal from '../components/Modal'
import { CATEGORIES, fmtShortDate, fmtTime, fromLocalInput, money, toLocalInput } from '../utils'

const TABS = [
  ['overview', 'Overview'],
  ['events', 'Events'],
  ['attendees', 'Attendees'],
  ['notifications', 'Notifications'],
]

/* ---------- Overview ---------- */
function Overview() {
  const [stats, setStats] = useState(null)
  const toast = useToast()
  useEffect(() => {
    api.stats().then(setStats).catch((e) => toast(e.message, 'error'))
  }, [toast])
  if (!stats) return <div className="page-loading">Loading…</div>

  const maxDay = Math.max(1, ...stats.registrations_by_day.map((d) => d.count))
  const maxCat = Math.max(1, ...stats.by_category.map((c) => c.registrations))

  return (
    <>
      <div className="stats">
        <div className="stat"><span>Upcoming events</span><strong>{stats.upcoming_events}</strong><small>of {stats.total_events} in total</small></div>
        <div className="stat"><span>Registrations</span><strong>{stats.total_registrations}</strong><small>confirmed seats</small></div>
        <div className="stat"><span>Ticket revenue</span><strong>₹{stats.revenue.toLocaleString('en-IN')}</strong><small>from confirmed seats</small></div>
        <div className="stat"><span>Seats filled</span><strong>{stats.fill_rate}%</strong><small>across upcoming events</small></div>
      </div>

      <div className="panels">
        <section className="card">
          <h3>Registrations, last 7 days</h3>
          <div className="columns" role="img" aria-label="Registrations per day for the last seven days">
            {stats.registrations_by_day.map((d) => (
              <div key={d.date} className="col">
                <span className="col-num">{d.count}</span>
                <i style={{ height: `calc((100% - 48px) * ${d.count / maxDay})` }} />
                <span className="col-label">{new Date(d.date).toLocaleDateString('en-IN', { weekday: 'short' })}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="card">
          <h3>Registrations by category</h3>
          <ul className="hbars">
            {stats.by_category.map((c) => (
              <li key={c.category}>
                <span>{c.category}</span>
                <div><i style={{ width: `${(c.registrations / maxCat) * 100}%` }} /></div>
                <b>{c.registrations}</b>
              </li>
            ))}
          </ul>
        </section>

        <section className="card card-wide">
          <h3>Most popular events</h3>
          <ol className="toplist">
            {stats.top_events.map((e) => (
              <li key={e.id}>
                <Link to={`/events/${e.id}`}>{e.title}</Link>
                <span>{e.registrations} / {e.capacity} seats</span>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </>
  )
}

/* ---------- Event form ---------- */
const EMPTY = { title: '', category: 'Technology', description: '', venue: '', city: '', start: '', end: '', price: 0, capacity: 50, image: '' }

function EventForm({ event, onClose, onSaved }) {
  const toast = useToast()
  const [form, setForm] = useState(
    event
      ? { ...EMPTY, ...event, start: toLocalInput(event.start), end: toLocalInput(event.end) }
      : EMPTY,
  )
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    const body = {
      title: form.title, category: form.category, description: form.description,
      venue: form.venue, city: form.city, image: form.image,
      start: fromLocalInput(form.start), end: fromLocalInput(form.end),
      price: Number(form.price), capacity: Number(form.capacity),
    }
    try {
      if (event) await api.updateEvent(event.id, body)
      else await api.createEvent(body)
      toast(event ? 'Event updated.' : 'Event created.')
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title={event ? 'Edit event' : 'Create event'} onClose={onClose} wide>
      <form className="form-grid" onSubmit={submit}>
        <label className="span-2">Title<input value={form.title} onChange={set('title')} required minLength={3} maxLength={120} /></label>
        <label>Category
          <select value={form.category} onChange={set('category')}>
            {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <label><span>Image URL <small>(optional)</small></span><input type="url" value={form.image} onChange={set('image')} placeholder="https://…" /></label>
        <label className="span-2">Description<textarea rows={3} value={form.description} onChange={set('description')} maxLength={2000} /></label>
        <label>Venue<input value={form.venue} onChange={set('venue')} required /></label>
        <label>City<input value={form.city} onChange={set('city')} /></label>
        <label>Starts<input type="datetime-local" value={form.start} onChange={set('start')} required /></label>
        <label><span>Ends <small>(optional)</small></span><input type="datetime-local" value={form.end} onChange={set('end')} /></label>
        <label><span>Price in ₹ <small>(0 for free)</small></span><input type="number" min="0" step="1" value={form.price} onChange={set('price')} /></label>
        <label>Capacity<input type="number" min={Math.max(1, event?.registered || 1)} max="100000" value={form.capacity} onChange={set('capacity')} required /></label>
        {error && <p className="form-error span-2" role="alert">{error}</p>}
        <div className="modal-actions span-2">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : event ? 'Save changes' : 'Create event'}</button>
        </div>
      </form>
    </Modal>
  )
}

/* ---------- Events ---------- */
function Events() {
  const toast = useToast()
  const [events, setEvents] = useState(null)
  const [editing, setEditing] = useState(null) // null | 'new' | event
  const [deleting, setDeleting] = useState(null)

  const load = useCallback(() => {
    api.listEvents({ scope: 'all' }).then((r) => setEvents(r.events)).catch((e) => toast(e.message, 'error'))
  }, [toast])
  useEffect(load, [load])

  const remove = async () => {
    try {
      const res = await api.deleteEvent(deleting.id)
      toast(`Event deleted. ${res.participants_notified} participant${res.participants_notified === 1 ? '' : 's'} notified.`)
      setDeleting(null)
      load()
    } catch (err) {
      toast(err.message, 'error')
    }
  }

  return (
    <>
      <div className="toolbar">
        <p>{events ? `${events.length} events` : ''}</p>
        <button className="btn btn-primary" onClick={() => setEditing('new')}><Plus size={18} /> New event</button>
      </div>
      {!events ? <div className="page-loading">Loading…</div> : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Event</th><th>Date</th><th>Price</th><th>Booked</th><th><span className="sr">Actions</span></th></tr></thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id}>
                  <td><Link to={`/events/${e.id}`}><strong>{e.title}</strong></Link><br /><small>{e.category} · {e.city || e.venue}</small></td>
                  <td>{fmtShortDate(e.start)}, {fmtTime(e.start)}</td>
                  <td>{money(e.price)}</td>
                  <td>{e.registered} / {e.capacity}</td>
                  <td className="row-actions">
                    <button className="icon-btn" aria-label={`Edit ${e.title}`} onClick={() => setEditing(e)}><Pencil size={16} /></button>
                    <button className="icon-btn danger" aria-label={`Delete ${e.title}`} onClick={() => setDeleting(e)}><Trash2 size={16} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <EventForm
          event={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load() }}
        />
      )}
      {deleting && (
        <Modal title="Delete this event?" onClose={() => setDeleting(null)}>
          <p><strong>{deleting.title}</strong> will be removed, and its {deleting.registered} registered participant{deleting.registered === 1 ? '' : 's'} will get a cancellation message.</p>
          <div className="modal-actions">
            <button className="btn btn-ghost" onClick={() => setDeleting(null)}>Keep event</button>
            <button className="btn btn-danger" onClick={remove}>Delete event</button>
          </div>
        </Modal>
      )}
    </>
  )
}

/* ---------- Attendees ---------- */
function Attendees() {
  const toast = useToast()
  const [events, setEvents] = useState([])
  const [eventId, setEventId] = useState('')
  const [data, setData] = useState(null)

  useEffect(() => {
    api.listEvents({ scope: 'all' }).then((r) => {
      setEvents(r.events)
      if (r.events[0]) setEventId(r.events[0].id)
    }).catch((e) => toast(e.message, 'error'))
  }, [toast])

  useEffect(() => {
    if (!eventId) return
    setData(null)
    api.eventRegistrations(eventId).then(setData).catch((e) => toast(e.message, 'error'))
  }, [eventId, toast])

  return (
    <>
      <div className="toolbar">
        <label className="inline-select">Event
          <select value={eventId} onChange={(e) => setEventId(e.target.value)}>
            {events.map((e) => <option key={e.id} value={e.id}>{e.title}</option>)}
          </select>
        </label>
        {data && <p>{data.registrations.filter((r) => r.status === 'confirmed').length} confirmed</p>}
      </div>
      {!data ? <div className="page-loading">Loading…</div> : data.registrations.length === 0 ? (
        <div className="empty"><h3>No registrations yet</h3><p>When people book this event they will be listed here.</p></div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Name</th><th>Email</th><th>Ticket</th><th>Status</th><th>Booked</th></tr></thead>
            <tbody>
              {data.registrations.map((r) => (
                <tr key={r.id}>
                  <td>{r.user_name}</td>
                  <td>{r.user_email}</td>
                  <td><code>{r.ticket_code}</code></td>
                  <td><span className={`status ${r.status === 'cancelled' ? 'status-bad' : ''}`}>{r.status === 'cancelled' ? 'Cancelled' : 'Confirmed'}</span></td>
                  <td>{fmtShortDate(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

/* ---------- Notifications ---------- */
function Notifications() {
  const toast = useToast()
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    api.notifications().then(setData).catch((e) => toast(e.message, 'error'))
  }, [toast])
  useEffect(load, [load])

  const run = async () => {
    setBusy(true)
    try {
      const res = await api.runReminders(24)
      toast(`Checked ${res.checked_events} event${res.checked_events === 1 ? '' : 's'} starting in the next ${res.window_hours} hours. Sent ${res.reminders_sent} reminder${res.reminders_sent === 1 ? '' : 's'}.`)
      load()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="toolbar">
        <p>{data?.mode === 'sns' ? 'Messages are sent through Amazon SNS.' : 'Local mode: messages are saved here instead of being emailed.'}</p>
        <button className="btn btn-primary" onClick={run} disabled={busy}><BellRing size={18} /> {busy ? 'Running…' : 'Send due reminders'}</button>
      </div>
      {!data ? <div className="page-loading">Loading…</div> : data.notifications.length === 0 ? (
        <div className="empty"><h3>No messages yet</h3><p>Register for an event and the confirmation will show up here.</p></div>
      ) : (
        <ul className="outbox">
          {data.notifications.map((n) => (
            <li key={n.id}>
              <div><span className={`kind kind-${n.kind}`}>{n.kind.replace('_', ' ')}</span><time>{new Date(n.sent_at).toLocaleString('en-IN')}</time></div>
              <strong>{n.subject}</strong>
              <small>To {n.to}</small>
              <pre>{n.message}</pre>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}

export default function Admin() {
  const [tab, setTab] = useState('overview')
  return (
    <div className="container section">
      <div className="section-head">
        <h1>Organiser dashboard</h1>
        <div className="tabs" role="tablist">
          {TABS.map(([key, label]) => (
            <button key={key} role="tab" aria-selected={tab === key} className={tab === key ? 'on' : ''} onClick={() => setTab(key)}>
              {label}
            </button>
          ))}
        </div>
      </div>
      {tab === 'overview' && <Overview />}
      {tab === 'events' && <Events />}
      {tab === 'attendees' && <Attendees />}
      {tab === 'notifications' && <Notifications />}
    </div>
  )
}
