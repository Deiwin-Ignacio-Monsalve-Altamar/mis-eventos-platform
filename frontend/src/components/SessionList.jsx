/** Show an event's real sessions and public capacity snapshots. */

import { useEffect, useState } from 'react'
import { getSessionOccupancy } from '../api/events.js'
import EventArtwork from './EventArtwork.jsx'
import EventErrorMessage from './EventErrorMessage.jsx'
import { EmptyMessage, LoadingMessage } from './RequestFeedback.jsx'
import { formatEventDate, getSessionAvailability, sortSessions } from '../utils/eventPresentation.js'

/** Render session cards in chronological order with available backend data. */
export default function SessionList({ eventId, sessions, status, error, onRetry, refreshKey = 0 }) {
  if (status === 'loading' || status === 'idle') {
    return <LoadingMessage>Cargando sesiones…</LoadingMessage>
  }
  if (status === 'error') {
    return (
      <div className="event-request-error">
        <EventErrorMessage error={error} />
        <button className="button button-secondary" onClick={onRetry} type="button">
          Volver a cargar sesiones
        </button>
      </div>
    )
  }
  if (sessions.length === 0) {
    return <EmptyMessage>Este evento todavía no tiene sesiones programadas.</EmptyMessage>
  }

  return (
    <ol className="session-list">
        {sortSessions(sessions).map((session, index) => (
          <SessionItem eventId={eventId} index={index} key={`${session.id}:${refreshKey}`} session={session} />
      ))}
    </ol>
  )
}

/** Load the current occupancy for one session without blocking its details. */
function SessionItem({ eventId, index, session }) {
  const [occupancy, setOccupancy] = useState(null)
  const [occupancyUnavailable, setOccupancyUnavailable] = useState(false)

  useEffect(() => {
    let active = true
    getSessionOccupancy(eventId, session.id)
      .then((result) => {
        if (active) setOccupancy(result)
      })
      .catch(() => {
        if (active) setOccupancyUnavailable(true)
      })
    return () => {
      active = false
    }
  }, [eventId, session.id])

  return (
    <li className="session-item">
      <div aria-hidden="true" className="session-index">{String(index + 1).padStart(2, '0')}</div>
      <div className="session-main">
        <div className="session-time">
          <time dateTime={session.starts_at}>{formatEventDate(session.starts_at, 'full')}</time>
          <span aria-hidden="true">—</span>
          <time dateTime={session.ends_at}>{formatEventDate(session.ends_at, 'full')}</time>
        </div>
        <h3>{session.title}</h3>
        {session.description && <p>{session.description}</p>}
        <SessionAvailability
          occupancy={occupancy}
          sessionCapacity={session.capacity}
          unavailable={occupancyUnavailable}
        />
      </div>
      <EventArtwork title={session.title} variant="session" />
    </li>
  )
}

/** Render the current availability state with text as well as a decorative star. */
function SessionAvailability({ occupancy, sessionCapacity, unavailable }) {
  const availability = getSessionAvailability(occupancy, unavailable, sessionCapacity)

  return (
    <div aria-live="polite" className="session-capacity">
      <span className={`availability-badge availability-${availability.tone}`} role="status">
        <span aria-hidden="true">✦</span>
        {availability.label}
      </span>
      {availability.detail && <span className="session-availability-detail">{availability.detail}</span>}
    </div>
  )
}
