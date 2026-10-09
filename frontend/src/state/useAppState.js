/** Expose shared application state and actions to React components. */

import { useContext } from 'react'
import AppStateContext from './AppStateContext.js'

/** Return the shared state value or throw when used outside its provider. */
export default function useAppState() {
  const context = useContext(AppStateContext)
  if (context === null) {
    throw new Error('useAppState must be used inside AppProvider.')
  }
  return context
}
