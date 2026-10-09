/** Validate authentication form values against the backend account contract. */

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

/** Return the first invalid registration field, or null when all values are valid. */
export function validateRegistration(values) {
  const firstName = values.first_name.trim()
  const lastName = values.last_name.trim()
  const email = values.email.trim()

  if (firstName.length < 1 || firstName.length > 100) {
    return { field: 'first_name', message: 'Escribe tu nombre (entre 1 y 100 caracteres).' }
  }
  if (lastName.length < 1 || lastName.length > 100) {
    return { field: 'last_name', message: 'Escribe tu apellido (entre 1 y 100 caracteres).' }
  }
  if (email.length > 320 || !EMAIL_PATTERN.test(email)) {
    return { field: 'email', message: 'Escribe un correo válido de hasta 320 caracteres.' }
  }
  if (values.password.length < 8 || values.password.length > 128) {
    return { field: 'password', message: 'La contraseña debe tener entre 8 y 128 caracteres.' }
  }
  return null
}

/** Return the first invalid login field, or null when the credentials are present. */
export function validateLogin(values) {
  const email = values.email.trim()
  if (email.length > 320 || !EMAIL_PATTERN.test(email)) {
    return { field: 'email', message: 'Escribe un correo electrónico válido.' }
  }
  if (!values.password) {
    return { field: 'password', message: 'Escribe tu contraseña.' }
  }
  return null
}
