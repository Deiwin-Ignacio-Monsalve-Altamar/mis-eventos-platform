/** Register a new account through the public authentication endpoint. */

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ErrorMessage } from '../components/RequestFeedback.jsx'
import useAppState from '../state/useAppState.js'

/** Submit account details and present the API's validation feedback. */
export default function RegisterPage() {
  const { signUp } = useAppState()
  const [error, setError] = useState(null)
  const [registered, setRegistered] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    const formData = new FormData(event.currentTarget)
    try {
      await signUp({
        email: formData.get('email'),
        password: formData.get('password'),
        first_name: formData.get('first_name'),
        last_name: formData.get('last_name'),
      })
      setRegistered(true)
    } catch (requestError) {
      setError(requestError)
    } finally {
      setSubmitting(false)
    }
  }

  if (registered) {
    return (
      <section className="content-panel form-panel-narrow">
        <p className="eyebrow">You are all set</p>
        <h1>Account created</h1>
        <p>You can now sign in with your new account.</p>
        <Link className="button button-primary" to="/login">Continue to sign in</Link>
      </section>
    )
  }

  return (
    <section className="form-panel form-panel-narrow">
      <p className="eyebrow">Join the community</p>
      <h1>Create an account</h1>
      <ErrorMessage error={error} />
      <form className="app-form" onSubmit={handleSubmit}>
        <label>
          First name
          <input autoComplete="given-name" name="first_name" required />
        </label>
        <label>
          Last name
          <input autoComplete="family-name" name="last_name" required />
        </label>
        <label>
          Email
          <input autoComplete="email" name="email" required type="email" />
        </label>
        <label>
          Password
          <input autoComplete="new-password" name="password" required type="password" />
        </label>
        <button className="button button-primary" disabled={submitting} type="submit">
          {submitting ? 'Creating account…' : 'Create account'}
        </button>
      </form>
      <p className="form-footnote">
        Already registered? <Link to="/login">Sign in</Link>
      </p>
    </section>
  )
}
