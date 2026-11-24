import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { useToast } from '../toast'
import { Logo } from '../components/Navbar'

const DEMOS = [
  { label: 'Try as participant', email: 'user@eventhub.test', password: 'User@1234' },
  { label: 'Try as organiser', email: 'admin@eventhub.test', password: 'Admin@123' },
]

export default function AuthPage({ mode }) {
  const signup = mode === 'signup'
  const { login, signup: doSignup, confirm, resendCode, cognitoEnabled } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [code, setCode] = useState('')
  const [awaitingCode, setAwaitingCode] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  const finish = (user, isNew) => {
    toast(`Welcome${isNew ? '' : ' back'}, ${user.name.split(' ')[0]}.`)
    navigate(location.state?.from || (user.role === 'admin' ? '/admin' : '/'), { replace: true })
  }

  const submit = async (e, creds) => {
    e?.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (awaitingCode) {
        finish(await confirm(form.email, code.trim(), form.password), true)
      } else if (signup && !creds) {
        const res = await doSignup(form.name, form.email, form.password)
        if (res.needsConfirm) {
          setAwaitingCode(true)
          toast(`We emailed a 6-digit code to ${form.email}.`)
        } else {
          finish(res.user, true)
        }
      } else {
        finish(await login(creds?.email || form.email, creds?.password || form.password), false)
      }
    } catch (err) {
      if (err.code === 'UserNotConfirmedException') setAwaitingCode(true)
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const sendAgain = async () => {
    try {
      await resendCode(form.email)
      toast('A new code is on its way.')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="auth">
      <div className="auth-side">
        <Logo />
        <h2>Your seat is one form away.</h2>
        <p>Create an account to book events, keep every ticket in one place and get reminders before the day.</p>
        {!cognitoEnabled && (
          <div className="demo-box">
            <p>Looking around? Skip the form.</p>
            <div>
              {DEMOS.map((d) => (
                <button key={d.email} className="btn btn-sun btn-sm" onClick={() => submit(null, d)} disabled={busy}>
                  {d.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <form className="auth-form" onSubmit={submit}>
        {awaitingCode ? (
          <>
            <h1>Check your email</h1>
            <p className="switch">Enter the 6-digit code we sent to <strong>{form.email}</strong>.</p>
            <label>
              Confirmation code
              <input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                inputMode="numeric"
                autoComplete="one-time-code"
                required
                minLength={6}
              />
            </label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="btn btn-primary btn-block btn-lg" disabled={busy}>
              {busy ? 'One moment…' : 'Confirm email'}
            </button>
            <button type="button" className="btn btn-link" onClick={sendAgain}>Send a new code</button>
          </>
        ) : (
          <>
            <h1>{signup ? 'Create your account' : 'Sign in'}</h1>
            {signup && (
              <label>
                Full name
                <input value={form.name} onChange={set('name')} autoComplete="name" required minLength={2} />
              </label>
            )}
            <label>
              Email
              <input type="email" value={form.email} onChange={set('email')} autoComplete="email" required />
            </label>
            <label>
              Password
              <input
                type="password"
                value={form.password}
                onChange={set('password')}
                autoComplete={signup ? 'new-password' : 'current-password'}
                required
                minLength={signup ? 8 : 1}
              />
              {signup && (
                <small>
                  {cognitoEnabled
                    ? 'At least 8 characters with upper and lower case letters, a number and a symbol.'
                    : 'At least 8 characters.'}
                </small>
              )}
            </label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="btn btn-primary btn-block btn-lg" disabled={busy}>
              {busy ? 'One moment…' : signup ? 'Create account' : 'Sign in'}
            </button>
            <p className="switch">
              {signup ? 'Already have an account?' : 'New to EventHub?'}{' '}
              <Link to={signup ? '/signin' : '/signup'} state={location.state}>
                {signup ? 'Sign in' : 'Create an account'}
              </Link>
            </p>
          </>
        )}
      </form>
    </div>
  )
}
