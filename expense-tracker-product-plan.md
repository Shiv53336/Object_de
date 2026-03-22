# Product Plan Document — Money Journal App

## Executive Summary

A personal money journal mobile app (iOS + Android) that transforms daily expense tracking from a chore into a mindful ritual. Unlike competitors that focus on automation, bank sync, or bill splitting, this app is built for people who **like writing down their expenses** — treating it as a daily journaling practice, not a finance tool.

**Target users:** Individuals and couples (22-40) who prefer manual expense logging over automated bank sync. Strong resonance with Indian households, but designed for global audiences.

**Distribution:** React Native (cross-platform), published on both Apple App Store and Google Play Store.

**Monetization:** Freemium — generous free tier, Pro subscription for power features.

---

## 1. Brand & Identity

### Name Options (Choose One Before Development)

| Name | Why It Works | Concerns |
|------|-------------|----------|
| **Hisaab** | Hindi for "accounts/reckoning." Short, unique, premium-sounding. International appeal (non-English names like Toshl work globally). Deeply cultural. | May need pronunciation guide for non-Hindi speakers |
| **Jotter** | English word for "small notebook for quick notes." Universal, immediately understood. Perfect metaphor for the app. | May conflict with existing note-taking apps |
| **Pennylog** | "Penny" + "log." Friendly, clear, approachable. Easy to spell and search. | Slightly generic |
| **Kharcha** | Hindi for "expense." Catchy, memorable, unique globally. | Narrow meaning (just "expense") vs. the journal identity |
| **CoinQuill** | "Coin" + "quill pen." Elegant, ties to the writing/journal aesthetic. | Slightly harder to remember |

### Tagline Options
- "Your daily money diary"
- "Write it down. Watch it change."
- "The mindful way to track money"

### Visual Identity
- **Aesthetic:** Warm notebook/diary — off-white (#FAF6F1), papery textures, muted earthy tones
- **Primary color:** Navy (#3D405B)
- **Accent colors:** Terracotta (#E07A5F), Sage (#81B29A), Gold (#F2CC8F)
- **Fonts:** Caveat (handwriting headers), Crimson Pro (serif numbers), DM Sans (UI body text)
- **App Icon direction:** A small open notebook with a pen/quill, warm tones, simple and recognizable at small sizes

---

## 2. Architecture & Tech Stack

### Current State (Web — Vite + React)
- Single `App.jsx` (~580 lines) with well-separated components
- `recharts` for charts (PieChart, BarChart)
- `localStorage` via custom `useLocalStorage` hook
- PWA configured via `vite-plugin-pwa` + workbox
- Fully offline, no backend, no authentication
- Payment type tracking (UPI/Card/Cash/Other)
- Custom category creation with emoji + budget

### Target State (Mobile — React Native)

```
Tech Stack:
├── Framework:      React Native (Expo managed workflow)
├── Navigation:     React Navigation (bottom tabs + stack)
├── Storage:        AsyncStorage (drop-in for localStorage)
├── Charts:         react-native-chart-kit or Victory Native
├── Animations:     react-native-reanimated + react-native-gesture-handler
├── Sound:          expo-av (for pen-on-paper sound effects)
├── Haptics:        expo-haptics (tactile feedback on expense add)
├── Notifications:  expo-notifications (daily reminder, budget alerts)
├── Subscriptions:  RevenueCat (manages both Apple + Google billing)
├── Analytics:      PostHog (free, privacy-friendly) or Firebase Analytics
├── Crash Reports:  Sentry (free tier)
├── Icons:          react-native-vector-icons or lucide-react-native
└── Build/Deploy:   EAS Build + EAS Submit (Expo Application Services)
```

### Why Expo (Managed Workflow)
- Single codebase for iOS + Android
- OTA updates (push bug fixes without App Store review)
- EAS Build handles native compilation (no local Xcode/Android Studio needed initially)
- Expo Go for rapid development/testing on your phone
- Can eject to bare workflow later if needed

### Data Model (AsyncStorage)

```javascript
// All stored as JSON in AsyncStorage
{
  "et_expenses": [
    {
      "id": 1711000000000,        // Date.now() timestamp
      "amount": 250,
      "category": "Food & Dining",
      "note": "Lunch at canteen",
      "date": "2026-03-22",       // ISO date string
      "emoji": "🍜",
      "payment": "UPI",
      "type": "expense"           // NEW: "expense" | "income"
    }
  ],
  "et_categories": [
    {
      "name": "Food & Dining",
      "emoji": "🍜",
      "color": "#E07A5F",
      "budget": 8000,
      "type": "expense"           // NEW: "expense" | "income"
    }
  ],
  "et_recurring": [               // NEW
    {
      "id": 1711000000001,
      "amount": 15000,
      "category": "Bills & Utilities",
      "note": "Rent",
      "emoji": "🏠",
      "payment": "UPI",
      "type": "expense",
      "frequency": "monthly",     // "daily" | "weekly" | "monthly" | "yearly"
      "dayOfMonth": 1,
      "lastAdded": "2026-03-01",
      "active": true
    }
  ],
  "et_daily_notes": {             // NEW
    "2026-03-22": "Stayed within budget today. Proud!",
    "2026-03-21": "Overspent on dinner but it was worth it."
  },
  "et_currency": "₹",
  "et_budget": 26000,
  "et_streak": {                  // NEW
    "currentStreak": 12,
    "longestStreak": 28,
    "lastLogDate": "2026-03-22"
  },
  "et_settings": {                // NEW
    "soundEnabled": true,
    "hapticEnabled": true,
    "dailyReminderTime": "21:00",
    "theme": "classic"            // "classic" | "dark" | "sepia" (Pro)
  }
}
```

### Migration Strategy (Web → React Native)
1. Copy component logic (state management, calculations, helpers) — these are framework-agnostic
2. Replace HTML/inline styles with React Native `View`, `Text`, `StyleSheet`
3. Replace `localStorage` with `AsyncStorage` (same API pattern)
4. Replace `recharts` with `react-native-chart-kit` or Victory Native
5. Add React Navigation for bottom tab bar (replacing your current state-based view switching)
6. Add native-specific features: haptics, sound, notifications, widgets

---

## 3. Feature Specification

### 3.1 Core Features (FREE — v1.0)

#### 3.1.1 Quick Expense Entry (Existing — Enhanced)
**Current:** Amount + category dropdown + note + payment type
**Enhancements:**
- **Pen-on-paper sound effect** — plays on successful add. Synthesized using `expo-av` with a pre-bundled short audio file (~5KB). Subtle, satisfying, like a pen scratch.
- **Haptic feedback** — light impact vibration on add (expo-haptics)
- **Ink stroke animation** — newly added expense slides in with a handwriting-style reveal animation (opacity 0→1 + translateX with spring physics via reanimated)
- **Date picker** — defaults to today, tap to pick a past date (for logging yesterday's forgotten expenses)
- **Income toggle** — switch between "Expense" and "Income" mode. Income entries show in green, expenses in terracotta red. Affects net balance calculation.

```
┌─────────────────────────────────────┐
│  ✏️ Quick Entry                      │
│                                     │
│  [₹] [____amount____] [🍜 Food ▾]  │
│  [Add a note...                  ]  │
│  Paid via: [UPI] [Card] [Cash] [+]  │
│  Type: (●) Expense  (○) Income      │
│  Date: [Today ▾]                    │
│                          [✓ Add]    │
└─────────────────────────────────────┘
```

#### 3.1.2 Edit Existing Expense (NEW)
- Tap any expense in the list → opens edit modal pre-filled with all fields
- Can change amount, category, note, payment type, date
- "Save" and "Delete" buttons at bottom
- Swipe-left to delete (gesture handler) as alternative

#### 3.1.3 Search & Filter (NEW)
- Search bar at top of expense list — filters by note text
- Filter chips: by category, by payment type, by date range
- Sort: newest first (default), oldest first, highest amount, lowest amount

```
┌─────────────────────────────────────┐
│  🔍 [Search expenses...          ]  │
│  [All] [🍜Food] [🛺Transport] [+]  │
│  [This Week ▾]  [All Payments ▾]   │
└─────────────────────────────────────┘
```

#### 3.1.4 Income Tracking (NEW)
- Same quick entry UI, but with a toggle for "Expense" vs "Income"
- Default income categories: Salary, Freelance, Investment, Gift, Other
- Users can create custom income categories
- Budget card shows: Income - Expenses = Net Balance
- Charts include income vs expense comparison

#### 3.1.5 Recurring Expenses (NEW)
- Settings/dedicated section to set up recurring entries
- Fields: amount, category, note, payment, frequency (daily/weekly/monthly/yearly), day of month
- App auto-adds the entry when the date arrives (checked on app open)
- List of active recurring items with toggle to pause/resume
- Examples: Rent, EMI, Netflix, gym membership

#### 3.1.6 Budget Card (Existing — Enhanced)
- Show total income, total expenses, net balance
- Progress bar with color coding (green → yellow → red)
- Days remaining in month
- Per-category budget vs spent mini-bars
- Warning when approaching 85% of budget

#### 3.1.7 Category Breakdown (Existing)
- Toggle between donut chart and bar chart
- Filter by time period (this week / this month / custom)
- Custom category creation with emoji, name, color, budget
- Shows spent vs budget per category

#### 3.1.8 Weekly Trend (Existing — Enhanced)
- Bar chart showing daily spending for the week
- Toggle: daily / weekly / monthly views
- Avg per day, total, highest spending day
- Monthly view shows bar per week

#### 3.1.9 Expense List (Existing — Enhanced)
- Grouped by date with "Today", "Yesterday", and date labels
- Each item shows: emoji, note, category, payment badge, amount
- NEW: Edit on tap (opens edit modal)
- NEW: Swipe left to delete with confirmation
- NEW: Ink-slide animation on newly added items
- NEW: Who-added avatar (preparation for future Shared Notebook)

---

### 3.2 Signature Features (FREE — The Differentiators)

#### 3.2.1 Pen-on-Paper Sound & Haptic
**Purpose:** Make logging feel like a physical act of writing, not tapping a screen.
**Implementation:**
- Bundle a short (~0.3s) pen-scratch audio file (royalty-free, ~5KB WAV)
- Play via `expo-av` Audio API on successful expense add
- Simultaneously trigger `Haptics.impactAsync(ImpactFeedbackStyle.Light)`
- Toggle on/off in settings (default: ON)
- Sound should be subtle — not loud or annoying

#### 3.2.2 Ink Stroke Animation
**Purpose:** Visual delight when adding an expense — it should feel like ink appearing on paper.
**Implementation:**
- New expense card enters with: `opacity: 0 → 1`, `translateY: -20 → 0`, spring animation (damping 15, stiffness 150)
- Slight scale pulse on the amount text: `scale: 1 → 1.05 → 1` over 300ms
- Use `react-native-reanimated` entering/exiting animations
- Only plays on the NEWLY added item, not on list re-renders

#### 3.2.3 Daily Money Note (NEW — Killer Feature)
**Purpose:** Transform expense tracking into journaling. Users reflect on their day's spending.
**Trigger:** Shown on home screen below the expense list. Also triggered via evening notification (9 PM default).
**UI:**

```
┌─────────────────────────────────────┐
│  📝 Today's Note                    │
│                                     │
│  You spent ₹1,430 across 5 entries  │
│  Top: Food (₹680)                   │
│                                     │
│  ┌─────────────────────────────────┐│
│  │ How was your spending today?    ││
│  │ Write a reflection...           ││
│  │                                 ││
│  └─────────────────────────────────┘│
│                          [Save 💾] │
│                                     │
│  Yesterday: "Good day, only ₹400   │
│  on essentials. Cooking at home     │
│  saved a lot."                      │
└─────────────────────────────────────┘
```

**Data:** Stored in `et_daily_notes` as date→string map.
**Value:** After weeks, users have a personal finance diary they genuinely value. Creates emotional attachment to the app. Improves retention dramatically.

#### 3.2.4 Streak Counter (NEW)
**Purpose:** Encourage daily logging habit through consistency tracking.
**Logic:**
- A "streak" = consecutive calendar days with at least 1 expense logged
- Displayed on home screen header: "🔥 12-day streak"
- Streak breaks if user misses a full calendar day with zero entries
- Milestones: 7, 14, 30, 60, 90, 180, 365 days — subtle celebration animation
- Longest streak recorded and shown in stats

```
┌─────────────────────────────────────┐
│  My Expenses            🔥 12 days  │
│  March 2026                         │
└─────────────────────────────────────┘
```

**Implementation:**
- On each expense add, check if `lastLogDate` < today → increment streak
- On app open, check if `lastLogDate` < yesterday → streak reset to 0
- Store in `et_streak` object

#### 3.2.5 Weekly Letter (NEW — Shareable)
**Purpose:** A beautiful, warm, weekly summary that users look forward to and share.
**Trigger:** Generated every Sunday (or manually accessible via Stats tab).
**Format:** A single-screen card written in warm, human language — NOT cold stats.

```
┌─────────────────────────────────────┐
│          📬 Your Weekly Letter       │
│            Mar 16 — Mar 22          │
│                                     │
│  This week, you logged 23 entries   │
│  totaling ₹9,680.                   │
│                                     │
│  Food & Dining was your biggest     │
│  companion at ₹3,200 (33%).         │
│                                     │
│  Your lightest day was Tuesday —    │
│  just ₹120 on chai. ☕             │
│                                     │
│  You stayed within budget on 4 out  │
│  of 6 categories. 💪               │
│                                     │
│  Your streak: 12 days and counting! │
│                                     │
│  Daily notes highlight:             │
│  "Cooking at home saved a lot"      │
│                                     │
│  ── [Share This Week 📤] ──        │
│                                     │
│  Powered by [AppName]               │
└─────────────────────────────────────┘
```

**Share functionality:**
- "Share This Week" generates a beautiful image card (using `react-native-view-shot`)
- Card includes summary stats + app branding + download link
- User shares via native share sheet (WhatsApp, Instagram Stories, etc.)
- THIS IS YOUR ORGANIC GROWTH ENGINE — every share is a free ad

#### 3.2.6 Monthly Chapter (NEW)
**Purpose:** Each month becomes a "chapter" in the user's money story.
**Trigger:** Generated on the 1st of each month for the previous month.
**Content:**
- Total income, total expenses, net savings
- Category breakdown with vs. previous month comparison
- Top 3 biggest expenses
- Streak stats for the month
- Best daily note of the month (longest one or user-starred)
- "Chapter 3 of 2026" — numbering creates a sense of progress

**After 12 months:** "Your Year in Money" annual review (Pro feature for export).

---

### 3.3 Pro Features (PAID — Subscription)

**Pricing:**
- Monthly: $2.99 / ₹149
- Yearly: $19.99 / ₹999 (best value — ~30% discount)
- Lifetime: $39.99 / ₹1,999 (for users who hate subscriptions)
- Regional pricing set via App Store / Play Store tiers

**Pro Features:**

| Feature | Description |
|---------|-------------|
| **Export PDF/Excel** | Export monthly/yearly reports as beautifully formatted PDF or Excel file |
| **Unlimited History** | Free tier keeps 6 months; Pro keeps everything forever |
| **Custom Themes** | Dark mode, Sepia (aged paper), Midnight Blue, Forest Green |
| **Recurring Expenses** | Auto-add monthly/weekly repeating entries (rent, EMI, subscriptions) |
| **Budget Alerts** | Push notifications when approaching 80%, 90%, 100% of budget |
| **Year-in-Review** | Beautiful annual summary — exportable and shareable |
| **Home Screen Widget** | Shows today's spending, remaining budget, streak (iOS + Android) |
| **Multiple Currencies** | Track expenses in different currencies with auto conversion |
| **Data Backup/Restore** | Manual export/import of all data as JSON file |
| **Category Icons** | Expanded emoji/icon picker for custom categories |

**Paywall Strategy:**
- NO hard paywall on first open — let users fall in love first
- Contextual soft paywalls: when user tries a Pro feature, show a friendly upgrade screen
- After 14 days of active use, show a one-time "Unlock Pro" nudge (dismissible, never annoying)
- Free trial: 7-day Pro trial on first upgrade tap

**Implementation:**
- Use **RevenueCat** SDK — handles both Apple StoreKit 2 and Google Play Billing
- Offerings configured remotely (can change pricing without app update)
- Free up to $2,500/month in revenue (then 1% fee)

---

## 4. Navigation Structure

```
Bottom Tab Bar (4 tabs):
├── 🏠 Home
│   ├── Header (app name + streak counter + currency picker + avatar)
│   ├── Quick Entry bar
│   ├── Budget Card (income - expenses - net)
│   ├── Expense List (grouped by date, with search/filter)
│   └── Daily Money Note
│
├── 📊 Stats
│   ├── Weekly Trend (bar chart with daily/weekly/monthly toggle)
│   ├── Category Breakdown (donut/bar toggle)
│   ├── Income vs Expense comparison
│   ├── Weekly Letter (shareable card)
│   └── Monthly Chapter (current + past months)
│
├── 🔄 Recurring (Pro badge if locked)
│   ├── Active recurring list with toggle
│   ├── Add new recurring entry
│   └── Upcoming this month
│
└── ⚙️ Settings
    ├── Currency selection
    ├── Monthly budget
    ├── Sound & haptic toggles
    ├── Daily reminder time
    ├── Theme selection (Pro)
    ├── Manage categories
    ├── Data: Export / Import / Clear All
    ├── Upgrade to Pro
    ├── Rate the app
    ├── Privacy Policy
    └── About
```

---

## 5. Onboarding Flow (First-Time User)

**Goal:** Get user from install → first expense in under 60 seconds.

```
Screen 1 (Welcome):
  "Welcome to [AppName]"
  "Your personal money diary"
  [Beautiful illustration of an open notebook with a pen]
  [Get Started →]

Screen 2 (Currency):
  "What currency do you use?"
  [₹ INR] [$  USD] [€ EUR] [£ GBP]
  (Auto-detect from device locale, user can change)
  [Next →]

Screen 3 (Budget):
  "Set a monthly budget"
  "We'll help you stay on track"
  [₹ ________]
  [Skip for now] [Set Budget →]

Screen 4 (First Entry):
  "Let's log your first expense!"
  [Pre-filled quick entry form]
  [The pen-on-paper sound plays on add — this is the "aha" moment]
  
Screen 5 (Done):
  "You're all set! 🎉"
  "Come back daily to build your streak."
  [Start Journaling →]
```

**Rules:**
- Skip button on every screen (never trap the user)
- Total time: under 45 seconds
- Onboarding only shows once (flag in AsyncStorage)

---

## 6. Sound Design Specification

### 6.1 Expense Added — Pen Scratch
- **File:** `pen-scratch.wav` (~5KB, 0.3 seconds)
- **Character:** Soft, satisfying pen-on-paper scratch. Not sharp or clicky.
- **Trigger:** On successful expense add (inside `handleAdd`)
- **Volume:** 60% of system volume
- **Source:** Royalty-free from freesound.org or similar (license: CC0)

### 6.2 Streak Milestone — Gentle Chime
- **File:** `milestone.wav` (~8KB, 0.5 seconds)
- **Character:** Warm, gentle chime — like a bell in a quiet library
- **Trigger:** When streak hits 7, 14, 30, 60, 90, 180, 365
- **Volume:** 70% of system volume

### 6.3 Delete Expense — Soft Erase
- **File:** `erase.wav` (~4KB, 0.2 seconds)
- **Character:** Soft eraser-on-paper sound
- **Trigger:** On expense delete confirmation
- **Volume:** 50% of system volume

### 6.4 Budget Warning — Subtle Alert
- **File:** None (system haptic only)
- **Character:** Medium haptic impact
- **Trigger:** When budget crosses 85% threshold

### Settings
- Master toggle: Sound ON/OFF (default ON)
- Master toggle: Haptic ON/OFF (default ON)
- Sound and haptic respect device silent mode

---

## 7. Animation Specification

### 7.1 New Expense Entry (Ink Stroke)
```javascript
// react-native-reanimated entering animation
entering: FadeInUp.duration(400).springify().damping(15).stiffness(150)
```
- New expense card slides in from top with spring physics
- Amount text does a subtle scale pulse (1 → 1.05 → 1) over 300ms
- Only the NEWLY added item animates (track via `lastAddedId` state)

### 7.2 Streak Counter Fire
- The 🔥 emoji next to streak count does a subtle bounce every time the app opens
- On milestone: the entire streak badge glows briefly (golden shadow pulse)

### 7.3 Budget Progress Bar
- Animates width from 0 to actual percentage on mount (800ms ease-out)
- Color transitions smoothly between green → yellow → red

### 7.4 Chart Transitions
- Pie chart segments animate in sequentially (staggered by 100ms each)
- Bar chart bars grow from bottom up

### 7.5 Tab Transitions
- Fade + subtle slide when switching bottom tabs
- No jarring screen swaps

### 7.6 Delete Swipe
- Expense item slides left to reveal red delete button
- On confirm: item collapses with fade-out animation

---

## 8. Notifications

### 8.1 Daily Reminder
- **Default time:** 9:00 PM (configurable in settings)
- **Message variations (rotate daily):**
  - "Time to jot down today's expenses ✏️"
  - "How did you spend today? Let's write it down 📝"
  - "Your money diary is waiting 📖"
  - "Don't break your {X}-day streak! 🔥"
- **Implementation:** expo-notifications with local scheduling

### 8.2 Budget Alert (Pro)
- Triggers when monthly spending crosses 80% and 100%
- "Heads up! You've used 80% of your March budget."

### 8.3 Weekly Letter Ready
- Every Sunday at 10 AM: "Your weekly letter is ready! 📬"

### 8.4 Recurring Expense Added
- When a recurring expense auto-logs: "Rent (₹15,000) added automatically"

---

## 9. Monetization Implementation

### Revenue Stack
```
RevenueCat SDK
├── Apple StoreKit 2 (iOS)
├── Google Play Billing (Android)
├── Offering: "pro_monthly"  — $2.99/₹149 per month
├── Offering: "pro_yearly"   — $19.99/₹999 per year
├── Offering: "pro_lifetime" — $39.99/₹1,999 one-time
└── Free trial: 7 days on first subscription
```

### Paywall Screens
- **Contextual:** User taps a Pro feature → soft paywall overlay showing what they unlock
- **Nudge:** After 14 days of active use → one-time upgrade prompt (dismiss forever)
- **Settings:** "Upgrade to Pro" row always visible in settings

### Revenue Tracking
- RevenueCat dashboard for MRR, conversions, churn
- Custom events in PostHog: "paywall_shown", "trial_started", "subscription_activated"

---

## 10. Analytics Events (PostHog)

Track these events to understand user behavior:

| Event | Properties | Why |
|-------|-----------|-----|
| `app_opened` | `streak_count`, `total_expenses` | Daily active tracking |
| `expense_added` | `category`, `payment`, `amount_range`, `has_note` | Understand logging behavior |
| `expense_edited` | `field_changed` | How often do users edit |
| `expense_deleted` | — | Mistake rate |
| `daily_note_saved` | `word_count` | Journal engagement |
| `weekly_letter_viewed` | `week_number` | Content engagement |
| `weekly_letter_shared` | `share_platform` | Viral loop tracking |
| `streak_milestone` | `milestone` (7/14/30/etc) | Retention indicator |
| `search_used` | `query_length`, `filters` | Feature usage |
| `category_created` | — | Customization depth |
| `paywall_shown` | `trigger` (feature/nudge/settings) | Conversion funnel |
| `trial_started` | — | Monetization funnel |
| `subscription_activated` | `plan` (monthly/yearly/lifetime) | Revenue |
| `onboarding_completed` | `time_seconds`, `skipped_screens` | First-run quality |
| `tab_switched` | `from_tab`, `to_tab` | Navigation patterns |

---

## 11. App Store Optimization (ASO)

### App Store Title
`[AppName] — Daily Expense Tracker & Money Journal`

### Subtitle (iOS) / Short Description (Android)
`Track spending, build habits, journal your money`

### Keywords (iOS — 100 character limit)
`expense,tracker,budget,money,diary,journal,spending,finance,daily,savings,planner,log,personal`

### Long Description (both stores)
```
[AppName] is the mindful way to track your daily expenses.

Unlike complex finance apps that connect to your bank and overwhelm you with data, [AppName] is built for people who prefer to write down their expenses — like a personal money diary.

✏️ QUICK & SATISFYING ENTRY
Log expenses in seconds with a satisfying pen-on-paper experience. Hear the ink, feel the tap, watch your entry appear.

🔥 BUILD A STREAK
Track consecutive days of logging. Watch your streak grow from 7 days to 30 to 365. Don't break the chain!

📝 DAILY MONEY NOTE
End each day with a quick reflection on your spending. Over time, build a personal finance journal that helps you understand your relationship with money.

📬 WEEKLY LETTER
Every Sunday, receive a warm, beautifully written summary of your week's spending. Share it with friends or keep it as your personal record.

📊 CLEAR INSIGHTS
Donut charts, bar charts, category breakdowns, and trends — all designed to be beautiful and easy to understand.

💰 BUDGET TRACKING
Set a monthly budget and watch a visual progress bar keep you on track. Color-coded warnings help you stay within limits.

🏷️ YOUR CATEGORIES
Create custom categories with emojis. Track payments by UPI, Card, Cash, or add your own methods.

🔒 PRIVACY FIRST
All data stays on your device. No bank connections. No account required. No data collection. Your money, your diary, your privacy.

PRO FEATURES:
• Export beautiful PDF/Excel reports
• Custom themes (Dark, Sepia, and more)
• Recurring expense automation
• Budget push notifications
• Home screen widget
• Year-in-Review report
```

### Screenshots Strategy (6 screens)
1. Home screen showing Quick Entry + Budget Card (headline: "Your money diary")
2. Expense list with ink animation highlight (headline: "Feels like pen on paper")
3. Streak counter + daily note (headline: "Build a daily habit")
4. Weekly letter card (headline: "Your weekly money story")
5. Charts — donut + bar (headline: "Know where your money goes")
6. Categories + payment types (headline: "Track it your way")

### Preview Video (30 seconds)
- Show: open app → add expense → hear sound → see ink animation → show streak → scroll charts → weekly letter → share
- Music: soft, warm acoustic background
- Text overlays: key features

---

## 12. Privacy & Legal

### Privacy Policy (Required)
- Host on GitHub Pages (free) or a simple static page
- Content: "We collect no personal data. All expense data is stored locally on your device. We use anonymous analytics (PostHog) to understand app usage patterns. No data is sold to third parties."
- Include: GDPR compliance statement, CCPA compliance, data deletion instructions (clear data in settings)

### Terms of Service (Required)
- Standard terms: usage rules, subscription terms, liability limitations
- Template available from various legal template sites

### App Store Data Declarations
- Apple: "Data Not Linked to You" — analytics only
- Google: "No data shared with third parties", "Analytics data collected"

---

## 13. Development Phases & Timeline

### Phase 1: React Native Migration & Core (Weeks 1-4)
**Goal:** Feature parity with current web app, running on both platforms.

- [ ] Initialize Expo project with React Native
- [ ] Set up React Navigation (bottom tabs)
- [ ] Migrate `useLocalStorage` → AsyncStorage wrapper
- [ ] Port Header component
- [ ] Port QuickAdd component (+ date picker + income toggle)
- [ ] Port BudgetCard component (+ income tracking)
- [ ] Port CategoryBreakdown component (react-native-chart-kit)
- [ ] Port WeeklyTrend component
- [ ] Port ExpenseList component (+ swipe to delete)
- [ ] Port SettingsView component
- [ ] Build Edit Expense modal
- [ ] Build Search/Filter bar
- [ ] Test on iOS simulator + Android emulator
- [ ] Test on physical devices (your phone)

### Phase 2: Signature Features (Weeks 5-7)
**Goal:** Add the features that make the app unique.

- [ ] Integrate expo-av for pen-scratch sound
- [ ] Integrate expo-haptics for tactile feedback
- [ ] Build ink-stroke animation (reanimated)
- [ ] Build Streak Counter (logic + UI + milestone animation)
- [ ] Build Daily Money Note component
- [ ] Build Weekly Letter generator + shareable card
- [ ] Build Monthly Chapter view
- [ ] Build Recurring Expenses manager
- [ ] Build onboarding flow (4-5 screens)
- [ ] Set up expo-notifications for daily reminder

### Phase 3: Pro & Monetization (Weeks 8-9)
**Goal:** Gate Pro features and set up subscription billing.

- [ ] Integrate RevenueCat SDK
- [ ] Create subscription products in App Store Connect + Google Play Console
- [ ] Build paywall/upgrade screens
- [ ] Gate features: export, themes, recurring, widgets, alerts, unlimited history
- [ ] Build export to PDF/Excel functionality
- [ ] Build custom themes (dark mode, sepia)
- [ ] Implement 7-day free trial flow
- [ ] Test purchase flow on both platforms (sandbox)

### Phase 4: Polish & Analytics (Weeks 10-11)
**Goal:** Production-ready quality.

- [ ] Integrate PostHog analytics
- [ ] Integrate Sentry crash reporting
- [ ] Performance optimization (list virtualization, lazy loading)
- [ ] Accessibility audit (screen reader, font scaling)
- [ ] App icon design (final)
- [ ] Splash screen
- [ ] Create App Store screenshots (6 per device size)
- [ ] Create preview video
- [ ] Write App Store description + keywords
- [ ] Privacy policy + terms of service pages
- [ ] Manual backup/restore (JSON export/import)

### Phase 5: Launch (Week 12)
**Goal:** Live on both stores.

- [ ] Apple Developer Account ($99)
- [ ] Google Play Developer Account ($25)
- [ ] EAS Build — production builds for both platforms
- [ ] Submit to Apple App Store (expect 1-3 day review)
- [ ] Submit to Google Play Store (expect 1-2 day review)
- [ ] Post on Reddit (r/sideproject, r/personalfinance, r/india, r/reactnative)
- [ ] Post on Twitter/X with demo video
- [ ] Submit to Product Hunt
- [ ] Tell friends & family — ask for honest reviews

### Phase 6: Post-Launch (Ongoing)
**Goal:** Iterate based on real user feedback.

- [ ] Monitor PostHog for user behavior patterns
- [ ] Monitor crash reports in Sentry
- [ ] Respond to App Store reviews
- [ ] A/B test paywall placement and pricing
- [ ] Evaluate paid ads once organic traction is established
- [ ] Based on demand: plan Shared Notebook (v2.0)
- [ ] Home screen widgets (iOS WidgetKit, Android Glance)

---

## 14. Budget Summary

| Item | Cost | When |
|------|------|------|
| Apple Developer Account | $99/year (~₹8,300) | Phase 5 |
| Google Play Developer Account | $25 one-time (~₹2,100) | Phase 5 |
| RevenueCat | Free (up to $2,500/mo revenue) | Phase 3 |
| PostHog Analytics | Free (up to 1M events/mo) | Phase 4 |
| Sentry Crash Reporting | Free (up to 5K events/mo) | Phase 4 |
| Expo / EAS Build | Free tier (limited builds) | Phase 1 |
| Sound effects (royalty-free) | Free (CC0 from freesound.org) | Phase 2 |
| App icon design | ₹0-5,000 (DIY or Fiverr) | Phase 4 |
| Privacy policy hosting | Free (GitHub Pages) | Phase 4 |
| **Total to launch** | **~₹10,400 - ₹15,400** | |

### Monthly Running Costs (Post-Launch)
| Item | Cost |
|------|------|
| Apple Developer Account | ~₹700/month (amortized) |
| Everything else | Free at launch scale |
| **Total** | **~₹700/month** |

---

## 15. Success Metrics

### Month 1
- App live on both stores ✓
- 100+ downloads
- 4.0+ star rating
- 20+ daily active users

### Month 3
- 1,000+ total downloads
- 50+ daily active users
- 10+ Pro subscribers
- Average streak > 7 days for active users

### Month 6
- 5,000+ total downloads
- 200+ daily active users
- 50+ Pro subscribers
- First $100 MRR

### Month 12
- 20,000+ total downloads
- 500+ daily active users
- 200+ Pro subscribers
- $500+ MRR
- Decision point: invest in Shared Notebook (v2) or double down on personal features

---

## 16. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| App Store rejection | Medium | High | Follow Apple HIG strictly, test with TestFlight first |
| Low downloads | High | Medium | Strong ASO + organic sharing + Reddit/PH launch |
| Low Pro conversion | Medium | High | Test pricing, improve paywall timing, add more Pro value |
| React Native performance | Low | Medium | Use Hermes engine, optimize re-renders, virtualize lists |
| Competitor copies the journal angle | Low | Low | First-mover advantage + brand loyalty + streak data lock-in |
| User data loss (phone change) | Medium | High | Build export/import early, add cloud backup in v2 |

---

## 17. Future Roadmap (Post v1)

### v1.1 — Quick Wins from User Feedback
- Bug fixes from initial reviews
- Small UX improvements
- More chart types

### v1.5 — Widgets & Polish
- Home screen widgets (iOS + Android)
- Apple Watch complication (shows today's spend)
- Improved animations

### v2.0 — Shared Notebook
- Invite partner/family via code
- Real-time sync (Firebase Realtime DB or Supabase)
- Shared budget with individual contributions
- Combined weekly letter ("Together, you spent...")
- Backend: Firebase Auth (Google/Apple sign-in) + Firestore

### v2.5 — Intelligence
- AI-powered monthly insights ("You spend 40% more on food on weekends")
- Smart categorization suggestions based on note text
- Anomaly detection ("This expense is 3x your average for Transport")

### v3.0 — Platform
- API for third-party integrations
- CSV/bank statement import (manual upload, not live sync)
- Multi-language support (Hindi, Spanish, Portuguese, Japanese, Korean, German)
- Localized onboarding and App Store listings

---

*Document version: 1.0*
*Last updated: March 22, 2026*
*Author: Product planning session with Claude*
