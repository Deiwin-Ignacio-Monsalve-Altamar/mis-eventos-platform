/** Provide the shared editorial split composition for authentication screens. */

import { useState } from 'react'
import { Link } from 'react-router-dom'

const editorialImageUrl =
  'https://images.unsplash.com/photo-1646265780630-b639fcc8fc28?auto=format&fit=crop&fm=jpg&q=82&w=1800'

/** Render an authentication form beside event photography and brand copy. */
export default function AuthLayout({ children, variant = 'login' }) {
  const [imageUnavailable, setImageUnavailable] = useState(false)

  return (
    <div className={`auth-layout auth-layout-${variant}`}>
      <aside aria-label="Presentación de Mis Eventos" className="auth-story">
        {!imageUnavailable && (
          <img
            alt=""
            aria-hidden="true"
            className="auth-story-image"
            onError={() => setImageUnavailable(true)}
            src={editorialImageUrl}
          />
        )}
        <div aria-hidden="true" className="auth-story-shade" />
        <div className="auth-story-content">
          <Link className="auth-story-brand" to="/events">Mis Eventos<span>.</span></Link>
          <div className="auth-story-message">
            <p className="auth-story-kicker">Haz espacio para una buena historia</p>
            <h2>Los mejores momentos empiezan aquí</h2>
            <p>Descubre eventos, conecta con personas y crea experiencias memorables</p>
          </div>
          <p className="auth-story-mantra">Descubre. Organiza. Comparte.</p>
        </div>
      </aside>
      <section aria-label="Acceso a tu cuenta" className="auth-form-side">
        {children}
      </section>
    </div>
  )
}
