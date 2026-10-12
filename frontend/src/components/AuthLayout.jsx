/** Provide the shared editorial split composition for authentication screens. */

import { useState } from 'react'
import { Link } from 'react-router-dom'

const editorialImageUrl =
  'https://images.unsplash.com/photo-1506157786151-b8491531f063?auto=format&fit=crop&fm=jpg&q=85&w=1800'

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
          <Link aria-label="Mis Eventos" className="auth-story-brand" to="/events">
            <svg aria-hidden="true" className="auth-story-ticket" fill="none" viewBox="0 0 32 32">
              <path d="M7 6.5h18a2.5 2.5 0 0 1 2.5 2.5v4a3 3 0 0 0 0 6v4a2.5 2.5 0 0 1-2.5 2.5H7A2.5 2.5 0 0 1 4.5 23v-4a3 3 0 0 0 0-6V9A2.5 2.5 0 0 1 7 6.5Z" stroke="currentColor" strokeWidth="2" />
              <path d="M19 8.5v3m0 3v3m0 3v3" stroke="currentColor" strokeDasharray="1 1" strokeLinecap="round" strokeWidth="2" />
            </svg>
            <span className="auth-story-brand-name">Mis Eventos</span><span className="auth-story-brand-dot">.</span>
          </Link>
          <div aria-hidden="true" className="auth-story-confetti auth-story-confetti-one" />
          <div aria-hidden="true" className="auth-story-confetti auth-story-confetti-two" />
          <div className="auth-story-message">
            <p className="auth-story-kicker"><span /> Tu próximo gran plan</p>
            <h2>Los grandes momentos empiezan aquí</h2>
            <p>Descubre eventos, organiza experiencias y gestiona cada detalle desde un solo lugar</p>
          </div>
          <p className="auth-story-mantra"><span>01</span> Descubre <i /> <span>02</span> Organiza <i /> <span>03</span> Comparte</p>
        </div>
      </aside>
      <section aria-label="Acceso a tu cuenta" className="auth-form-side">
        {children}
      </section>
    </div>
  )
}
