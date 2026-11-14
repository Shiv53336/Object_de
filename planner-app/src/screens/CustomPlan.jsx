import { useState } from 'react'
import { BackHeader, DayPicker, Stepper, Toggle } from '../components/Controls.jsx'
import Icon from '../components/Icon.jsx'
import { addDays } from '../lib/dates.js'
import { INTERVALS, intervalLabel, intervalTimes, spreadTimes } from '../lib/schedule.js'
import { go, uid, useStore } from '../lib/store.js'

const ALL_DAYS = [true, true, true, true, true, true, true]
const MAX_TIMES_A_DAY = 12

const MODES = [
  { id: 'interval', label: 'Every few hours' },
  { id: 'count', label: 'Times a day' },
  { id: 'times', label: 'Set times' },
]

const makePresets = (today) => ({
  water: { label: 'Drink water', name: 'Drink water', mode: 'interval', every: 60, from: '09:00', to: '21:00', days: ALL_DAYS },
  face: { label: 'Wash face', name: 'Wash face', mode: 'count', count: 2, from: '07:00', to: '22:00', days: ALL_DAYS },
  interview: {
    label: 'Interview prep',
    name: 'Interview prep',
    mode: 'times',
    days: [true, true, true, true, true, true, false],
    endDate: addDays(today, 28),
    steps: [
      { name: 'Coding practice', time: '07:00' },
      { name: 'System design reading', time: '20:00' },
      { name: 'Mock interview', time: '21:00' },
    ],
  },
})

const fromPreset = (id, preset) => ({
  preset: id,
  every: 60,
  count: 5,
  from: '09:00',
  to: '21:00',
  endDate: '',
  counts: true,
  ...preset,
  days: [...preset.days],
  steps: (preset.steps || []).map((s) => ({ ...s, id: uid() })),
})

export default function CustomPlan() {
  const { dispatch, today, askForNotifications } = useStore()
  const [presets] = useState(() => makePresets(today))
  const [form, setForm] = useState(() => fromPreset('water', presets.water))
  const set = (patch) => setForm((f) => ({ ...f, ...patch }))

  const setMode = (mode) => {
    // "Set times" needs at least one row to fill in.
    const steps = mode === 'times' && form.steps.length === 0 ? [{ id: uid(), name: form.name, time: '09:00' }] : form.steps
    set({ mode, steps })
  }
  const setStep = (id, patch) => set({ steps: form.steps.map((s) => (s.id === id ? { ...s, ...patch } : s)) })

  const times =
    form.mode === 'interval'
      ? intervalTimes(form.from, form.to, form.every)
      : form.mode === 'count'
        ? spreadTimes(form.from, form.to, form.count)
        : []
  const namedSteps = form.steps.filter((s) => s.name.trim() && s.time)
  const windowInvalid = form.mode !== 'times' && times.length === 0
  const hasSteps = form.mode === 'times' ? namedSteps.length > 0 : times.length > 0
  const canSave = form.name.trim() && hasSteps && form.days.some(Boolean)

  const save = () => {
    const name = form.name.trim()
    const steps =
      form.mode === 'times'
        ? namedSteps.map((s) => ({ id: s.id, name: s.name.trim(), time: s.time, reminder: true }))
        : times.map((time) => ({ id: uid(), name, time, reminder: true }))
    dispatch({
      type: 'savePlan',
      plan: {
        id: uid(),
        templateId: null,
        name,
        category: name,
        startDate: today,
        endDate: form.mode === 'times' && form.endDate ? form.endDate : null,
        days: form.days,
        steps,
        streakAlert: false,
        countsForStreak: form.counts,
      },
    })
    askForNotifications()
    go('#/')
  }

  const everyIndex = INTERVALS.indexOf(form.every)

  return (
    <main className="screen">
      <BackHeader title="Create your own plan" />

      <div className="form">
        <div className="field-group">
          <div className="section-label">Start from an example</div>
          <div className="chips tight">
            {Object.entries(presets).map(([id, preset]) => (
              <button key={id} type="button" className="chip" aria-pressed={form.preset === id} onClick={() => setForm(fromPreset(id, preset))}>
                {preset.label}
              </button>
            ))}
          </div>
        </div>

        <label className="field-group">
          <span className="section-label">Plan name</span>
          <input className="field" type="text" value={form.name} onChange={(e) => set({ name: e.target.value })} />
        </label>

        <div className="field-group">
          <div className="section-label">How should we remind you?</div>
          <div className="segments">
            {MODES.map((m) => (
              <button key={m.id} type="button" className="segment" aria-pressed={form.mode === m.id} onClick={() => setMode(m.id)}>
                {m.label}
              </button>
            ))}
          </div>
        </div>

        {form.mode === 'interval' && (
          <div className="card panel">
            <div className="panel-row">
              <div className="setting-title">Remind every</div>
              <Stepper
                value={intervalLabel(form.every)}
                lessLabel="Shorter gap"
                moreLabel="Longer gap"
                canLess={everyIndex > 0}
                canMore={everyIndex < INTERVALS.length - 1}
                onLess={() => set({ every: INTERVALS[everyIndex - 1] })}
                onMore={() => set({ every: INTERVALS[everyIndex + 1] })}
              />
            </div>
            <TimeWindow form={form} set={set} />
            <div className="muted">
              {windowInvalid ? 'Pick an end time later than the start time.' : `${times.length} reminders a day, none outside these hours.`}
            </div>
          </div>
        )}

        {form.mode === 'count' && (
          <div className="card panel">
            <div className="panel-row">
              <div className="setting-title">Times a day</div>
              <Stepper
                value={form.count}
                lessLabel="Fewer times"
                moreLabel="More times"
                canLess={form.count > 1}
                canMore={form.count < MAX_TIMES_A_DAY}
                onLess={() => set({ count: form.count - 1 })}
                onMore={() => set({ count: form.count + 1 })}
              />
            </div>
            <TimeWindow form={form} set={set} />
            {windowInvalid ? (
              <div className="muted">Pick an end time later than the start time.</div>
            ) : (
              <>
                <div className="muted">Spread evenly. Reminders will arrive at:</div>
                <div className="time-tags">
                  {times.map((t, i) => (
                    <div className="time-tag" key={i}>
                      {t}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {form.mode === 'times' && (
          <div className="card panel">
            <div>
              {form.steps.map((step) => (
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
                  <button
                    type="button"
                    className="icon-button small"
                    aria-label={`Remove ${step.name || 'step'}`}
                    disabled={form.steps.length === 1}
                    onClick={() => set({ steps: form.steps.filter((s) => s.id !== step.id) })}
                  >
                    <Icon name="close" size={16} />
                  </button>
                </div>
              ))}
            </div>
            <button
              type="button"
              className="dashed-button short"
              onClick={() => set({ steps: [...form.steps, { id: uid(), name: '', time: form.steps.at(-1)?.time || '09:00' }] })}
            >
              <Icon name="plus" />
              Add a step
            </button>
            <label className="panel-row">
              <span>
                <span className="setting-title">Ends on</span>
                <span className="step-label">{form.preset === 'interview' ? 'Your interview day' : 'Leave empty to keep going'}</span>
              </span>
              <input className="time" type="date" min={today} value={form.endDate} onChange={(e) => set({ endDate: e.target.value })} />
            </label>
          </div>
        )}

        <div className="field-group">
          <div className="section-label">Repeat on</div>
          <DayPicker days={form.days} onChange={(days) => set({ days })} />
        </div>

        <div className="setting">
          <div className="grow">
            <div className="setting-title">Count towards my streak</div>
            <div className="step-label">Turn off for reminders you only want as nudges</div>
          </div>
          <Toggle checked={form.counts} label="Count towards my streak" onChange={(counts) => set({ counts })} />
        </div>

        <div className="form-footer">
          <button type="button" className="button-primary big" disabled={!canSave} onClick={save}>
            Save plan
          </button>
        </div>
      </div>
    </main>
  )
}

function TimeWindow({ form, set }) {
  return (
    <div className="panel-row">
      <div className="setting-title">Between</div>
      <div className="between">
        <input className="time" type="time" aria-label="From" value={form.from} onChange={(e) => e.target.value && set({ from: e.target.value })} />
        <span className="muted">to</span>
        <input className="time" type="time" aria-label="Until" value={form.to} onChange={(e) => e.target.value && set({ to: e.target.value })} />
      </div>
    </div>
  )
}
