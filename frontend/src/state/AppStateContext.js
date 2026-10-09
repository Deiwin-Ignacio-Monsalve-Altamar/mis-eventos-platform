/** Share the application state provider between state and hook modules. */

import { createContext } from 'react'

const AppStateContext = createContext(null)

export default AppStateContext
