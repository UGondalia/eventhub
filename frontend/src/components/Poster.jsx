import { useState } from 'react'
import {
  Briefcase, Cpu, GraduationCap, Music2, Palette, Trophy, UtensilsCrossed, Users,
} from 'lucide-react'

// Each category gets its own colour pair and icon. A pattern variant is picked from
// the event id, so every event has a stable, slightly different poster when the
// organiser has not uploaded an image.
const THEME = {
  Technology: { bg: '#2B3BE5', ink: '#A8B3FF', pop: '#FFC933', Icon: Cpu },
  Music: { bg: '#FF5A4E', ink: '#FFB4AE', pop: '#101328', Icon: Music2 },
  Business: { bg: '#101328', ink: '#4A5080', pop: '#FFC933', Icon: Briefcase },
  Sports: { bg: '#00A389', ink: '#8FE6D3', pop: '#101328', Icon: Trophy },
  Arts: { bg: '#B8327E', ink: '#F2A6CF', pop: '#FFC933', Icon: Palette },
  Food: { bg: '#FF8A1F', ink: '#FFC98F', pop: '#101328', Icon: UtensilsCrossed },
  Education: { bg: '#1F6FB5', ink: '#9CCBF0', pop: '#FFC933', Icon: GraduationCap },
  Community: { bg: '#3F9A2E', ink: '#B5E8A8', pop: '#101328', Icon: Users },
}

function hash(text) {
  let h = 0
  for (let i = 0; i < text.length; i++) h = (h * 31 + text.charCodeAt(i)) >>> 0
  return h
}

function Pattern({ variant, ink, pop }) {
  switch (variant) {
    case 0:
      return (
        <g fill="none" stroke={ink} strokeWidth="2" opacity="0.7">
          {[40, 80, 120, 160, 200].map((r) => <circle key={r} cx="330" cy="40" r={r} />)}
          <circle cx="330" cy="40" r="22" fill={pop} stroke="none" opacity="1" />
        </g>
      )
    case 1:
      return (
        <g stroke={ink} strokeWidth="10" opacity="0.55">
          {Array.from({ length: 14 }).map((_, i) => (
            <line key={i} x1={i * 40 - 120} y1="260" x2={i * 40 + 20} y2="-20" />
          ))}
          <circle cx="70" cy="70" r="28" fill={pop} stroke="none" opacity="1" />
        </g>
      )
    case 2:
      return (
        <g fill={ink} opacity="0.75">
          {Array.from({ length: 8 }).map((_, r) =>
            Array.from({ length: 14 }).map((__, c) => (
              <circle key={`${r}-${c}`} cx={20 + c * 30} cy={16 + r * 30} r={r + c > 12 ? 3 : 4.5} />
            )),
          )}
          <rect x="250" y="130" width="110" height="110" rx="24" fill={pop} opacity="1" />
        </g>
      )
    default:
      return (
        <g>
          <circle cx="90" cy="190" r="130" fill={ink} opacity="0.55" />
          <circle cx="300" cy="60" r="90" fill={ink} opacity="0.4" />
          <circle cx="215" cy="150" r="34" fill={pop} />
        </g>
      )
  }
}

export default function Poster({ event, children, className = '' }) {
  const [broken, setBroken] = useState(false)
  const theme = THEME[event.category] || THEME.Community
  const { Icon } = theme

  return (
    <div className={`poster ${className}`} style={{ background: theme.bg }}>
      {event.image && !broken ? (
        <img src={event.image} alt="" className="poster-img" onError={() => setBroken(true)} />
      ) : (
        <>
          <svg viewBox="0 0 400 240" preserveAspectRatio="xMidYMid slice" className="poster-art" aria-hidden="true">
            <Pattern variant={hash(event.id) % 4} ink={theme.ink} pop={theme.pop} />
          </svg>
          <Icon className="poster-icon" size={92} strokeWidth={1.3} color="#fff" aria-hidden="true" />
        </>
      )}
      {children}
    </div>
  )
}
