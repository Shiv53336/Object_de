import { createContext, useContext } from 'react'
import { addDays } from './dates.js'

const STORAGE_KEY = 'planner-app:v1'

export const emptyState = { plans: [], log: {}, adhoc: {} }

export const uid = () =>
  globalThis.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`

export function loadState() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY))
    if (saved && Array.isArray(saved.plans)) return { ...emptyState, ...saved }
  } catch {
    // Unreadable or blocked storage: start fresh.
  }
  return emptyState
}

export function saveState(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    // Storage full or blocked: the app keeps working for this visit.
  }
}

export function reducer(state, action) {
  switch (action.type) {
    case 'savePlan': {
      const exists = state.plans.some((p) => p.id === action.plan.id)
      const plans = exists
        ? state.plans.map((p) => (p.id === action.plan.id ? action.plan : p))
        : [...state.plans, action.plan]
      return { ...state, plans }
    }
    case 'removePlan': {
      // A plan with history is ended yesterday rather than deleted, so past days keep their record.
      const yesterday = addDays(action.today, -1)
      const plans = state.plans.flatMap((p) => {
        if (p.id !== action.id) return [p]
        if (p.startDate > yesterday) return []
        const endDate = p.endDate && p.endDate < yesterday ? p.endDate : yesterday
        return [{ ...p, archived: true, endDate }]
      })
      return { ...state, plans }
    }
    case 'toggleStep': {
      const day = { ...(state.log[action.date] || {}) }
      if (day[action.key]) delete day[action.key]
      else day[action.key] = true
      return { ...state, log: { ...state.log, [action.date]: day } }
    }
    case 'addAdhoc': {
      const list = [...(state.adhoc[action.date] || []), { id: uid(), name: action.name, time: action.time }]
      return { ...state, adhoc: { ...state.adhoc, [action.date]: list } }
    }
    case 'removeAdhoc': {
      const list = (state.adhoc[action.date] || []).filter((s) => s.id !== action.id)
      const adhoc = { ...state.adhoc, [action.date]: list }
      if (list.length === 0) delete adhoc[action.date]
      return { ...state, adhoc }
    }
    default:
      return state
  }
}

export const StoreContext = createContext(null)
export const useStore = () => useContext(StoreContext)

/** Move to another screen, e.g. go('#/plans'). */
export const go = (hash) => window.location.assign(hash)
