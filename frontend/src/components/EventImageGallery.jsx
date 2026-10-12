/** Show a stable, accessible gallery or the established empty event state. */
export default function EventImageGallery({ event }) {
  const images = [...(event.images || [])]
    .filter((image) => image.position !== 0)
    .sort((left, right) => left.position - right.position)

  if (event.images?.some((image) => image.position === 0) && images.length === 0) return null

  return (
    <section aria-labelledby="event-gallery-heading" className="event-gallery">
      <h2 id="event-gallery-heading">Otras imágenes</h2>
      {images.length ? (
        <div className="event-image-grid">
          {images.map((image, index) => (
            <img alt={`${event.title}, imagen ${index + 1}`} key={`${image.position}-${image.url}`} src={image.url} />
          ))}
        </div>
      ) : <p className="event-gallery-empty">La organización aún no ha agregado imágenes a este evento.</p>}
    </section>
  )
}
