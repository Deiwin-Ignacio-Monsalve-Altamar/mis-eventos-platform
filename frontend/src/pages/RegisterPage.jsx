/** Register a new account through the public authentication endpoint. */

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout.jsx'
import AuthErrorMessage from '../components/AuthErrorMessage.jsx'
import useAppState from '../state/useAppState.js'
import { validateRegistration } from './authValidation.js'

/** Submit account details and present the API's validation feedback. */
export default function RegisterPage() {
  const { signUp } = useAppState()
  const navigate = useNavigate()
  const [error, setError] = useState(null)
  const [fieldError, setFieldError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)
    const account = {
      email: formData.get('email'),
      password: formData.get('password'),
      first_name: formData.get('first_name'),
      last_name: formData.get('last_name'),
    }
    const validationError = validateRegistration(account)
    setError(null)
    setFieldError(validationError)
    if (validationError) return

    setSubmitting(true)
    try {
      await signUp(account)
      navigate('/login', { replace: true, state: { registrationComplete: true } })
    } catch (requestError) {
      setError(requestError)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout variant="register">
      <section aria-labelledby="register-heading" className="auth-panel">
        <p className="eyebrow">Sé parte de la comunidad</p>
        <h1 id="register-heading">Crea tu cuenta</h1>
        <p className="auth-intro">Empieza a descubrir encuentros que vale la pena recordar.</p>
        <AuthErrorMessage error={error} />
        <form className="app-form" onSubmit={handleSubmit}>
          <label htmlFor="register-first-name">
            Nombre
            <input aria-describedby={fieldError?.field === 'first_name' ? 'register-field-error' : undefined} aria-invalid={fieldError?.field === 'first_name'} autoComplete="given-name" id="register-first-name" maxLength={100} name="first_name" required />
          </label>
          <label htmlFor="register-last-name">
            Apellido
            <input aria-describedby={fieldError?.field === 'last_name' ? 'register-field-error' : undefined} aria-invalid={fieldError?.field === 'last_name'} autoComplete="family-name" id="register-last-name" maxLength={100} name="last_name" required />
          </label>
          <label htmlFor="register-email">
            Correo electrónico
            <input aria-describedby={fieldError?.field === 'email' ? 'register-field-error' : undefined} aria-invalid={fieldError?.field === 'email'} autoComplete="email" id="register-email" maxLength={320} name="email" required type="email" />
          </label>
          <label htmlFor="register-password">
            Contraseña
            <input aria-describedby={fieldError?.field === 'password' ? 'register-field-error' : undefined} aria-invalid={fieldError?.field === 'password'} autoComplete="new-password" id="register-password" maxLength={128} minLength={8} name="password" required type="password" />
          </label>
          {fieldError && <p className="field-error" id="register-field-error" role="alert">{fieldError.message}</p>}
          <button aria-busy={submitting} className="button button-primary auth-submit" disabled={submitting} type="submit">
            {submitting ? 'Creando cuenta…' : 'Crear cuenta'}
          </button>
        </form>
        <p className="form-footnote">
          ¿Ya tienes cuenta? <Link to="/login">Inicia sesión</Link>
        </p>
      </section>
    </AuthLayout>
  )
}
