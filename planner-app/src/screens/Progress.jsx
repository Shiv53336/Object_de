import Icon from '../components/Icon.jsx'
import { addDays, DAY_LETTERS, weekday } from '../lib/dates.js'
import { bestStreak, currentStreak, dayStatus, planProgress } from '../lib/stats.js'
import { useStore } from '../lib/store.js'

const WEEKS = 4

export default function Progress() {
  const { state, today } = useStore()
  const streak = currentStreak(state, today)
  const best = bestStreak(state, today)

  // Four full Monday–Sunday rows, ending with the current week.
  const firstCell = addDays(today, -weekday(today) - (WEEKS - 1) * 7)
  const cells = Array.from({ length: WEEKS * 7 }, (_, i) => {
    const key = addDays(firstCell, i)
    return { key, status: dayStatus(state, key, today), isToday: key === today }
  })
  const count = (status) => cells.filter((c) => c.status === status).length
  const summary = `Last four weeks: ${count('done')} days done, ${count('missed')} missed.`

  const plans = state.plans.filter((p) => !p.archived)

  return (
    <main className="screen">
      <header className="page-header">
        <h1>Progress</h1>
      </header>

      <div className="sections">
        <div className="card card-strong streak-card">
          <div className="streak-number">{streak}</div>
          <div className="grow">
            <div className="card-title">day streak</div>
            <div className="muted">Best so far: {best} {best === 1 ? 'day' : 'days'}</div>
          </div>
          <Icon name="flame" size={32} strokeWidth={1.5} />
        </div>

        <section className="field-group">
          <h2 className="section-label">Last 4 weeks</h2>
          <div className="calendar letters" aria-hidden="true">
            {DAY_LETTERS.map((letter, i) => (
              <div key={i}>{letter}</div>
            ))}
          </div>
          <div className="calendar" role="img" aria-label={summary}>
            {cells.map((cell) => (
              <div key={cell.key} className={`cell ${cell.status === 'today' ? 'open' : cell.status}${cell.isToday ? ' is-today' : ''}`} />
            ))}
          </div>
          <div className="legend">
            <div><span className="swatch done" />Done</div>
            <div><span className="swatch missed" />Missed</div>
            <div><span className="swatch is-today" />Today</div>
            <div><span className="swatch rest" />Nothing due</div>
          </div>
        </section>

        <section>
          <h2 className="section-label">By plan</h2>
          {plans.length === 0 && (
            <div className="empty">
              <div className="muted">Start a plan to see how you are doing.</div>
              <a href="#/plans" className="button-primary">
                Browse plans
              </a>
            </div>
          )}
          {plans.map((plan) => {
            const p = planProgress(plan, state, today)
            return (
              <div className="plan-progress" key={plan.id}>
                <div className="progress-labels strong">
                  <div className="setting-title">{plan.name}</div>
                  <div className="muted">{p.label}</div>
                </div>
                <div className="bar" role="img" aria-label={`${plan.name}: ${p.label}`}>
                  <div className="bar-fill" style={{ width: `${p.pct}%` }} />
                </div>
              </div>
            )
          })}
        </section>
      </div>
    </main>
  )
}
