/** Render a branded decorative fallback where event-specific imagery is absent. */

/** Show an abstract brand mark without implying it depicts the real event. */
export default function EventArtwork({ title = 'Evento', variant = 'card' }) {
  const initials = title
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0])
    .join('')
    .toUpperCase()

  return (
    <div aria-hidden="true" className={`event-artwork event-artwork-${variant}`}>
      <span className="event-artwork-orbit" />
      <span className="event-artwork-initials">{initials || 'ME'}</span>
      <span className="event-artwork-wordmark">Mis Eventos</span>
    </div>
  )
}
