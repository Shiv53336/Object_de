# Planner

A daily planner built from the Planner app wireframes: pick a ready-made plan (or create your own), tick off today's steps, get reminders, and keep a streak going. It is an offline-first PWA — everything is stored on the device, there is no account and no server.

## Screens

| Screen | Route | What it does |
| --- | --- | --- |
| Home | `#/` | Today's checklist, progress bar, "up next" card, one-off steps for today |
| Plans | `#/plans` | Ready-made plans with category filters, your active plans, link to create your own |
| Plan setup | `#/setup/:template`, `#/edit/:plan` | Start date, repeat days, step times, per-step reminders, streak-at-risk alert |
| Custom plan | `#/custom` | Remind every few hours, N times a day, or at set times |
| Progress | `#/progress` | Current and best streak, last 4 weeks, progress per plan |

## Run it

```bash
npm install --legacy-peer-deps
npm run dev      # local dev server
npm test         # unit tests for schedules, streaks and reminders
npm run lint
npm run build    # production build in dist/
npm run preview  # serve the production build
```

The build uses relative paths, so `dist/` can be hosted from any folder (GitHub Pages, Netlify, or any static server).

## How it works

- **Storage** — plans, ticked steps and one-off steps live in `localStorage` under `planner-app:v1`.
- **Streak** — a day counts when every step that counts towards the streak is ticked. Days with nothing due are skipped, and an unfinished today does not break the streak.
- **Removing a plan** — the plan is ended rather than erased, so days already completed stay in your progress.
- **Reminders** — shown as browser notifications. They fire while the app is open or installed and running in the background; there is no push server, so a fully closed app cannot notify.

## Layout

```
src/
  lib/         dates, schedules, streak maths, storage, reminders (+ tests)
  components/  icons, tab bar, toggle, day picker, stepper
  screens/     Home, Plans, PlanSetup, CustomPlan, Progress
```
