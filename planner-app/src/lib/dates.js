// Dates are handled as local 'YYYY-MM-DD' keys and times as 'HH:MM' strings,
// so both compare correctly as plain strings.
const pad = (n) => String(n).padStart(2, '0')

export const toKey = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

export const fromKey = (key) => {
  const [y, m, d] = key.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export const addDays = (key, n) => {
  const d = fromKey(key)
  d.setDate(d.getDate() + n)
  return toKey(d)
}

/** Monday = 0 … Sunday = 6 */
export const weekday = (key) => (fromKey(key).getDay() + 6) % 7

export const toHHMM = (d) => `${pad(d.getHours())}:${pad(d.getMinutes())}`

export const toMinutes = (time) => {
  const [h, m] = time.split(':').map(Number)
  return h * 60 + m
}

export const fromMinutes = (mins) => `${pad(Math.floor(mins / 60))}:${pad(mins % 60)}`

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** 'Sat, 14 Nov' */
export const formatDay = (key) => {
  const d = fromKey(key)
  return `${WEEKDAYS[weekday(key)]}, ${d.getDate()} ${MONTHS[d.getMonth()]}`
}

export const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
export const DAY_LETTERS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
