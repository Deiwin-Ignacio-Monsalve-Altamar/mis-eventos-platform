/** Store shared authentication and event data for the route tree. */

import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
} from 'react'
import { getCurrentUser, login, logout, registerAccount } from '../api/auth.js'
import {
  createEvent,
  deleteEvent,
  getEvent,
  listEventSessions,
  listEvents,
  updateEvent,
} from '../api/events.js'
import AppStateContext from './AppStateContext.js'
import { appReducer, initialState } from './appReducer.js'

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

  const signOut = useCallback(async () => {
    await logout()
    dispatch({ type: 'auth/logout-success' })
  }, [])

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
      eventsRequestId.current += 1
      eventRequestId.current += 1
      dispatch({ type: 'event-creation/success', event })
      return event
    } catch (error) {
      dispatch({ type: 'event-creation/error', error })
      throw error
    }
  }, [])

  const saveEventChanges = useCallback(async (eventId, eventData) => {
    dispatch({ type: 'event-updating/loading' })
    try {
      const event = await updateEvent(eventId, eventData)
      eventsRequestId.current += 1
      eventRequestId.current += 1
      dispatch({ type: 'event-updating/success', event })
      return event
    } catch (error) {
      dispatch({ type: 'event-updating/error', error })
      throw error
    }
  }, [])

  const removeEvent = useCallback(async (eventId) => {
    dispatch({ type: 'event-deleting/loading' })
    try {
      await deleteEvent(eventId)
      eventsRequestId.current += 1
      eventRequestId.current += 1
      sessionsRequestId.current += 1
      dispatch({ type: 'event-deleting/success', eventId })
    } catch (error) {
      dispatch({ type: 'event-deleting/error', error })
      throw error
    }
  }, [])

  const value = useMemo(
    () => ({ state, signIn, signUp, signOut, refreshEvents, loadEvent, loadEventSessions, submitEvent, saveEventChanges, removeEvent }),
    [state, signIn, signUp, signOut, refreshEvents, loadEvent, loadEventSessions, submitEvent, saveEventChanges, removeEvent],
  )

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>
}

