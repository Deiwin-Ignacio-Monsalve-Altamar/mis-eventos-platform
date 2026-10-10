/** Keep the event registration status independent from event capacity data. */

export const initialRegistrationState = {
  eventKey: null,
  status: 'checking',
  registered: false,
  error: null,
}

/** Apply persisted registration checks and API action results to view state. */
export function registrationReducer(state, action) {
  if (action.type !== 'check/start'
    && action.eventKey !== undefined
    && action.eventKey !== state.eventKey) return state

  switch (action.type) {
    case 'check/start':
      return { eventKey: action.eventKey, status: 'checking', registered: false, error: null }
    case 'check/complete':
      return {
        ...state,
        status: 'idle',
        registered: action.registration?.status === 'registered',
        error: null,
      }
    case 'check/failure':
      return { ...state, status: 'check-error', registered: false, error: action.error || null }
    case 'register/start':
      return { ...state, status: 'loading', registered: false, error: null }
    case 'register/success':
      return { ...state, status: 'success', registered: true, error: null }
    case 'register/duplicate':
      return { ...state, status: 'duplicate', registered: true, error: null }
    case 'register/failure':
      return { ...state, status: 'error', registered: false, error: action.error }
    case 'cancel/start':
      return { ...state, status: 'cancelling', registered: true, error: null }
    case 'cancel/success':
      return { ...state, status: 'cancelled', registered: false, error: null }
    case 'cancel/failure':
      return { ...state, status: 'error', registered: true, error: action.error }
    default:
      return state
  }
}
