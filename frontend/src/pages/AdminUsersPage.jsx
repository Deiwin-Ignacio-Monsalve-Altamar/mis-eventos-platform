/** Let administrators search the user directory and promote attendees. */

import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { listUsers, promoteUserToOrganizer } from '../api/admin.js'
import { EmptyMessage, ErrorMessage, LoadingMessage } from '../components/RequestFeedback.jsx'
import PaginationControls from '../components/PaginationControls.jsx'
import useAppState from '../state/useAppState.js'

const PAGE_SIZE = 20
const ROLE_LABELS = { ATTENDEE: 'Asistente', ORGANIZER: 'Organizador', ADMIN: 'Administrador' }

/** Render a server-paginated directory; role changes remain backend-authorized. */
export default function AdminUsersPage() {
  const { clearAuthentication } = useAppState()
  const [searchParams, setSearchParams] = useSearchParams()
  const [searchDraft, setSearchDraft] = useState(searchParams.get('q') || '')
  const [resultState, setResultState] = useState(null)
  const [requestError, setRequestError] = useState(null)
  const [busyUserId, setBusyUserId] = useState(null)
  const [notice, setNotice] = useState('')
  const [retry, setRetry] = useState(0)
  const pendingPromotion = useRef(false)
  const page = Math.max(1, Number(searchParams.get('page')) || 1)
  const query = searchParams.get('q') || ''
  const requestKey = `${page}:${query}:${retry}`
  const result = resultState?.key === requestKey ? resultState.data : null
  const loadError = resultState?.key === requestKey ? resultState.error : null

  useEffect(() => {
    let active = true
    listUsers({ page, pageSize: PAGE_SIZE, query })
      .then((data) => {
        if (active) setResultState({ key: requestKey, data, error: null })
      })
      .catch((error) => {
        if (!active) return
        if (error.status === 401) clearAuthentication()
        setResultState({ key: requestKey, data: null, error })
      })
    return () => { active = false }
  }, [page, query, requestKey, clearAuthentication])

  function updateQuery(event) {
    event.preventDefault()
    setRequestError(null)
    const next = new URLSearchParams()
    const normalized = searchDraft.trim()
    if (normalized) next.set('q', normalized)
    setSearchParams(next)
  }

  async function promote(user) {
    if (pendingPromotion.current || user.role !== 'ATTENDEE') return
    if (!window.confirm(`¿Promover a ${user.first_name} ${user.last_name} a organizador?`)) return
    pendingPromotion.current = true
    setBusyUserId(user.id)
    setRequestError(null)
    setNotice('')
    try {
      const updatedUser = await promoteUserToOrganizer(user.id)
      setResultState((current) => current?.key === requestKey
        ? { ...current, data: { ...current.data, users: current.data.users.map((item) => item.id === updatedUser.id ? updatedUser : item) } }
        : current)
      setNotice(`${updatedUser.first_name} ${updatedUser.last_name} ahora es organizador.`)
    } catch (error) {
      if (error.status === 401) clearAuthentication()
      setRequestError(error)
    } finally {
      pendingPromotion.current = false
      setBusyUserId(null)
    }
  }

  const error = requestError || loadError

  return (
    <section aria-labelledby="admin-users-heading" className="organizer-page admin-users-page">
      <header className="organizer-page-heading">
        <div><p className="eyebrow">Administración</p><h1 id="admin-users-heading">Usuarios y roles</h1>
          <p>Consulta las cuentas y habilita a asistentes para organizar eventos.</p></div>
      </header>
      <form className="organizer-filters admin-users-search" onSubmit={updateQuery}>
        <label htmlFor="admin-users-query">Buscar por nombre o correo
          <input autoComplete="off" id="admin-users-query" onChange={(event) => setSearchDraft(event.target.value)} value={searchDraft} />
        </label>
        <button className="button button-primary" type="submit">Buscar</button>
      </form>
      {notice && <p aria-live="polite" className="feedback feedback-success" role="status">{notice}</p>}
      {error && <><ErrorMessage error={error} />{error.status !== 401 && <button className="button button-secondary" onClick={() => { setRequestError(null); setRetry((value) => value + 1) }} type="button">Intentar de nuevo</button>}</>}
      {!result && !error && <LoadingMessage>Cargando usuarios…</LoadingMessage>}
      {result?.users.length === 0 && <EmptyMessage>{query ? 'No encontramos usuarios con esa búsqueda.' : 'Todavía no hay usuarios para mostrar.'}</EmptyMessage>}
      {result?.users.length > 0 && <div aria-label="Usuarios registrados" className="admin-user-list">
        {result.users.map((user) => (
          <article className="admin-user-card" key={user.id}>
            <div className="admin-user-identity"><h2>{user.first_name} {user.last_name}</h2><p>{user.email}</p></div>
            <span className={`admin-role-badge admin-role-${user.role.toLowerCase()}`}>{ROLE_LABELS[user.role] || user.role}</span>
            {user.role === 'ATTENDEE' && <button className="button button-secondary" disabled={busyUserId !== null} onClick={() => promote(user)} type="button">{busyUserId === user.id ? 'Promoviendo…' : 'Promover a organizador'}</button>}
          </article>
        ))}
      </div>}
      <PaginationControls disabled={!result || busyUserId !== null} itemLabel="usuarios" onPageChange={(nextPage) => { const next = new URLSearchParams(searchParams); next.set('page', String(nextPage)); setSearchParams(next) }} pagination={result?.pagination} />
    </section>
  )
}
