// ─── Colors ───────────────────────────────────────────────────────────────────
export const COLORS = {
  bg:         '#FAF6F1',
  bgDark:     '#F3EDE4',
  card:       '#FFFFFF',
  border:     '#EDE8E1',
  navy:       '#3D405B',
  terracotta: '#E07A5F',
  sage:       '#81B29A',
  gold:       '#F2CC8F',
  purple:     '#7B68EE',
  pink:       '#E88D97',
  indigo:     '#6C63FF',
  textDark:   '#2D2A26',
  textMid:    '#5A5550',
  textLight:  '#8B8580',
  textFaint:  '#CCC5BB',
};

// ─── Fonts (system fallbacks since expo-font not set up) ──────────────────────
export const FONTS = {
  heading: 'serif',   // Caveat fallback
  body:    'sans-serif',
  number:  'serif',   // Crimson Pro fallback
};

// ─── Default data ─────────────────────────────────────────────────────────────
export const DEFAULT_EXPENSE_CATEGORIES = [
  { name: 'Food & Dining',     emoji: '🍜', color: '#E07A5F', budget: 8000,  type: 'expense' },
  { name: 'Transport',         emoji: '🛺', color: '#3D405B', budget: 3000,  type: 'expense' },
  { name: 'Shopping',          emoji: '🛍️', color: '#81B29A', budget: 5000,  type: 'expense' },
  { name: 'Bills & Utilities', emoji: '💡', color: '#F2CC8F', budget: 6000,  type: 'expense' },
  { name: 'Entertainment',     emoji: '🎮', color: '#7B68EE', budget: 2000,  type: 'expense' },
  { name: 'Health',            emoji: '💊', color: '#E88D97', budget: 2000,  type: 'expense' },
];

export const DEFAULT_INCOME_CATEGORIES = [
  { name: 'Salary',     emoji: '💼', color: '#81B29A', budget: 0, type: 'income' },
  { name: 'Freelance',  emoji: '💻', color: '#2A9D8F', budget: 0, type: 'income' },
  { name: 'Investment', emoji: '📈', color: '#F2CC8F', budget: 0, type: 'income' },
  { name: 'Gift',       emoji: '🎁', color: '#E88D97', budget: 0, type: 'income' },
  { name: 'Other',      emoji: '💰', color: '#6C63FF', budget: 0, type: 'income' },
];

export const DEFAULT_CATEGORIES = [
  ...DEFAULT_EXPENSE_CATEGORIES,
  ...DEFAULT_INCOME_CATEGORIES,
];

export const PAYMENT_TYPES = [
  { label: 'UPI',  icon: '📱', color: '#6C63FF' },
  { label: 'Card', icon: '💳', color: '#E07A5F' },
  { label: 'Cash', icon: '💵', color: '#81B29A' },
  { label: 'Other',icon: '💸', color: '#8B8580' },
];

export const CURRENCIES = {
  '₹': 'INR',
  '$': 'USD',
  '€': 'EUR',
  '£': 'GBP',
};

export const RAND_COLORS = [
  '#E07A5F', '#3D405B', '#81B29A', '#F2CC8F', '#7B68EE',
  '#E88D97', '#6C63FF', '#F4A261', '#2A9D8F', '#E76F51',
];

export const DEFAULT_BUDGET = 26000;

export const STREAK_MILESTONES = [7, 14, 30, 60, 90, 180, 365];

export const FREQ_LABELS = {
  daily:   'Daily',
  weekly:  'Weekly',
  monthly: 'Monthly',
  yearly:  'Yearly',
};

// ─── Storage keys ─────────────────────────────────────────────────────────────
export const KEYS = {
  currency:   'et_currency',
  budget:     'et_budget',
  expenses:   'et_expenses',
  categories: 'et_categories',
  recurring:  'et_recurring',
  dailyNotes: 'et_daily_notes',
  streak:     'et_streak',
  settings:   'et_settings',
};
