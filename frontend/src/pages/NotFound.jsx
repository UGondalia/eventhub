import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="container section empty">
      <h1>Page not found</h1>
      <p>That page doesn’t exist, or the link is out of date.</p>
      <Link className="btn btn-primary" to="/">Back to events</Link>
    </div>
  )
}
