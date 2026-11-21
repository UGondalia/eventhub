import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CalendarX, MapPin, Search } from 'lucide-react'
import { api } from '../api'
import EventCard from '../components/EventCard'
import Poster from '../components/Poster'
import { CATEGORIES, countdown, dateParts, fmtTime, money } from '../utils'

function NextUp({ event }) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30000)
    return () => clearInterval(timer)
  }, [])
  if (!event) return <div className="nextup nextup-empty" aria-hidden="true" />

  const { days, hours, minutes } = countdown(event.start, now)
  const { day, month } = dateParts(event.start)
  return (
    <Link to={`/events/${event.id}`} className="nextup" aria-label={`Next up: ${event.title}`}>
      <Poster event={event} className="nextup-poster">
        <div className="date-stub"><strong>{day}</strong><span>{month}</span></div>
      </Poster>
      <div className="perforation" aria-hidden="true" />
      <div className="nextup-body">
        <p className="nextup-label">Starting soonest</p>
        <h3>{event.title}</h3>
        <p className="meta"><MapPin size={15} /> {event.city || event.venue} · {fmtTime(event.start)} · {money(event.price)}</p>
        <div className="countdown" aria-label="Time until start">
          <div><strong>{days}</strong><span>days</span></div>
          <div><strong>{hours}</strong><span>hours</span></div>
          <div><strong>{minutes}</strong><span>min</span></div>
        </div>
      </div>
    </Link>
  )
}

export default function Home() {
  const [events, setEvents] = useState(null)
  const [nextUp, setNextUp] = useState(null)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    const timer = setTimeout(() => {
      api
        .listEvents({ q: query.trim(), category })
        .then((res) => {
          if (cancelled) return
          setError('')
          setEvents(res.events)
          if (!query && !category) setNextUp(res.events[0] || null)
        })
        .catch((err) => !cancelled && setError(err.message))
    }, query ? 250 : 0)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [query, category])

  return (
    <>
      <section className="hero">
        <div className="container hero-grid">
          <div className="hero-copy">
            <h1>Events worth showing up for.</h1>
            <p className="lead">
              Workshops, concerts, runs and meetups in your city. Pick one, grab a seat, and get
              your ticket in two clicks.
            </p>
            <label className="search">
              <Search size={20} aria-hidden="true" />
              <input
                type="search"
                placeholder="Search by event, venue or city"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                aria-label="Search events"
              />
            </label>
            <div className="chips" role="group" aria-label="Filter by category">
              <button className={`chip ${category === '' ? 'on' : ''}`} onClick={() => setCategory('')}>
                All
              </button>
              {CATEGORIES.map((c) => (
                <button
                  key={c}
                  className={`chip ${category === c ? 'on' : ''}`}
                  onClick={() => setCategory(c === category ? '' : c)}
                  aria-pressed={category === c}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
          <NextUp event={nextUp} />
        </div>
      </section>

      <section className="container section">
        <div className="section-head">
          <h2>{category ? `${category} events` : 'Upcoming events'}</h2>
          {events && <span className="count">{events.length} {events.length === 1 ? 'event' : 'events'}</span>}
        </div>

        {error && (
          <div className="empty">
            <CalendarX size={36} />
            <h3>We couldn’t load events</h3>
            <p>{error}</p>
          </div>
        )}

        {!error && events === null && (
          <div className="grid">
            {Array.from({ length: 6 }).map((_, i) => <div key={i} className="skeleton" />)}
          </div>
        )}

        {!error && events && events.length === 0 && (
          <div className="empty">
            <CalendarX size={36} />
            <h3>No events match that search</h3>
            <p>Try a different word, or clear the category filter.</p>
            <button className="btn btn-ghost" onClick={() => { setQuery(''); setCategory('') }}>
              Clear filters
            </button>
          </div>
        )}

        {!error && events && events.length > 0 && (
          <div className="grid">
            {events.map((event) => <EventCard key={event.id} event={event} />)}
          </div>
        )}
      </section>
    </>
  )
}
