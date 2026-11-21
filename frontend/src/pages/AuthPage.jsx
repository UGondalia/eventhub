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
  const { login, signup: doSignup } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  const submit = async (e, creds) => {
    e?.preventDefault()
    setBusy(true)
    setError('')
    try {
      const user = signup && !creds
        ? await doSignup(form.name, form.email, form.password)
        : await login(creds?.email || form.email, creds?.password || form.password)
      toast(`Welcome${signup && !creds ? '' : ' back'}, ${user.name.split(' ')[0]}.`)
      navigate(location.state?.from || (user.role === 'admin' ? '/admin' : '/'), { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth">
      <div className="auth-side">
        <Logo />
        <h2>Your seat is one form away.</h2>
        <p>Create an account to book events, keep every ticket in one place and get reminders before the day.</p>
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
      </div>

      <form className="auth-form" onSubmit={submit}>
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
          {signup && <small>At least 8 characters.</small>}
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
      </form>
    </div>
  )
}
