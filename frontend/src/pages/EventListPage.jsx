/** Display the public event catalogue loaded through shared application state. */

import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { EmptyMessage, ErrorMessage, LoadingMessage } from '../components/RequestFeedback.jsx'
import useAppState from '../state/useAppState.js'

/** Load and render a page of events with loading, error, and empty states. */
export default function EventListPage() {
  const { state, refreshEvents } = useAppState()
  const { events } = state

  useEffect(() => {
    refreshEvents()
  }, [refreshEvents])

  return (
    <section className="page-section">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Discover and plan</p>
          <h1>Events</h1>
        </div>
        <Link className="button button-primary" to="/events/new">
          Create event
        </Link>
      </div>

      {events.status === 'loading' && <LoadingMessage>Loading events…</LoadingMessage>}
      {events.status === 'error' && <ErrorMessage error={events.error} />}
      {events.status === 'success' && events.items.length === 0 && (
        <EmptyMessage>No events are available yet.</EmptyMessage>
      )}

      {events.items.length > 0 && (
        <div className="event-grid">
          {events.items.map((event) => (
            <article className="event-card" key={event.id}>
              <div className="event-card-meta">
                <span className={`status-badge status-${event.status}`}>{event.status}</span>
                <time dateTime={event.starts_at}>{formatDate(event.starts_at)}</time>
              </div>
              <h2>{event.title}</h2>
              <p>{event.description || 'Event details will be announced soon.'}</p>
              <p className="event-location">{event.location || 'Location to be announced'}</p>
              <Link className="text-link" to={`/events/${event.id}`}>
                View event <span aria-hidden="true">→</span>
              </Link>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

/** Format a valid API timestamp for a readable event card. */
function formatDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}
