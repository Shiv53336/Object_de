import { fromMinutes, toMinutes } from './dates.js'

/** Gap choices for "Every few hours", in minutes. */
export const INTERVALS = [30, 60, 90, 120, 180, 240]

export const intervalLabel = (mins) => {
  if (mins < 60) return `${mins} min`
  const hours = mins / 60
  return `${hours} ${hours === 1 ? 'hour' : 'hours'}`
}

/** Every `every` minutes from `from` to `to`, both ends included. */
export function intervalTimes(from, to, every) {
  const start = toMinutes(from)
  const end = toMinutes(to)
  const times = []
  for (let t = start; t <= end; t += every) times.push(fromMinutes(t))
  return end > start ? times : []
}

/** `count` reminders spread evenly from `from` to `to`, both ends included. */
export function spreadTimes(from, to, count) {
  const start = toMinutes(from)
  const end = toMinutes(to)
  if (end <= start || count < 1) return []
  if (count === 1) return [from]
  const gap = (end - start) / (count - 1)
  return Array.from({ length: count }, (_, i) => fromMinutes(Math.round(start + gap * i)))
}
