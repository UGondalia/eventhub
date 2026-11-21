import { Logo } from './Navbar'

export default function Footer() {
  return (
    <footer className="footer">
      <div className="container footer-inner">
        <Logo />
        <p>Cloud Computing special assignment. React, Python, DynamoDB and friends on AWS.</p>
      </div>
    </footer>
  )
}
