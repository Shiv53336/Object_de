export const CATEGORIES = ['Fitness', 'Study', 'Daily routine']

const ALL_DAYS = [true, true, true, true, true, true, true]

/** Ready-made plans. `weeks: null` means the plan keeps going until removed. */
export const TEMPLATES = [
  {
    id: 'home-workout',
    name: 'Beginner home workout',
    category: 'Fitness',
    weeks: 4,
    icon: 'dumbbell',
    days: [true, false, true, false, true, true, false],
    steps: [
      { name: 'Warm-up', time: '07:00', reminder: true },
      { name: 'Workout', time: '07:10', reminder: true },
      { name: 'Cool-down and log', time: '07:40', reminder: false },
    ],
  },
  {
    id: '10k-steps',
    name: '10k steps a day',
    category: 'Fitness',
    weeks: null,
    icon: 'walk',
    days: ALL_DAYS,
    steps: [{ name: 'Walk 10,000 steps', time: '19:00', reminder: true }],
  },
  {
    id: 'exam-prep',
    name: 'Exam prep',
    category: 'Study',
    weeks: 8,
    icon: 'book',
    days: [true, true, true, true, true, true, false],
    steps: [
      { name: 'Study block, 2 hours', time: '10:00', reminder: true },
      { name: 'Review notes', time: '20:00', reminder: true },
    ],
  },
  {
    id: 'morning-routine',
    name: 'Morning routine',
    category: 'Daily routine',
    weeks: null,
    icon: 'sun',
    days: ALL_DAYS,
    steps: [
      { name: 'Wake up and water', time: '06:30', reminder: true },
      { name: 'Stretch for 10 minutes', time: '06:45', reminder: false },
      { name: 'Healthy breakfast', time: '07:15', reminder: false },
      { name: 'Plan the day', time: '07:30', reminder: true },
    ],
  },
]

export const durationLabel = (weeks) => (weeks ? `${weeks} weeks` : 'Ongoing')

export const stepsLabel = (n) => `${n} ${n === 1 ? 'step' : 'steps'} a day`
