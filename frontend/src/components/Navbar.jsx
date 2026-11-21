import { Link, NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, LogOut, Ticket } from 'lucide-react'
import { useAuth } from '../auth'

export function Logo() {
  return (
    <span className="logo">
      <svg viewBox="0 0 64 64" width="30" height="30" aria-hidden="true">
        <rect width="64" height="64" rx="14" fill="#2B3BE5" />
        <path d="M14 22h36v6a4 4 0 0 0 0 8v6H14v-6a4 4 0 0 0 0-8z" fill="#FFC933" />
        <path d="M42 22v20" stroke="#2B3BE5" strokeWidth="2.5" strokeDasharray="3 3" />
      </svg>
      <span>EventHub</span>
    </span>
  )
}

export default function Navbar() {
  const { user, isAdmin, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <header className="nav">
      <div className="container nav-inner">
        <Link to="/" aria-label="EventHub home">
          <Logo />
        </Link>
        <nav className="nav-links" aria-label="Main">
          <NavLink to="/" end>Discover</NavLink>
          {user && (
            <NavLink to="/tickets">
              <Ticket size={16} /> My tickets
            </NavLink>
          )}
          {isAdmin && (
            <NavLink to="/admin">
              <LayoutDashboard size={16} /> Organiser
            </NavLink>
          )}
        </nav>
        <div className="nav-user">
          {user ? (
            <>
              <span className="avatar" title={user.email}>{user.name.slice(0, 1).toUpperCase()}</span>
              <span className="nav-name">{user.name.split(' ')[0]}</span>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => { logout(); navigate('/') }}
              >
                <LogOut size={15} /> Sign out
              </button>
            </>
          ) : (
            <>
              <Link className="btn btn-ghost btn-sm" to="/signin">Sign in</Link>
              <Link className="btn btn-primary btn-sm" to="/signup">Create account</Link>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
