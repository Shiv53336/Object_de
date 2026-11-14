import { useState } from 'react'
import Icon from '../components/Icon.jsx'
import { formatDay, toHHMM } from '../lib/dates.js'
import { currentStreak, stepsForDay } from '../lib/stats.js'
import { useStore } from '../lib/store.js'

export default function Home() {
  const { state, dispatch, today, now, permission, askForNotifications } = useStore()
  const steps = stepsForDay(state, today)
  const ticked = state.log[today] || {}
  const doneCount = steps.filter((s) => ticked[s.key]).length
  const pct = steps.length ? Math.round((doneCount / steps.length) * 100) : 0
  const streak = currentStreak(state, today)

  const nowTime = toHHMM(now)
  const open = steps.filter((s) => !ticked[s.key])
  const next = open.find((s) => s.time >= nowTime) || open[0]

  return (
    <main className="screen">
      <header className="home-header">
        <div>
          <div className="muted">{formatDay(today)}</div>
          <h1>Today</h1>
        </div>
        <a href="#/progress" className="pill pill-strong">
          <Icon name="flame" />
          {streak} day streak
        </a>
      </header>

      {steps.length === 0 ? (
        <EmptyDay hasPlans={state.plans.some((p) => !p.archived)} />
      ) : (
        <>
          <div className="progress-block">
            <div className="progress-labels">
              <div>
                {doneCount} of {steps.length} steps done
              </div>
              <div>{pct}%</div>
            </div>
            <div className="bar" role="img" aria-label={`${pct}% of today's steps done`}>
              <div className="bar-fill accent" style={{ width: `${pct}%` }} />
            </div>
          </div>

          <div className="card card-strong up-next">
            {next ? (
              <>
                <div className="grow">
                  <div className="eyebrow">{next.time >= nowTime ? `Up next at ${next.time}` : `Still open from ${next.time}`}</div>
                  <div className="card-title">{next.name}</div>
                </div>
                <div className="reminder-state">
                  <Icon name={next.reminder ? 'bell' : 'bellOff'} />
                  {next.reminder ? 'Reminder on' : 'No reminder'}
                </div>
              </>
            ) : (
              <div className="grow">
                <div className="eyebrow">All done</div>
                <div className="card-title">Every step ticked off today</div>
              </div>
            )}
          </div>

          {permission === 'default' && steps.some((s) => s.reminder) && (
            <button type="button" className="notice" onClick={askForNotifications}>
              <Icon name="bell" />
              Allow notifications to get your reminders
            </button>
          )}

          <h2 className="section-label">Your steps today</h2>
        </>
      )}

      <div className="step-list">
        {steps.map((step) => {
          const done = Boolean(ticked[step.key])
          return (
            <div className="step" key={step.key}>
              <button
                type="button"
                className="check-button"
                role="checkbox"
                aria-checked={done}
                aria-label={step.name}
                onClick={() => dispatch({ type: 'toggleStep', date: today, key: step.key })}
              >
                <span className="check">{done && <Icon name="check" size={16} strokeWidth={3} />}</span>
              </button>
              <div className="grow">
                <div className={done ? 'step-name done' : 'step-name'}>{step.name}</div>
                <div className="step-label">{step.label}</div>
              </div>
              <div className="step-time">{step.time}</div>
              {step.adhocId && (
                <button
                  type="button"
                  className="icon-button small"
                  aria-label={`Remove ${step.name}`}
                  onClick={() => dispatch({ type: 'removeAdhoc', date: today, id: step.adhocId })}
                >
                  <Icon name="close" size={16} />
                </button>
              )}
            </div>
          )
        })}
        <AddStep defaultTime={nowTime} onAdd={(name, time) => dispatch({ type: 'addAdhoc', date: today, name, time })} />
      </div>
    </main>
  )
}

function EmptyDay({ hasPlans }) {
  return (
    <div className="empty">
      <div className="card-title">{hasPlans ? 'Nothing planned for today' : 'No plans yet'}</div>
      <div className="muted">
        {hasPlans ? 'Enjoy the rest day, or add a one-off step below.' : 'Pick a ready-made plan or create your own to fill your day.'}
      </div>
      <a href="#/plans" className="button-primary">
        Browse plans
      </a>
    </div>
  )
}

function AddStep({ defaultTime, onAdd }) {
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState('')
  const [time, setTime] = useState(defaultTime)

  if (!adding) {
    return (
      <button
        type="button"
        className="dashed-button"
        onClick={() => {
          setTime(defaultTime)
          setAdding(true)
        }}
      >
        <Icon name="plus" />
        Add a step for today
      </button>
    )
  }

  const submit = (e) => {
    e.preventDefault()
    if (!name.trim() || !time) return
    onAdd(name.trim(), time)
    setName('')
    setAdding(false)
  }

  return (
    <form className="add-step" onSubmit={submit}>
      <div className="add-step-row">
        <input
          className="field grow"
          type="text"
          placeholder="What do you want to do?"
          aria-label="Step name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
        />
        <input className="time" type="time" aria-label="Time" value={time} onChange={(e) => setTime(e.target.value)} required />
      </div>
      <div className="add-step-row">
        <button type="button" className="button-outline grow" onClick={() => setAdding(false)}>
          Cancel
        </button>
        <button type="submit" className="button-primary grow" disabled={!name.trim()}>
          Add step
        </button>
      </div>
    </form>
  )
}
