import { useState } from 'react'
import Icon from '../components/Icon.jsx'
import { CATEGORIES, durationLabel, stepsLabel, TEMPLATES } from '../lib/templates.js'
import { useStore } from '../lib/store.js'

export default function Plans() {
  const { state } = useStore()
  const [filter, setFilter] = useState('All')
  const active = state.plans.filter((p) => !p.archived)
  const ownPlans = active.filter((p) => !p.templateId)
  const templates = TEMPLATES.filter((t) => filter === 'All' || t.category === filter)

  return (
    <main className="screen">
      <header className="page-header">
        <h1>Plans</h1>
        <div className="muted">Pick a ready-made plan, then set your own times.</div>
      </header>

      <div className="chips">
        {['All', ...CATEGORIES].map((name) => (
          <button key={name} type="button" className="chip" aria-pressed={filter === name} onClick={() => setFilter(name)}>
            {name}
          </button>
        ))}
      </div>

      <div className="plan-list">
        {templates.map((t) => {
          const running = active.find((p) => p.templateId === t.id)
          return (
            <PlanCard
              key={t.id}
              icon={t.icon}
              name={t.name}
              meta={`${t.category} · ${durationLabel(t.weeks)} · ${stepsLabel(t.steps.length)}`}
              href={running ? `#/edit/${running.id}` : `#/setup/${t.id}`}
              action={running ? 'Edit' : 'Start'}
              active={Boolean(running)}
            />
          )
        })}

        {filter === 'All' &&
          ownPlans.map((p) => (
            <PlanCard
              key={p.id}
              icon="star"
              name={p.name}
              meta={`Your plan · ${p.endDate ? 'Has an end date' : 'Ongoing'} · ${stepsLabel(p.steps.length)}`}
              href={`#/edit/${p.id}`}
              action="Edit"
              active
            />
          ))}

        <a href="#/custom" className="dashed-button tall">
          <Icon name="plus" />
          Create your own plan
        </a>
      </div>
    </main>
  )
}

function PlanCard({ icon, name, meta, href, action, active }) {
  return (
    <div className="card plan-card">
      <div className="thumb">
        <Icon name={icon} size={26} strokeWidth={1.5} />
      </div>
      <div className="grow">
        <div className="plan-name">{name}</div>
        <div className="step-label">{meta}</div>
        {active && <div className="badge">Active</div>}
      </div>
      <a href={href} className="pill pill-strong" aria-label={`${action} ${name}`}>
        {action}
      </a>
    </div>
  )
}
