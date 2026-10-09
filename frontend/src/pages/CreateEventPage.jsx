/** Provide a small event creation form backed by the documented event API. */

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ErrorMessage } from '../components/RequestFeedback.jsx'
import useAppState from '../state/useAppState.js'

/** Validate basic required fields and submit an event for the current user. */
export default function CreateEventPage() {
  const { state, submitEvent } = useAppState()
  const navigate = useNavigate()
  const [formError, setFormError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setFormError(null)
    setSubmitting(true)
    const formData = new FormData(event.currentTarget)
    try {
      const newEvent = await submitEvent({
        title: formData.get('title'),
        description: formData.get('description') || null,
        location: formData.get('location') || null,
        starts_at: toUtc(formData.get('starts_at')),
        ends_at: toUtc(formData.get('ends_at')),
        capacity: Number(formData.get('capacity')),
        status: formData.get('status'),
      })
      if (!newEvent) {
        setFormError(state.eventCreation.error)
        return
      }
      navigate(`/events/${newEvent.id}`)
    } catch (error) {
      setFormError(error)
    } finally {
      setSubmitting(false)
    }
  }

  if (state.auth.status === 'loading') {
    return <p aria-live="polite">Checking your sign-in status…</p>
  }
  if (state.auth.status !== 'authenticated') {
    return (
      <section className="content-panel">
        <h1>Sign in to create an event</h1>
        <p>Event creation is available to authenticated users.</p>
        {state.auth.status === 'error' && <ErrorMessage error={state.auth.error} />}
        <Link className="button button-primary" to="/login">Sign in</Link>
      </section>
    )
  }

  return (
    <section className="form-panel">
      <p className="eyebrow">Share something worth attending</p>
      <h1>Create event</h1>
      <ErrorMessage error={formError || state.eventCreation.error} />
      <form className="app-form" onSubmit={handleSubmit}>
        <label>
          Event title
          <input autoComplete="off" maxLength="200" name="title" required />
        </label>
        <label>
          Description
          <textarea name="description" rows="4" />
        </label>
        <label>
          Location
          <input maxLength="255" name="location" />
        </label>
        <div className="form-columns">
          <label>
            Starts at
            <input name="starts_at" required type="datetime-local" />
          </label>
          <label>
            Ends at
            <input name="ends_at" required type="datetime-local" />
          </label>
        </div>
        <div className="form-columns">
          <label>
            Capacity
            <input min="1" name="capacity" required type="number" />
          </label>
          <label>
            Status
            <select defaultValue="draft" name="status">
              <option value="draft">Draft</option>
              <option value="published">Published</option>
            </select>
          </label>
        </div>
        <button className="button button-primary" disabled={submitting} type="submit">
          {submitting ? 'Creating…' : 'Create event'}
        </button>
      </form>
    </section>
  )
}

/** Convert a local date-time input to the ISO 8601 UTC form expected by the API. */
function toUtc(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    throw new Error('Enter a valid date and time.')
  }
  return date.toISOString()
}
