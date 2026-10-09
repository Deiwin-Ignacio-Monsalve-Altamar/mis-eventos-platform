/** Store shared authentication and event data for the route tree. */

import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
} from 'react'
import { getCurrentUser, login, registerAccount } from '../api/auth.js'
import {
  createEvent,
  getEvent,
  listEventSessions,
  listEvents,
} from '../api/events.js'
import AppStateContext from './AppStateContext.js'

const initialState = {
  auth: { user: null, status: 'loading', error: null },
  events: { items: [], pagination: null, status: 'idle', error: null },
  selectedEvent: {
    event: null,
    status: 'idle',
    error: null,
    sessions: [],
    sessionsStatus: 'idle',
    sessionsError: null,
  },
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
          query: action.query,
          page: action.page,
          pageSize: action.pageSize,
          status: 'success',
          error: null,
        },
      }
    case 'events/error':
      return { ...state, events: { ...state.events, status: 'error', error: action.error } }
    case 'selected-event/loading':
      return {
        ...state,
        selectedEvent: {
          event: null,
          status: 'loading',
          error: null,
          sessions: [],
          sessionsStatus: 'idle',
          sessionsError: null,
        },
      }
    case 'selected-event/success':
      return { ...state, selectedEvent: { ...state.selectedEvent, event: action.event, status: 'success', error: null } }
    case 'selected-event/error':
      return { ...state, selectedEvent: { ...state.selectedEvent, event: null, status: 'error', error: action.error } }
    case 'selected-event/sessions-loading':
      return { ...state, selectedEvent: { ...state.selectedEvent, sessions: [], sessionsStatus: 'loading', sessionsError: null } }
    case 'selected-event/sessions-success':
      return { ...state, selectedEvent: { ...state.selectedEvent, sessions: action.sessions, sessionsStatus: 'success', sessionsError: null } }
    case 'selected-event/sessions-error':
      return { ...state, selectedEvent: { ...state.selectedEvent, sessions: [], sessionsStatus: 'error', sessionsError: action.error } }
    case 'event-creation/loading':
      return { ...state, eventCreation: { status: 'loading', error: null } }
    case 'event-creation/success':
      return {
        ...state,
        events: {
          ...state.events,
          items: [action.event, ...state.events.items.filter((item) => item.id !== action.event.id)],
        },
        selectedEvent: {
          event: action.event,
          status: 'success',
          error: null,
          sessions: [],
          sessionsStatus: 'idle',
          sessionsError: null,
        },
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
  const eventsRequestId = useRef(0)
  const eventRequestId = useRef(0)
  const sessionsRequestId = useRef(0)

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

  const refreshEvents = useCallback(async ({ query = '', page = 1, pageSize = 9 } = {}) => {
    const requestId = ++eventsRequestId.current
    dispatch({ type: 'events/loading' })
    try {
      const result = await listEvents({ query, page, pageSize })
      if (requestId !== eventsRequestId.current) return
      dispatch({
        type: 'events/success',
        events: result.events,
        pagination: result.pagination,
        query,
        page,
        pageSize,
      })
    } catch (error) {
      if (requestId === eventsRequestId.current) dispatch({ type: 'events/error', error })
    }
  }, [])

  const loadEvent = useCallback(async (eventId) => {
    const requestId = ++eventRequestId.current
    dispatch({ type: 'selected-event/loading' })
    try {
      const event = await getEvent(eventId)
      if (requestId !== eventRequestId.current) return
      dispatch({ type: 'selected-event/success', event })
    } catch (error) {
      if (requestId === eventRequestId.current) dispatch({ type: 'selected-event/error', error })
    }
  }, [])

  const loadEventSessions = useCallback(async (eventId) => {
    const requestId = ++sessionsRequestId.current
    dispatch({ type: 'selected-event/sessions-loading' })
    try {
      const sessions = await listEventSessions(eventId)
      if (requestId !== sessionsRequestId.current) return
      dispatch({ type: 'selected-event/sessions-success', sessions })
    } catch (error) {
      if (requestId === sessionsRequestId.current) {
        dispatch({ type: 'selected-event/sessions-error', error })
      }
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
    () => ({ state, signIn, signUp, refreshEvents, loadEvent, loadEventSessions, submitEvent }),
    [state, signIn, signUp, refreshEvents, loadEvent, loadEventSessions, submitEvent],
  )

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>
}

