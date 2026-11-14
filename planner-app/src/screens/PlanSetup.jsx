import { useState } from 'react'
import { BackHeader, DayPicker, Toggle } from '../components/Controls.jsx'
import Icon from '../components/Icon.jsx'
import { addDays } from '../lib/dates.js'
import { STREAK_ALERT_TIME } from '../lib/reminders.js'
import { go, uid, useStore } from '../lib/store.js'
import { durationLabel, TEMPLATES } from '../lib/templates.js'

/** Builds the editable draft: a fresh plan from a template, or a copy of an existing plan. */
function makeDraft(mode, id, plans, today) {
  if (mode === 'edit') {
    const plan = plans.find((p) => p.id === id && !p.archived)
    return plan ? { ...plan, weeks: null } : null
  }
  const t = TEMPLATES.find((x) => x.id === id)
  if (!t) return null
  return {
    id: uid(),
    templateId: t.id,
    name: t.name,
    category: t.category,
    weeks: t.weeks,
    startDate: today,
    endDate: null,
    days: [...t.days],
    steps: t.steps.map((s) => ({ ...s, id: uid() })),
    streakAlert: true,
    countsForStreak: true,
  }
}

export default function PlanSetup({ mode, id }) {
  const { state, dispatch, today, askForNotifications } = useStore()
  const [draft, setDraft] = useState(() => makeDraft(mode, id, state.plans, today))
  const editing = mode === 'edit'

  if (!draft) {
    return (
      <main className="screen">
        <BackHeader title="Plan not found" />
        <div className="form">
          <div className="muted">This plan is no longer available.</div>
          <a href="#/plans" className="button-primary">
            Back to plans
          </a>
        </div>
      </main>
    )
  }

  const set = (patch) => setDraft((d) => ({ ...d, ...patch }))
  const setStep = (stepId, patch) => set({ steps: draft.steps.map((s) => (s.id === stepId ? { ...s, ...patch } : s)) })
  const addStep = () => {
    const last = draft.steps.at(-1)
    // Steps added to a running plan only apply from today, so earlier days stay as they were.
    const step = { id: uid(), name: '', time: last?.time || '08:00', reminder: true, ...(editing && { addedOn: today }) }
    set({ steps: [...draft.steps, step] })
  }

  const namedSteps = draft.steps.filter((s) => s.name.trim() && s.time)
  const canSave = namedSteps.length > 0 && draft.days.some(Boolean) && draft.startDate

  const save = () => {
    const { weeks, ...plan } = draft
    plan.steps = namedSteps.map((s) => ({ ...s, name: s.name.trim() }))
    if (!editing && weeks) plan.endDate = addDays(plan.startDate, weeks * 7 - 1)
    dispatch({ type: 'savePlan', plan })
    if (plan.streakAlert || plan.steps.some((s) => s.reminder)) askForNotifications()
    go('#/')
  }

  const remove = () => {
    if (!window.confirm(`Remove "${draft.name}"? Days you already completed stay in your progress.`)) return
    dispatch({ type: 'removePlan', id: draft.id, today })
    go('#/plans')
  }

  const subtitle = editing
    ? `${draft.category} · ${draft.endDate ? 'Has an end date' : 'Ongoing'}`
    : `${draft.category} · ${durationLabel(draft.weeks)}`

  return (
    <main className="screen">
      <BackHeader title={editing ? 'Edit plan' : 'Set up plan'} />

      <div className="form">
        <div>
          <h1 className="plan-title">{draft.name}</h1>
          <div className="muted">{subtitle}</div>
        </div>

        <label className="field-group">
          <span className="section-label">Start date</span>
          <input className="field" type="date" value={draft.startDate} onChange={(e) => set({ startDate: e.target.value })} required />
        </label>

        <div className="field-group">
          <div className="section-label">Repeat on</div>
          <DayPicker days={draft.days} onChange={(days) => set({ days })} />
        </div>

        <div>
          <div className="row-labels section-label">
            <div>Steps and times</div>
            <div>Reminder</div>
          </div>
          {draft.steps.map((step) => (
            <div className="setup-step" key={step.id}>
              <input
                className="step-input grow"
                type="text"
                placeholder="Step name"
                aria-label="Step name"
                value={step.name}
                onChange={(e) => setStep(step.id, { name: e.target.value })}
              />
              <input
                className="time"
                type="time"
                aria-label={`Time for ${step.name || 'new step'}`}
                value={step.time}
                onChange={(e) => setStep(step.id, { time: e.target.value })}
              />
              <Toggle checked={step.reminder} label={`Reminder for ${step.name || 'new step'}`} onChange={(reminder) => setStep(step.id, { reminder })} />
              <button
                type="button"
                className="icon-button small"
                aria-label={`Remove ${step.name || 'step'}`}
                disabled={draft.steps.length === 1}
                onClick={() => set({ steps: draft.steps.filter((s) => s.id !== step.id) })}
              >
                <Icon name="close" size={16} />
              </button>
            </div>
          ))}
        </div>

        <button type="button" className="dashed-button" onClick={addStep}>
          <Icon name="plus" />
          Add a step
        </button>

        <div className="setting">
          <div className="grow">
            <div className="setting-title">Streak-at-risk alert</div>
            <div className="step-label">One nudge at {STREAK_ALERT_TIME} if steps are still open</div>
          </div>
          <Toggle checked={draft.streakAlert} label="Streak-at-risk alert" onChange={(streakAlert) => set({ streakAlert })} />
        </div>

        <div className="form-footer">
          <button type="button" className="button-primary big" disabled={!canSave} onClick={save}>
            {editing ? 'Save changes' : 'Start plan'}
          </button>
          {editing && (
            <button type="button" className="button-text" onClick={remove}>
              Remove plan
            </button>
          )}
        </div>
      </div>
    </main>
  )
}
