import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { MapPin, TicketX } from 'lucide-react'
import { api } from '../api'
import { useToast } from '../toast'
import Modal from '../components/Modal'
import { dateParts, fmtDate, fmtTime, money } from '../utils'

function Ticket({ reg, onCancel }) {
  const event = reg.event
  const past = event && new Date(event.start) <= new Date()
  const inactive = reg.status !== 'confirmed' || past || !event
  const { day, month } = event ? dateParts(event.start) : { day: '--', month: '' }

  return (
    <article className={`my-ticket ${inactive ? 'is-inactive' : ''}`}>
      <div className="stub stub-date">
        <strong>{day}</strong>
        <span>{month}</span>
      </div>
      <div className="my-ticket-main">
        {event ? (
          <>
            <Link to={`/events/${event.id}`}><h3>{event.title}</h3></Link>
            <p className="meta">{fmtDate(event.start)} · {fmtTime(event.start)}</p>
            <p className="meta"><MapPin size={15} /> {event.venue}{event.city ? `, ${event.city}` : ''}</p>
          </>
        ) : (
          <>
            <h3>This event was removed</h3>
            <p className="meta">The organiser cancelled it.</p>
          </>
        )}
        <p className="meta">
          {event ? money(event.price) : ''}
          {reg.status === 'cancelled' && <span className="status status-bad">Cancelled</span>}
          {reg.status === 'confirmed' && past && <span className="status">Attended</span>}
        </p>
      </div>
      <div className="stub stub-code">
        <span>Ticket</span>
        <strong>{reg.ticket_code}</strong>
        <div className="barcode" aria-hidden="true" />
        {!inactive && (
          <button className="btn btn-link" onClick={() => onCancel(reg)}>Cancel</button>
        )}
      </div>
    </article>
  )
}

export default function MyTickets() {
  const toast = useToast()
  const [regs, setRegs] = useState(null)
  const [tab, setTab] = useState('upcoming')
  const [target, setTarget] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    api.myRegistrations().then((res) => setRegs(res.registrations)).catch((e) => toast(e.message, 'error'))
  }, [toast])
  useEffect(load, [load])

  const confirm = async () => {
    setBusy(true)
    try {
      await api.cancelRegistration(target.id)
      toast('Registration cancelled.')
      setTarget(null)
      load()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  const isUpcoming = (r) => r.status === 'confirmed' && r.event && new Date(r.event.start) > new Date()
  const shown = (regs || []).filter((r) => (tab === 'upcoming' ? isUpcoming(r) : !isUpcoming(r)))

  return (
    <div className="container section">
      <div className="section-head">
        <h1>My tickets</h1>
        <div className="tabs" role="tablist">
          {['upcoming', 'history'].map((t) => (
            <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>
              {t === 'upcoming' ? 'Upcoming' : 'Past and cancelled'}
            </button>
          ))}
        </div>
      </div>

      {regs === null ? (
        <div className="page-loading">Loading…</div>
      ) : shown.length === 0 ? (
        <div className="empty">
          <TicketX size={36} />
          <h3>{tab === 'upcoming' ? 'No tickets yet' : 'Nothing here yet'}</h3>
          <p>{tab === 'upcoming' ? 'Find an event you like and register. Your ticket will show up here.' : 'Past and cancelled registrations will appear here.'}</p>
          {tab === 'upcoming' && <Link className="btn btn-primary" to="/">Browse events</Link>}
        </div>
      ) : (
        <div className="tickets">
          {shown.map((r) => <Ticket key={r.id} reg={r} onCancel={setTarget} />)}
        </div>
      )}

      {target && (
        <Modal title="Cancel this registration?" onClose={() => setTarget(null)}>
          <p>Ticket <strong>{target.ticket_code}</strong> for {target.event?.title} will be released.</p>
          <div className="modal-actions">
            <button className="btn btn-ghost" onClick={() => setTarget(null)}>Keep my ticket</button>
            <button className="btn btn-danger" onClick={confirm} disabled={busy}>Cancel registration</button>
          </div>
        </Modal>
      )}
    </div>
  )
}
