import { DAY_LETTERS, DAY_NAMES } from '../lib/dates.js'
import Icon from './Icon.jsx'

export function Toggle({ checked, onChange, label }) {
  return (
    <button type="button" className="toggle" role="switch" aria-checked={checked} aria-label={label} onClick={() => onChange(!checked)}>
      <span className="toggle-track">
        <span className="toggle-knob" />
      </span>
    </button>
  )
}

export function DayPicker({ days, onChange }) {
  return (
    <div className="days">
      {DAY_NAMES.map((name, i) => (
        <button
          key={name}
          type="button"
          className="day"
          aria-label={name}
          aria-pressed={days[i]}
          onClick={() => onChange(days.map((on, j) => (j === i ? !on : on)))}
        >
          {DAY_LETTERS[i]}
        </button>
      ))}
    </div>
  )
}

export function Stepper({ value, onLess, onMore, lessLabel, moreLabel, canLess = true, canMore = true }) {
  return (
    <div className="stepper">
      <button type="button" className="square" aria-label={lessLabel} disabled={!canLess} onClick={onLess}>
        <Icon name="minus" />
      </button>
      <div className="stepper-value" aria-live="polite">{value}</div>
      <button type="button" className="square" aria-label={moreLabel} disabled={!canMore} onClick={onMore}>
        <Icon name="plus" />
      </button>
    </div>
  )
}

export function BackHeader({ title, href = '#/plans' }) {
  return (
    <header className="back-header">
      <a href={href} className="icon-button" aria-label="Back to plans">
        <Icon name="back" size={22} />
      </a>
      <div className="back-title">{title}</div>
    </header>
  )
}
