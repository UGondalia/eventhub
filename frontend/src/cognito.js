// Amazon Cognito sign-in (used only when VITE_COGNITO_* are set at build time).
// Locally these are empty, `enabled` is false and the app uses the Python /auth endpoints.
import {
  AuthenticationDetails, CognitoUser, CognitoUserAttribute, CognitoUserPool,
} from 'amazon-cognito-identity-js'

const POOL_ID = import.meta.env.VITE_COGNITO_USER_POOL_ID
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID

export const enabled = Boolean(POOL_ID && CLIENT_ID)
const pool = enabled ? new CognitoUserPool({ UserPoolId: POOL_ID, ClientId: CLIENT_ID }) : null

const MESSAGES = {
  UsernameExistsException: 'An account with this email already exists. Sign in instead.',
  NotAuthorizedException: 'Email or password is incorrect.',
  UserNotFoundException: 'Email or password is incorrect.',
  UserNotConfirmedException: 'Confirm your email first. Enter the code we sent you.',
  CodeMismatchException: 'That code is not correct. Check it and try again.',
  ExpiredCodeException: 'That code has expired. Choose “Send a new code”.',
  InvalidPasswordException: 'Password needs 8+ characters with upper and lower case letters, a number and a symbol.',
  LimitExceededException: 'Too many attempts. Wait a minute and try again.',
  TooManyRequestsException: 'Too many attempts. Wait a minute and try again.',
}

function fail(err) {
  const error = new Error(MESSAGES[err?.code] || err?.message || 'Something went wrong. Try again.')
  error.code = err?.code
  return error
}

const user = (email) => new CognitoUser({ Username: email, Pool: pool })

export const signUp = (name, email, password) =>
  new Promise((resolve, reject) =>
    pool.signUp(
      email, password,
      [
        new CognitoUserAttribute({ Name: 'email', Value: email }),
        new CognitoUserAttribute({ Name: 'name', Value: name }),
      ],
      null,
      (err, result) => (err ? reject(fail(err)) : resolve(result)),
    ),
  )

export const confirmSignUp = (email, code) =>
  new Promise((resolve, reject) =>
    user(email).confirmRegistration(code, true, (err) => (err ? reject(fail(err)) : resolve())),
  )

export const resendCode = (email) =>
  new Promise((resolve, reject) =>
    user(email).resendConfirmationCode((err) => (err ? reject(fail(err)) : resolve())),
  )

export const signIn = (email, password) =>
  new Promise((resolve, reject) =>
    user(email).authenticateUser(new AuthenticationDetails({ Username: email, Password: password }), {
      onSuccess: (session) => resolve(session.getIdToken().getJwtToken()),
      onFailure: (err) => reject(fail(err)),
      newPasswordRequired: () => reject(new Error('This account needs a new password. Sign up with a new email instead.')),
    }),
  )

// Returns a valid ID token (refreshing it silently when needed) or null when signed out.
export const getIdToken = () =>
  new Promise((resolve) => {
    const current = pool?.getCurrentUser()
    if (!current) return resolve(null)
    current.getSession((err, session) => resolve(!err && session?.isValid() ? session.getIdToken().getJwtToken() : null))
  })

export const signOut = () => pool?.getCurrentUser()?.signOut()

// Display only. The server decides what the user may do from the verified token.
export function userFromToken(token) {
  const part = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
  const claims = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(part), (c) => c.charCodeAt(0))))
  const groups = claims['cognito:groups'] || []
  return {
    id: claims.sub,
    email: claims.email,
    name: claims.name || claims.email,
    role: groups.includes('admin') ? 'admin' : 'participant',
  }
}
