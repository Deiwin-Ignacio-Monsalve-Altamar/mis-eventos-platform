/** Define shared application state and cache transitions for authentication and events. */

export const initialState = {
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
  eventMutation: { status: 'idle', error: null },
}

/** Apply one shared state transition without mutating existing state. */
export function appReducer(state, action) {
  switch (action.type) {
    case 'auth/loading':
      return { ...state, auth: { user: null, status: 'loading', error: null } }
    case 'auth/success':
      return { ...state, auth: { user: action.user, status: 'authenticated', error: null } }
    case 'auth/anonymous':
      return { ...state, auth: { user: null, status: 'anonymous', error: null } }
    case 'auth/logout-success':
      return {
        ...initialState,
        auth: { user: null, status: 'anonymous', error: null },
      }
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
    case 'event-creation/success': {
      const alreadyInResults = state.events.items.some((item) => item.id === action.event.id)
      const matchesQuery = eventMatchesQuery(action.event, state.events.query)
      const total = state.events.pagination
        ? state.events.pagination.total + (!alreadyInResults && matchesQuery ? 1 : 0)
        : null
      const canUpdateCurrentPage = (state.events.page || 1) === 1 || alreadyInResults
      const items = matchesQuery && canUpdateCurrentPage
        ? sortEvents([action.event, ...state.events.items.filter((item) => item.id !== action.event.id)])
          .slice(0, state.events.pagination?.page_size || state.events.items.length || 9)
        : state.events.items
      return {
        ...state,
        events: {
          ...state.events,
          items,
          pagination: state.events.pagination ? paginationWithTotal(state.events.pagination, total) : null,
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
    }
    case 'event-creation/error':
      return { ...state, eventCreation: { status: 'error', error: action.error } }
    case 'event-updating/loading':
    case 'event-deleting/loading':
      return { ...state, eventMutation: { status: 'loading', error: null } }
    case 'event-updating/success': {
      const oldEvent = state.selectedEvent.event
        || state.events.items.find((item) => item.id === action.event.id)
      const wasInResults = state.events.items.some((item) => item.id === action.event.id)
      const previouslyMatched = oldEvent && eventMatchesQuery(oldEvent, state.events.query)
      const nowMatches = eventMatchesQuery(action.event, state.events.query)
      let total = state.events.pagination?.total ?? null
      if (state.events.pagination && previouslyMatched !== nowMatches) {
        total = Math.max(0, total + (nowMatches ? 1 : -1))
      }
      let items = state.events.items.filter((item) => item.id !== action.event.id)
      if (nowMatches && (wasInResults || (state.events.page || 1) === 1)) {
        items = sortEvents([action.event, ...items])
          .slice(0, state.events.pagination?.page_size || state.events.items.length || 9)
      }
      return {
        ...state,
        events: {
          ...state.events,
          items,
          pagination: state.events.pagination ? paginationWithTotal(state.events.pagination, total) : null,
        },
        selectedEvent: { ...state.selectedEvent, event: action.event, status: 'success', error: null },
        eventMutation: { status: 'success', error: null },
      }
    }
    case 'event-updating/error':
    case 'event-deleting/error':
      return { ...state, eventMutation: { status: 'error', error: action.error } }
    case 'event-deleting/success': {
      const removedEvent = state.events.items.find((item) => item.id === action.eventId)
        || (state.selectedEvent.event?.id === action.eventId ? state.selectedEvent.event : null)
      const removedFromResult = removedEvent && eventMatchesQuery(removedEvent, state.events.query)
      const total = state.events.pagination
        ? Math.max(0, state.events.pagination.total - (removedFromResult ? 1 : 0))
        : null
      return {
        ...state,
        events: {
          ...state.events,
          items: state.events.items.filter((item) => item.id !== action.eventId),
          pagination: state.events.pagination
            ? paginationWithTotal(state.events.pagination, total)
            : null,
        },
        selectedEvent: state.selectedEvent.event?.id === action.eventId
          ? { event: null, status: 'error', error: { status: 404, code: 'not_found' }, sessions: [], sessionsStatus: 'idle', sessionsError: null }
          : state.selectedEvent,
        eventMutation: { status: 'success', error: null },
      }
    }
    default:
      return state
  }
}

/** Recalculate page metadata after the cached result count changes. */
function paginationWithTotal(pagination, total) {
  return { ...pagination, total, total_pages: Math.ceil(total / pagination.page_size) }
}

/** Keep cached event cards in the stable order used by the backend listing. */
function sortEvents(events) {
  return [...events].sort((first, second) => {
    const startsAtDifference = Date.parse(first.starts_at) - Date.parse(second.starts_at)
    return startsAtDifference || first.id - second.id
  })
}

/** Check whether a cached event still matches the active catalogue search. */
function eventMatchesQuery(event, query = '') {
  if (!query) return true
  const normalizedQuery = query.trim().toLocaleLowerCase()
  return [event?.title, event?.description, event?.location]
    .some((value) => String(value || '').toLocaleLowerCase().includes(normalizedQuery))
}
