import { useEffect } from 'react'
import { toHHMM, toMinutes } from './dates.js'
import { stepsForDay } from './stats.js'

export const STREAK_ALERT_TIME = '21:00'
// A reminder still fires if the tab was asleep when its minute passed, up to this many minutes late.
const GRACE_MINUTES = 5

export const notificationPermission = () =>
  typeof Notification === 'undefined' ? 'unsupported' : Notification.permission

export async function requestNotifications() {
  if (typeof Notification === 'undefined') return 'unsupported'
  if (Notification.permission !== 'default') return Notification.permission
  try {
    return await Notification.requestPermission()
  } catch {
    return Notification.permission
  }
}

async function notify(title, body, tag) {
  const options = { body, tag, icon: './pwa-192x192.png', badge: './pwa-192x192.png' }
  try {
    const registration = await navigator.serviceWorker?.getRegistration()
    if (registration) return await registration.showNotification(title, options)
    new Notification(title, options)
  } catch {
    // Notifications are a nice-to-have; never let them break the app.
  }
}

const SENT_KEY = 'planner-app:sent'
function alreadySent(id) {
  try {
    const sent = JSON.parse(sessionStorage.getItem(SENT_KEY)) || []
    if (sent.includes(id)) return true
    sessionStorage.setItem(SENT_KEY, JSON.stringify([...sent.slice(-200), id]))
  } catch {
    // Without session storage we may repeat a reminder after a reload; acceptable.
  }
  return false
}

const isDue = (time, nowMinutes) => {
  const late = nowMinutes - toMinutes(time)
  return late >= 0 && late <= GRACE_MINUTES
}

/** Reminders that should fire right now. Pure, so it can be tested. */
export function dueReminders(state, today, now) {
  const nowMinutes = toMinutes(toHHMM(now))
  const done = state.log[today] || {}
  const open = stepsForDay(state, today).filter((s) => !done[s.key])
  const due = open
    .filter((s) => s.reminder && isDue(s.time, nowMinutes))
    .map((s) => ({ id: `${today}|${s.key}`, title: s.name, body: `${s.label} · ${s.time}` }))

  const openStreakSteps = open.filter((s) => s.counts)
  const alertOn = state.plans.some((p) => p.streakAlert && openStreakSteps.some((s) => s.planId === p.id))
  if (alertOn && isDue(STREAK_ALERT_TIME, nowMinutes)) {
    const n = openStreakSteps.length
    due.push({
      id: `${today}|streak`,
      title: 'Your streak is at risk',
      body: `${n} ${n === 1 ? 'step is' : 'steps are'} still open today.`,
    })
  }
  return due
}

/** Fires reminders while the app is open. `now` ticks from the App clock. */
export function useReminders(state, today, now) {
  useEffect(() => {
    if (notificationPermission() !== 'granted') return
    for (const r of dueReminders(state, today, now)) {
      if (!alreadySent(r.id)) notify(r.title, r.body, r.id)
    }
  }, [state, today, now])
}
