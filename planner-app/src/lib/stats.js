import { addDays, weekday } from './dates.js'

/** Is this plan due on the given day? */
export function isScheduled(plan, key) {
  if (key < plan.startDate) return false
  if (plan.endDate && key > plan.endDate) return false
  return plan.days[weekday(key)]
}

/** Steps of one plan that apply on a day (steps added later don't rewrite history). */
const planSteps = (plan, key) => plan.steps.filter((s) => !s.addedOn || key >= s.addedOn)

/** Every checklist item for a day, sorted by time. */
export function stepsForDay(state, key) {
  const items = []
  for (const plan of state.plans) {
    if (!isScheduled(plan, key)) continue
    for (const step of planSteps(plan, key)) {
      items.push({
        key: `${plan.id}:${step.id}`,
        name: step.name,
        time: step.time,
        reminder: step.reminder,
        label: plan.category,
        planId: plan.id,
        counts: plan.countsForStreak,
      })
    }
  }
  for (const step of state.adhoc[key] || []) {
    items.push({
      key: `adhoc:${step.id}`,
      name: step.name,
      time: step.time,
      reminder: false,
      label: 'Just today',
      adhocId: step.id,
      counts: true,
    })
  }
  return items.sort((a, b) => a.time.localeCompare(b.time))
}

/**
 * 'done'   every streak-counting step was ticked
 * 'missed' a past day with steps left open
 * 'today'  today, still in progress
 * 'rest'   nothing was due
 * 'future' not here yet
 */
export function dayStatus(state, key, today) {
  if (key > today) return 'future'
  const steps = stepsForDay(state, key).filter((s) => s.counts)
  if (steps.length === 0) return 'rest'
  const done = state.log[key] || {}
  if (steps.every((s) => done[s.key])) return 'done'
  return key === today ? 'today' : 'missed'
}

/** First day anything was ever due, or null if there is no history. */
export function firstDay(state) {
  const keys = [...state.plans.map((p) => p.startDate), ...Object.keys(state.adhoc)]
  return keys.length ? keys.reduce((a, b) => (a < b ? a : b)) : null
}

/** Days in a row with everything done. Rest days are skipped; an unfinished today doesn't break it. */
export function currentStreak(state, today) {
  const first = firstDay(state)
  if (!first) return 0
  let streak = 0
  for (let key = today; key >= first; key = addDays(key, -1)) {
    const status = dayStatus(state, key, today)
    if (status === 'done') streak++
    else if (status === 'missed') break
  }
  return streak
}

export function bestStreak(state, today) {
  const first = firstDay(state)
  if (!first) return 0
  let best = 0
  let run = 0
  for (let key = first; key <= today; key = addDays(key, 1)) {
    const status = dayStatus(state, key, today)
    if (status === 'done') best = Math.max(best, ++run)
    else if (status === 'missed') run = 0
  }
  return best
}

/** Completed vs. due days for one plan: whole plan length if it has an end, days so far if not. */
export function planProgress(plan, state, today) {
  const until = plan.endDate || today
  let total = 0
  let done = 0
  for (let key = plan.startDate; key <= until; key = addDays(key, 1)) {
    if (!isScheduled(plan, key)) continue
    total++
    if (key > today) continue
    const ticked = state.log[key] || {}
    const steps = planSteps(plan, key)
    if (steps.length && steps.every((s) => ticked[`${plan.id}:${s.id}`])) done++
  }
  return {
    done,
    total,
    pct: total ? Math.round((done / total) * 100) : 0,
    label: `${done} of ${total} ${plan.endDate ? 'sessions' : 'days'}`,
  }
}
