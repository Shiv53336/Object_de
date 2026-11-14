import { describe, expect, it } from 'vitest'
import { addDays, formatDay, weekday } from './dates.js'
import { intervalTimes, spreadTimes } from './schedule.js'
import { bestStreak, currentStreak, dayStatus, planProgress, stepsForDay } from './stats.js'
import { emptyState, reducer } from './store.js'
import { dueReminders } from './reminders.js'

const TODAY = '2026-11-14' // a Saturday
const ALL = [true, true, true, true, true, true, true]

const plan = (over = {}) => ({
  id: 'p1',
  name: 'Morning routine',
  category: 'Daily routine',
  startDate: addDays(TODAY, -5),
  endDate: null,
  days: ALL,
  steps: [
    { id: 'a', name: 'Water', time: '06:30', reminder: true },
    { id: 'b', name: 'Stretch', time: '06:45', reminder: false },
  ],
  streakAlert: true,
  countsForStreak: true,
  ...over,
})

const tick = (state, date, ...keys) => keys.reduce((s, key) => reducer(s, { type: 'toggleStep', date, key }), state)
const withPlan = (p = plan()) => reducer(emptyState, { type: 'savePlan', plan: p })

describe('dates', () => {
  it('formats and finds weekdays', () => {
    expect(formatDay(TODAY)).toBe('Sat, 14 Nov')
    expect(weekday(TODAY)).toBe(5)
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01')
  })
})

describe('schedule', () => {
  it('builds hourly reminders with both ends included', () => {
    const times = intervalTimes('09:00', '21:00', 60)
    expect(times).toHaveLength(13)
    expect(times.at(-1)).toBe('21:00')
  })
  it('spreads a count evenly', () => {
    expect(spreadTimes('07:00', '22:00', 5)).toEqual(['07:00', '10:45', '14:30', '18:15', '22:00'])
    expect(spreadTimes('07:00', '22:00', 1)).toEqual(['07:00'])
  })
  it('returns nothing for an empty window', () => {
    expect(intervalTimes('21:00', '09:00', 60)).toEqual([])
    expect(spreadTimes('10:00', '10:00', 3)).toEqual([])
  })
})

describe('streaks', () => {
  it('counts consecutive done days and ignores an unfinished today', () => {
    let s = withPlan()
    for (const n of [-3, -2, -1]) s = tick(s, addDays(TODAY, n), 'p1:a', 'p1:b')
    expect(dayStatus(s, TODAY, TODAY)).toBe('today')
    expect(dayStatus(s, addDays(TODAY, -4), TODAY)).toBe('missed')
    expect(currentStreak(s, TODAY)).toBe(3)
    s = tick(s, TODAY, 'p1:a', 'p1:b')
    expect(currentStreak(s, TODAY)).toBe(4)
    expect(bestStreak(s, TODAY)).toBe(4)
  })
  it('breaks on a missed day but remembers the best run', () => {
    let s = withPlan()
    for (const n of [-5, -4, -3]) s = tick(s, addDays(TODAY, n), 'p1:a', 'p1:b')
    s = tick(s, addDays(TODAY, -1), 'p1:a', 'p1:b')
    expect(currentStreak(s, TODAY)).toBe(1)
    expect(bestStreak(s, TODAY)).toBe(3)
  })
  it('skips days with nothing due', () => {
    const weekdaysOnly = [true, true, true, true, true, false, false]
    let s = withPlan(plan({ days: weekdaysOnly, startDate: addDays(TODAY, -8) }))
    for (const n of [-2, -1]) s = tick(s, addDays(TODAY, n), 'p1:a', 'p1:b') // Thu, Fri
    expect(dayStatus(s, TODAY, TODAY)).toBe('rest')
    expect(currentStreak(s, TODAY)).toBe(2)
  })
  it('leaves nudge-only plans out of the streak', () => {
    const s = withPlan(plan({ countsForStreak: false }))
    expect(stepsForDay(s, TODAY)).toHaveLength(2)
    expect(dayStatus(s, addDays(TODAY, -1), TODAY)).toBe('rest')
  })
})

describe('plans', () => {
  it('reports progress against the whole plan when it has an end', () => {
    let s = withPlan(plan({ endDate: addDays(TODAY, 4) }))
    s = tick(s, TODAY, 'p1:a', 'p1:b')
    expect(planProgress(s.plans[0], s, TODAY)).toMatchObject({ done: 1, total: 10, label: '1 of 10 sessions' })
  })
  it('keeps history when a plan is removed', () => {
    let s = withPlan()
    s = tick(s, addDays(TODAY, -1), 'p1:a', 'p1:b')
    s = reducer(s, { type: 'removePlan', id: 'p1', today: TODAY })
    expect(s.plans[0].archived).toBe(true)
    expect(stepsForDay(s, TODAY)).toHaveLength(0)
    expect(dayStatus(s, addDays(TODAY, -1), TODAY)).toBe('done')
  })
  it('deletes a plan that never ran', () => {
    const s = reducer(withPlan(plan({ startDate: TODAY })), { type: 'removePlan', id: 'p1', today: TODAY })
    expect(s.plans).toHaveLength(0)
  })
  it('adds and removes one-off steps', () => {
    let s = reducer(emptyState, { type: 'addAdhoc', date: TODAY, name: 'Call mum', time: '18:00' })
    const [step] = stepsForDay(s, TODAY)
    expect(step.name).toBe('Call mum')
    s = reducer(s, { type: 'removeAdhoc', date: TODAY, id: step.adhocId })
    expect(s.adhoc).toEqual({})
  })
})

describe('reminders', () => {
  const at = (time) => new Date(`${TODAY}T${time}:00`)
  it('fires for open steps with a reminder, within the grace window', () => {
    const s = withPlan()
    expect(dueReminders(s, TODAY, at('06:30')).map((r) => r.title)).toEqual(['Water'])
    expect(dueReminders(s, TODAY, at('06:33'))).toHaveLength(1) // a few minutes late still fires
    expect(dueReminders(s, TODAY, at('06:46'))).toHaveLength(0) // Stretch has no reminder
    expect(dueReminders(s, TODAY, at('06:36'))).toHaveLength(0)
    expect(dueReminders(tick(s, TODAY, 'p1:a'), TODAY, at('06:30'))).toHaveLength(0)
  })
  it('sends the streak alert only while steps are open', () => {
    const s = withPlan()
    expect(dueReminders(s, TODAY, at('21:00'))[0].title).toBe('Your streak is at risk')
    expect(dueReminders(tick(s, TODAY, 'p1:a', 'p1:b'), TODAY, at('21:00'))).toHaveLength(0)
  })
})
