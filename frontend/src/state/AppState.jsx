/** Store shared authentication and event data for the route tree. */

import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
} from 'react'
import { getCurrentUser, login, registerAccount } from '../api/auth.js'
import { createEvent, getEvent, listEvents } from '../api/events.js'
import AppStateContext from './AppStateContext.js'

const initialState = {
  auth: { user: null, status: 'loading', error: null },
  events: { items: [], pagination: null, status: 'idle', error: null },
  selectedEvent: { event: null, status: 'idle', error: null },
  eventCreation: { status: 'idle', error: null },
}

/** Apply one shared state transition without mutating existing state. */
function appReducer(state, action) {
  switch (action.type) {
    case 'auth/loading':
      return { ...state, auth: { user: null, status: 'loading', error: null } }
    case 'auth/success':
      return { ...state, auth: { user: action.user, status: 'authenticated', error: null } }
    case 'auth/anonymous':
      return { ...state, auth: { user: null, status: 'anonymous', error: null } }
    case 'auth/error':
      return { ...state, auth: { user: null, status: 'error', error: action.error } }
    case 'events/loading':
      return { ...state, events: { ...state.events, status: 'loading', error: null } }
    case 'events/success':
      return {
        ...state,
        events: {
          items: action.events,
          pagination: action.pagination,
          status: 'success',
          error: null,
        },
      }
    case 'events/error':
      return { ...state, events: { ...state.events, status: 'error', error: action.error } }
    case 'selected-event/loading':
      return { ...state, selectedEvent: { event: null, status: 'loading', error: null } }
    case 'selected-event/success':
      return { ...state, selectedEvent: { event: action.event, status: 'success', error: null } }
    case 'selected-event/error':
      return { ...state, selectedEvent: { event: null, status: 'error', error: action.error } }
    case 'event-creation/loading':
      return { ...state, eventCreation: { status: 'loading', error: null } }
    case 'event-creation/success':
      return {
        ...state,
        events: {
          ...state.events,
          items: [action.event, ...state.events.items.filter((item) => item.id !== action.event.id)],
        },
        selectedEvent: { event: action.event, status: 'success', error: null },
        eventCreation: { status: 'success', error: null },
      }
    case 'event-creation/error':
      return { ...state, eventCreation: { status: 'error', error: action.error } }
    default:
      return state
  }
}

/** Provide shared state and API-backed actions to every application route. */
export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(appReducer, initialState)

  useEffect(() => {
    let active = true
    getCurrentUser()
      .then((user) => {
        if (active) dispatch({ type: 'auth/success', user })
      })
      .catch((error) => {
        if (!active) return
        dispatch({
          type: error.status === 401 ? 'auth/anonymous' : 'auth/error',
          error,
        })
      })
    return () => {
      active = false
    }
  }, [])

  const signIn = useCallback(async (credentials) => {
    dispatch({ type: 'auth/loading' })
    try {
      const user = await login(credentials)
      dispatch({ type: 'auth/success', user })
      return user
    } catch (error) {
      dispatch({ type: 'auth/error', error })
      throw error
    }
  }, [])

  const signUp = useCallback((account) => registerAccount(account), [])

  const refreshEvents = useCallback(async (query = '') => {
    dispatch({ type: 'events/loading' })
    try {
      const result = await listEvents({ query })
      dispatch({ type: 'events/success', events: result.events, pagination: result.pagination })
    } catch (error) {
      dispatch({ type: 'events/error', error })
    }
  }, [])

  const loadEvent = useCallback(async (eventId) => {
    dispatch({ type: 'selected-event/loading' })
    try {
      const event = await getEvent(eventId)
      dispatch({ type: 'selected-event/success', event })
    } catch (error) {
      dispatch({ type: 'selected-event/error', error })
    }
  }, [])

  const submitEvent = useCallback(async (eventData) => {
    dispatch({ type: 'event-creation/loading' })
    try {
      const event = await createEvent(eventData)
      dispatch({ type: 'event-creation/success', event })
      return event
    } catch (error) {
      dispatch({ type: 'event-creation/error', error })
      return null
    }
  }, [])

  const value = useMemo(
    () => ({ state, signIn, signUp, refreshEvents, loadEvent, submitEvent }),
    [state, signIn, signUp, refreshEvents, loadEvent, submitEvent],
  )

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>
}

