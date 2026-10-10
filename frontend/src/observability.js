/** Capture browser errors and performance locally without exporting private data. */

const REPORTED_API_ERRORS = new WeakSet()
const OBSERVABILITY_EVENTS = Object.freeze({
  errors: 'mis_eventos_frontend_errors_total',
  apiErrors: 'mis_eventos_frontend_api_errors_total',
  pageLoad: 'mis_eventos_frontend_page_load_duration_seconds',
  apiDuration: 'mis_eventos_frontend_api_request_duration_seconds',
  webVitals: 'mis_eventos_frontend_web_vitals',
})

/** Write a bounded, credential-free telemetry event to the browser console. */
function emit(eventName, values = {}, level = 'debug') {
  const payload = {
    event: eventName,
    timestamp: new Date().toISOString(),
    severity: level.toUpperCase(),
    service: 'mis-eventos-frontend',
    environment: import.meta.env?.VITE_APP_ENVIRONMENT || 'local',
    version: import.meta.env?.VITE_APP_VERSION || 'dev',
    ...values,
  }
  console[level](JSON.stringify(payload))
}

/** Record an API error so the global rejection handler does not report it twice. */
export function reportApiError(error, status = null) {
  if (error && typeof error === 'object') REPORTED_API_ERRORS.add(error)
  emit(OBSERVABILITY_EVENTS.apiErrors, {
    error_type: typeof error?.name === 'string' ? error.name.slice(0, 80) : 'Error',
    status_code: Number.isInteger(status) ? status : null,
  }, 'warn')
}

/** Record API duration without including paths, query parameters, or request data. */
export function reportApiDuration(durationSeconds, method = 'GET') {
  emit(OBSERVABILITY_EVENTS.apiDuration, {
    duration_seconds: Number(durationSeconds.toFixed(6)),
    method: /^[A-Z]{1,10}$/.test(method) ? method : 'OTHER',
  })
}

/** Install global browser error, rejection, page-load, and supported Web Vital listeners. */
export function initializeFrontendObservability(targetWindow = window) {
  const handleError = () => {
    emit(OBSERVABILITY_EVENTS.errors, { error_type: 'JavaScriptError' }, 'error')
  }
  const handleRejection = (event) => {
    if (event.reason && REPORTED_API_ERRORS.has(event.reason)) return
    const errorType = typeof event.reason?.name === 'string'
      ? event.reason.name.slice(0, 80)
      : 'UnhandledRejection'
    emit(OBSERVABILITY_EVENTS.errors, { error_type: errorType }, 'error')
  }
  const reportPageLoad = () => {
    const navigation = targetWindow.performance?.getEntriesByType?.('navigation')?.[0]
    if (navigation && Number.isFinite(navigation.duration)) {
      emit(OBSERVABILITY_EVENTS.pageLoad, {
        duration_seconds: Number((navigation.duration / 1000).toFixed(6)),
      })
    }
  }

  targetWindow.addEventListener('error', handleError)
  targetWindow.addEventListener('unhandledrejection', handleRejection)
  if (targetWindow.document?.readyState === 'complete') {
    reportPageLoad()
  } else {
    targetWindow.addEventListener('load', reportPageLoad, { once: true })
  }

  const observers = []
  if (typeof targetWindow.PerformanceObserver === 'function') {
    for (const [entryType, metricName] of [
      ['largest-contentful-paint', 'LCP'],
      ['layout-shift', 'CLS'],
    ]) {
      try {
        const observer = new targetWindow.PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (entryType === 'layout-shift' && entry.hadRecentInput) continue
            const value = entryType === 'largest-contentful-paint'
              ? entry.startTime / 1000
              : entry.value
            emit(OBSERVABILITY_EVENTS.webVitals, {
              metric: metricName,
              value: Number(value.toFixed(6)),
            })
          }
        })
        observer.observe({ type: entryType, buffered: true })
        observers.push(observer)
      } catch {
        // Unsupported entry types are optional browser capabilities.
      }
    }
  }

  return () => {
    targetWindow.removeEventListener('error', handleError)
    targetWindow.removeEventListener('unhandledrejection', handleRejection)
    targetWindow.removeEventListener('load', reportPageLoad)
    for (const observer of observers) observer.disconnect()
  }
}
