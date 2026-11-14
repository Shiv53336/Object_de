import { useEffect, useMemo, useReducer, useState } from 'react'
import { toKey } from './lib/dates.js'
import { notificationPermission, requestNotifications, useReminders } from './lib/reminders.js'
import { loadState, reducer, saveState, StoreContext } from './lib/store.js'
import TabBar from './components/TabBar.jsx'
import Home from './screens/Home.jsx'
import Plans from './screens/Plans.jsx'
import PlanSetup from './screens/PlanSetup.jsx'
import CustomPlan from './screens/CustomPlan.jsx'
import Progress from './screens/Progress.jsx'

const readRoute = () => window.location.hash.replace(/^#\/?/, '').split('/')

function useRoute() {
  const [route, setRoute] = useState(readRoute)
  useEffect(() => {
    const onChange = () => {
      setRoute(readRoute())
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}

/** The current time, refreshed often enough to roll the day over and fire reminders. */
function useNow() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const update = () => setNow(new Date())
    const timer = setInterval(update, 30_000)
    document.addEventListener('visibilitychange', update)
    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', update)
    }
  }, [])
  return now
}

export default function App() {
  const [state, dispatch] = useReducer(reducer, undefined, loadState)
  const [permission, setPermission] = useState(notificationPermission)
  const now = useNow()
  const today = toKey(now)
  const [screen, param] = useRoute()

  useEffect(() => saveState(state), [state])
  useReminders(state, today, now)

  const store = useMemo(
    () => ({
      state,
      dispatch,
      today,
      now,
      permission,
      askForNotifications: async () => setPermission(await requestNotifications()),
    }),
    [state, today, now, permission],
  )

  let page
  let tab = null
  if (screen === 'plans') [page, tab] = [<Plans />, 'plans']
  else if (screen === 'progress') [page, tab] = [<Progress />, 'progress']
  else if (screen === 'setup' || screen === 'edit') page = <PlanSetup key={`${screen}/${param}`} mode={screen} id={param} />
  else if (screen === 'custom') page = <CustomPlan />
  else [page, tab] = [<Home />, 'home']

  return (
    <StoreContext.Provider value={store}>
      <div className="app">
        {page}
        {tab && <TabBar current={tab} />}
      </div>
    </StoreContext.Provider>
  )
}
