/** Authenticate a user and let the backend maintain its HttpOnly cookie. */

import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout.jsx'
import AuthErrorMessage from '../components/AuthErrorMessage.jsx'
import useAppState from '../state/useAppState.js'
import { validateLogin } from './authValidation.js'

/** Submit login credentials without persisting them in browser storage. */
export default function LoginPage() {
  const { state, signIn } = useAppState()
  const navigate = useNavigate()
  const location = useLocation()
  const [submitting, setSubmitting] = useState(false)
  const [fieldError, setFieldError] = useState(null)

  async function handleSubmit(event) {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)
    const credentials = {
      email: formData.get('email'),
      password: formData.get('password'),
    }
    const validationError = validateLogin(credentials)
    setFieldError(validationError)
    if (validationError) return

    setSubmitting(true)
    try {
      await signIn(credentials)
      navigate('/profile', { replace: true })
    } catch {
      // The provider stores the shared authentication error for display.
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout>
      <section aria-labelledby="login-heading" className="auth-panel">
        <p className="eyebrow">Tu cuenta</p>
        <h1 id="login-heading">¡Qué bueno verte!</h1>
        <p className="auth-intro">Ingresa para descubrir eventos y tener tus planes siempre a mano.</p>
        {location.state?.registrationComplete && <p className="feedback feedback-success" role="status">Tu cuenta está lista. Inicia sesión para continuar.</p>}
        <AuthErrorMessage error={state.auth.error} />
        <form className="app-form" onSubmit={handleSubmit}>
          <label htmlFor="login-email">
            Correo electrónico
            <input aria-describedby={fieldError?.field === 'email' ? 'login-field-error' : undefined} aria-invalid={fieldError?.field === 'email'} autoComplete="email" id="login-email" maxLength={320} name="email" required type="email" />
          </label>
          <label htmlFor="login-password">
            Contraseña
            <input aria-describedby={fieldError?.field === 'password' ? 'login-field-error' : undefined} aria-invalid={fieldError?.field === 'password'} autoComplete="current-password" id="login-password" name="password" required type="password" />
          </label>
          {fieldError && <p className="field-error" id="login-field-error" role="alert">{fieldError.message}</p>}
          <button aria-busy={submitting} className="button button-primary auth-submit" disabled={submitting} type="submit">
            {submitting ? 'Ingresando…' : 'Iniciar sesión'}
          </button>
        </form>
        <p className="form-footnote">
          ¿Aún no tienes cuenta? <Link to="/register">Crear una cuenta</Link>
        </p>
      </section>
    </AuthLayout>
  )
}
