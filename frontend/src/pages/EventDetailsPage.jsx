/** Present the details for one event selected by its route identifier. */

import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { EmptyMessage, ErrorMessage, LoadingMessage } from '../components/RequestFeedback.jsx'
import useAppState from '../state/useAppState.js'

/** Load an event by ID and show its public fields or request feedback. */
export default function EventDetailsPage() {
  const { eventId } = useParams()
  const { state, loadEvent } = useAppState()
  const { event, status, error } = state.selectedEvent

  useEffect(() => {
    loadEvent(eventId)
  }, [eventId, loadEvent])

  if (status === 'loading') {
    return <LoadingMessage>Loading event details…</LoadingMessage>
  }
  if (status === 'error') {
    return (
      <section className="page-section">
        <ErrorMessage error={error} />
        <Link className="text-link" to="/events">Return to events</Link>
      </section>
    )
  }
  if (!event) {
    return <EmptyMessage>Select an event to see its details.</EmptyMessage>
  }

  return (
    <article className="content-panel event-detail">
      <Link className="text-link" to="/events">← All events</Link>
      <p className="eyebrow">{event.status}</p>
      <h1>{event.title}</h1>
      <p className="event-description">
        {event.description || 'No description has been provided for this event.'}
      </p>
      <dl className="event-facts">
        <div><dt>Starts</dt><dd>{formatDate(event.starts_at)}</dd></div>
        <div><dt>Ends</dt><dd>{formatDate(event.ends_at)}</dd></div>
        <div><dt>Location</dt><dd>{event.location || 'To be announced'}</dd></div>
        <div><dt>Capacity</dt><dd>{event.capacity}</dd></div>
      </dl>
    </article>
  )
}

/** Format a timestamp returned by the event API. */
function formatDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'full', timeStyle: 'short' }).format(date)
}
