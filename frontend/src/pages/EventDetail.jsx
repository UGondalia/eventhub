import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, CalendarDays, CheckCircle2, Clock, MapPin, UserRound } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import { useToast } from '../toast'
import Poster from '../components/Poster'
import Modal from '../components/Modal'
import { fmtDate, fmtTime, money, seatsLabel } from '../utils'

export default function EventDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const location = useLocation()

  const [event, setEvent] = useState(null)
  const [mine, setMine] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirmCancel, setConfirmCancel] = useState(false)

  const load = useCallback(() => {
    api
      .getEvent(id)
      .then((res) => { setEvent(res.event); setMine(res.my_registration) })
      .catch((err) => setError(err.message))
  }, [id])

  useEffect(load, [load, user?.id])

  const register = async () => {
    if (!user) return navigate('/signin', { state: { from: location.pathname } })
    setBusy(true)
    try {
      const res = await api.register(id)
      setEvent(res.event)
      setMine(res.registration)
      toast(`You’re in. Ticket ${res.registration.ticket_code} is saved under My tickets.`)
    } catch (err) {
      toast(err.message, 'error')
      load()
    } finally {
      setBusy(false)
    }
  }

  const cancel = async () => {
    setBusy(true)
    try {
      await api.cancelRegistration(mine.id)
      toast('Registration cancelled. Your seat is back in the pool.')
      setConfirmCancel(false)
      load()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  if (error) {
    return (
      <div className="container section empty">
        <h3>{error}</h3>
        <Link className="btn btn-primary" to="/">Back to events</Link>
      </div>
    )
  }
  if (!event) return <div className="page-loading">Loading…</div>

  const started = new Date(event.start) <= new Date()
  const pct = Math.min(100, Math.round((event.registered / event.capacity) * 100))

  return (
    <div className="container detail">
      <Link to="/" className="back"><ArrowLeft size={16} /> All events</Link>
      <Poster event={event} className="detail-poster">
        <span className="tag tag-on-poster">{event.category}</span>
      </Poster>

      <div className="detail-grid">
        <article>
          <h1>{event.title}</h1>
          <ul className="facts">
            <li><CalendarDays size={18} /> {fmtDate(event.start)}</li>
            <li>
              <Clock size={18} /> {fmtTime(event.start)}{event.end ? ` to ${fmtTime(event.end)}` : ''}
            </li>
            <li><MapPin size={18} /> {event.venue}{event.city ? `, ${event.city}` : ''}</li>
            {event.organizer && <li><UserRound size={18} /> Hosted by {event.organizer}</li>}
          </ul>
          <h2>About this event</h2>
          <p className="prose">{event.description || 'The organiser has not added a description yet.'}</p>
        </article>

        <aside className="panel">
          <div className="panel-price">
            <strong>{money(event.price)}</strong>
            {event.price > 0 && <span>per person</span>}
          </div>
          <div className="seats seats-lg">
            <div className="bar"><i style={{ width: `${pct}%` }} className={event.sold_out ? 'full' : ''} /></div>
            <span>{seatsLabel(event)} · {event.registered} of {event.capacity} booked</span>
          </div>

          {mine ? (
            <div className="booked">
              <p><CheckCircle2 size={20} /> You’re registered</p>
              <div className="code">{mine.ticket_code}</div>
              <Link to="/tickets" className="btn btn-ghost btn-block">View my tickets</Link>
              {!started && (
                <button className="btn btn-link" onClick={() => setConfirmCancel(true)}>
                  Cancel registration
                </button>
              )}
            </div>
          ) : started ? (
            <button className="btn btn-block" disabled>This event has started</button>
          ) : event.sold_out ? (
            <button className="btn btn-block" disabled>Sold out</button>
          ) : (
            <button className="btn btn-coral btn-block btn-lg" onClick={register} disabled={busy}>
              {busy ? 'Booking…' : user ? 'Register for this event' : 'Sign in to register'}
            </button>
          )}
        </aside>
      </div>

      {confirmCancel && (
        <Modal title="Cancel your registration?" onClose={() => setConfirmCancel(false)}>
          <p>Ticket <strong>{mine.ticket_code}</strong> will be released and someone else can take your seat.</p>
          <div className="modal-actions">
            <button className="btn btn-ghost" onClick={() => setConfirmCancel(false)}>Keep my ticket</button>
            <button className="btn btn-danger" onClick={cancel} disabled={busy}>Cancel registration</button>
          </div>
        </Modal>
      )}
    </div>
  )
}
