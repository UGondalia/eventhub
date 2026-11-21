import { Link } from 'react-router-dom'
import { Clock, MapPin } from 'lucide-react'
import Poster from './Poster'
import { dateParts, fmtTime, money, seatsLabel } from '../utils'

export default function EventCard({ event }) {
  const { day, month } = dateParts(event.start)
  const pct = Math.min(100, Math.round((event.registered / event.capacity) * 100))
  const low = !event.sold_out && event.seats_left <= Math.max(5, event.capacity * 0.15)

  return (
    <Link to={`/events/${event.id}`} className="ticket-card">
      <Poster event={event}>
        <div className="date-stub">
          <strong>{day}</strong>
          <span>{month}</span>
        </div>
        <span className="price-pill">{money(event.price)}</span>
      </Poster>
      <div className="perforation" aria-hidden="true" />
      <div className="ticket-body">
        <span className="tag">{event.category}</span>
        <h3>{event.title}</h3>
        <p className="meta">
          <MapPin size={15} /> {event.venue}{event.city ? `, ${event.city}` : ''}
        </p>
        <p className="meta">
          <Clock size={15} /> {fmtTime(event.start)}
        </p>
        <div className="seats">
          <div className="bar" role="presentation">
            <i style={{ width: `${pct}%` }} className={event.sold_out ? 'full' : low ? 'low' : ''} />
          </div>
          <span className={event.sold_out ? 'sold' : low ? 'low-text' : ''}>{seatsLabel(event)}</span>
        </div>
      </div>
    </Link>
  )
}
