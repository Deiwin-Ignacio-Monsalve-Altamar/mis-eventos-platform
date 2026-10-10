/** Expose authentication operations backed by the documented API contract. */

import { request } from './client.js'

/** Create an account and return its public user representation. */
export async function registerAccount(account) {
  const response = await request('/auth/register', {
    method: 'POST',
    body: account,
  })
  return response.user
}

/** Authenticate with credentials and rely on the API's HttpOnly cookie. */
export async function login(credentials) {
  const response = await request('/auth/login', {
    method: 'POST',
    body: credentials,
  })
  return response.user
}

/** Ask the server to expire the authentication cookie. */
export async function logout() {
  return request('/auth/logout', { method: 'POST' })
}

/** Read the current user from the cookie-authenticated profile endpoint. */
export async function getCurrentUser() {
  const response = await request('/auth/me')
  return response.user
}
