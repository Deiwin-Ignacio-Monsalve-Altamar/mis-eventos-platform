/** Authenticate a user and let the backend maintain its HttpOnly cookie. */

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ErrorMessage } from '../components/RequestFeedback.jsx'
import useAppState from '../state/useAppState.js'

/** Submit login credentials without persisting them in browser storage. */
export default function LoginPage() {
  const { state, signIn } = useAppState()
  const navigate = useNavigate()
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setSubmitting(true)
    const formData = new FormData(event.currentTarget)
    try {
      await signIn({
        email: formData.get('email'),
        password: formData.get('password'),
      })
      navigate('/profile')
    } catch {
      // The provider stores the shared authentication error for display.
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="form-panel form-panel-narrow">
      <p className="eyebrow">Welcome back</p>
      <h1>Sign in</h1>
      <ErrorMessage error={state.auth.error} />
      <form className="app-form" onSubmit={handleSubmit}>
        <label>
          Email
          <input autoComplete="email" name="email" required type="email" />
        </label>
        <label>
          Password
          <input autoComplete="current-password" name="password" required type="password" />
        </label>
        <button className="button button-primary" disabled={submitting} type="submit">
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <p className="form-footnote">
        New to Mis Eventos? <Link to="/register">Create an account</Link>
      </p>
    </section>
  )
}
