import Icon from './Icon.jsx'

const TABS = [
  { id: 'home', label: 'Home', icon: 'home', href: '#/' },
  { id: 'plans', label: 'Plans', icon: 'list', href: '#/plans' },
  { id: 'progress', label: 'Progress', icon: 'chart', href: '#/progress' },
]

export default function TabBar({ current }) {
  return (
    <nav className="tabbar" aria-label="Main">
      {TABS.map((tab) => (
        <a key={tab.id} href={tab.href} aria-current={tab.id === current ? 'page' : undefined}>
          <Icon name={tab.icon} size={22} />
          {tab.label}
        </a>
      ))}
    </nav>
  )
}
