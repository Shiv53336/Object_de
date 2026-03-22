import { useState, useEffect } from "react";
import {
  PieChart, Pie, Cell,
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer
} from "recharts";

// ─── Constants ────────────────────────────────────────────────────────────────

const CURRENCIES = { "₹": "INR", "$": "USD", "€": "EUR", "£": "GBP" };

const DEFAULT_EXPENSE_CATEGORIES = [
  { name: "Food & Dining",     emoji: "🍜", color: "#E07A5F", budget: 8000, type: "expense" },
  { name: "Transport",         emoji: "🛺", color: "#3D405B", budget: 3000, type: "expense" },
  { name: "Shopping",          emoji: "🛍️", color: "#81B29A", budget: 5000, type: "expense" },
  { name: "Bills & Utilities", emoji: "💡", color: "#F2CC8F", budget: 6000, type: "expense" },
  { name: "Entertainment",     emoji: "🎮", color: "#7B68EE", budget: 2000, type: "expense" },
  { name: "Health",            emoji: "💊", color: "#E88D97", budget: 2000, type: "expense" },
];

const DEFAULT_INCOME_CATEGORIES = [
  { name: "Salary",     emoji: "💼", color: "#81B29A", budget: 0, type: "income" },
  { name: "Freelance",  emoji: "💻", color: "#2A9D8F", budget: 0, type: "income" },
  { name: "Investment", emoji: "📈", color: "#F2CC8F", budget: 0, type: "income" },
  { name: "Gift",       emoji: "🎁", color: "#E88D97", budget: 0, type: "income" },
  { name: "Other",      emoji: "💰", color: "#6C63FF", budget: 0, type: "income" },
];

const DEFAULT_CATEGORIES = [...DEFAULT_EXPENSE_CATEGORIES, ...DEFAULT_INCOME_CATEGORIES];

const PAYMENT_TYPES = [
  { label: "UPI",  icon: "📱", color: "#6C63FF" },
  { label: "Card", icon: "💳", color: "#E07A5F" },
  { label: "Cash", icon: "💵", color: "#81B29A" },
];

const RAND_COLORS = [
  "#E07A5F","#3D405B","#81B29A","#F2CC8F","#7B68EE",
  "#E88D97","#6C63FF","#F4A261","#2A9D8F","#E76F51",
];

const DEFAULT_BUDGET = 26000;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function useLocalStorage(key, initial) {
  const [value, setValue] = useState(() => {
    try {
      const stored = localStorage.getItem(key);
      return stored ? JSON.parse(stored) : initial;
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    localStorage.setItem(key, JSON.stringify(value));
  }, [key, value]);
  return [value, setValue];
}

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function yesterdayStr() {
  return new Date(Date.now() - 86400000).toISOString().slice(0, 10);
}

function dateLabel(dateStr) {
  const today     = todayStr();
  const yesterday = yesterdayStr();
  if (dateStr === today)     return "Today";
  if (dateStr === yesterday) return "Yesterday";
  return dateStr;
}

function getBudgetColor(pct) {
  if (pct < 60) return "#81B29A";
  if (pct < 85) return "#F2CC8F";
  return "#E07A5F";
}

function paymentColor(p) {
  if (p === "UPI")  return { bg: "#6C63FF18", fg: "#6C63FF" };
  if (p === "Card") return { bg: "#E07A5F18", fg: "#E07A5F" };
  if (p === "Cash") return { bg: "#81B29A18", fg: "#81B29A" };
  return { bg: "#EDE8E1", fg: "#8B8580" };
}

function paymentIcon(p) {
  if (p === "UPI")  return "📱";
  if (p === "Card") return "💳";
  if (p === "Cash") return "💵";
  return "💸";
}

// ─── Header ───────────────────────────────────────────────────────────────────

function Header({ currency, setCurrency, streak }) {
  const { currentStreak = 0, longestStreak = 0 } = streak || {};
  return (
    <div style={{ padding: "24px 20px 16px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <div>
        <h1 style={{ fontFamily: "'Caveat', cursive", fontSize: 32, fontWeight: 600, color: "#2D2A26", margin: 0, letterSpacing: -0.5 }}>
          My Expenses
        </h1>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, color: "#8B8580", margin: "2px 0 0" }}>
          {new Date().toLocaleDateString("en-US", { month: "long", year: "numeric" })}
        </p>
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        {/* Streak badge */}
        {currentStreak > 0 && (
          <div
            title={`Longest streak: ${longestStreak} days`}
            style={{ display: "flex", alignItems: "center", gap: 4, background: "#FFF8E1", border: "1px solid #F2CC8F", borderRadius: 20, padding: "5px 10px", cursor: "default" }}
          >
            <span style={{ fontSize: 14 }}>🔥</span>
            <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: 700, color: "#C8960C" }}>
              {currentStreak} {currentStreak === 1 ? "day" : "days"}
            </span>
          </div>
        )}
        <select
          value={currency}
          onChange={e => setCurrency(e.target.value)}
          style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 14, background: "#fff", border: "1px solid #E0D8CF", borderRadius: 10, padding: "6px 10px", color: "#2D2A26", cursor: "pointer", outline: "none" }}
        >
          {Object.entries(CURRENCIES).map(([sym, code]) => (
            <option key={sym} value={sym}>{sym} {code}</option>
          ))}
        </select>
      </div>
    </div>
  );
}

// ─── Quick Add ────────────────────────────────────────────────────────────────

function QuickAdd({ currency, categories, onAdd }) {
  const [amount,    setAmount]    = useState("");
  const [cat,       setCat]       = useState("");
  const [note,      setNote]      = useState("");
  const [payment,   setPayment]   = useState("UPI");
  const [customPay, setCustomPay] = useState("");
  const [entryType, setEntryType] = useState("expense");
  const [date,      setDate]      = useState(todayStr());

  const filteredCats = categories.filter(c => c.type === entryType);

  useEffect(() => {
    const fc = categories.filter(c => c.type === entryType);
    if (fc.length && !fc.find(c => c.name === cat)) {
      setCat(fc[0].name);
    }
  }, [categories, entryType]);

  const handleAdd = () => {
    const num = parseFloat(amount);
    if (!num || num <= 0) return;
    const catObj = categories.find(c => c.name === cat) || filteredCats[0];
    onAdd({
      id:       Date.now(),
      amount:   num,
      category: cat || catObj?.name,
      note:     note || cat || catObj?.name,
      date,
      emoji:    catObj?.emoji || "💸",
      payment:  entryType === "income" ? "—" : (payment === "Other" ? (customPay || "Other") : payment),
      type:     entryType,
    });
    setAmount("");
    setNote("");
    setDate(todayStr());
  };

  const accentColor = entryType === "expense" ? "#E07A5F" : "#81B29A";

  return (
    <div style={{ margin: "0 16px 16px", background: "#fff", borderRadius: 16, padding: 16, boxShadow: "0 2px 12px rgba(45,42,38,0.06)", border: "1px solid #EDE8E1" }}>
      {/* Header row: title + expense/income toggle */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <p style={{ fontFamily: "'Caveat', cursive", fontSize: 18, color: "#8B8580", margin: 0 }}>✏️ Quick Entry</p>
        <div style={{ display: "flex", background: "#FAF6F1", borderRadius: 20, padding: 3, border: "1px solid #EDE8E1" }}>
          {[{ key: "expense", label: "Expense" }, { key: "income", label: "Income" }].map(t => (
            <button
              key={t.key}
              onClick={() => setEntryType(t.key)}
              style={{
                fontFamily: "'DM Sans', sans-serif", fontSize: 12, padding: "4px 14px",
                border: "none", borderRadius: 16, cursor: "pointer", fontWeight: 600,
                background: entryType === t.key ? (t.key === "expense" ? "#E07A5F" : "#81B29A") : "transparent",
                color: entryType === t.key ? "#fff" : "#8B8580",
                transition: "all 0.2s",
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Amount + category + add button */}
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <div style={{ flex: 1, display: "flex", alignItems: "center", background: "#FAF6F1", borderRadius: 10, padding: "10px 12px", border: `1px solid ${accentColor}44` }}>
          <span style={{ fontSize: 18, marginRight: 6, color: accentColor }}>{currency}</span>
          <input
            type="number"
            value={amount}
            onChange={e => setAmount(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleAdd()}
            placeholder="0"
            style={{ border: "none", background: "transparent", fontSize: 20, fontFamily: "'Crimson Pro', serif", fontWeight: 600, color: "#2D2A26", width: "100%", outline: "none" }}
          />
        </div>
        <select
          value={cat}
          onChange={e => setCat(e.target.value)}
          style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, background: "#FAF6F1", border: "1px solid #EDE8E1", borderRadius: 10, padding: "10px 10px", color: "#2D2A26", outline: "none" }}
        >
          {filteredCats.map(c => (
            <option key={c.name} value={c.name}>{c.emoji} {c.name.split(" ")[0]}</option>
          ))}
        </select>
        <button
          onClick={handleAdd}
          style={{ background: accentColor, color: "#fff", border: "none", borderRadius: 10, padding: "10px 16px", fontFamily: "'DM Sans', sans-serif", fontSize: 14, fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap" }}
        >
          Add
        </button>
      </div>

      {/* Note + date picker */}
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <input
          value={note}
          onChange={e => setNote(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleAdd()}
          placeholder="Add a note..."
          style={{ flex: 1, border: "1px solid #EDE8E1", background: "#FAF6F1", borderRadius: 8, padding: "8px 12px", fontFamily: "'DM Sans', sans-serif", fontSize: 13, color: "#2D2A26", outline: "none" }}
        />
        <input
          type="date"
          value={date}
          max={todayStr()}
          onChange={e => setDate(e.target.value)}
          style={{ border: "1px solid #EDE8E1", background: "#FAF6F1", borderRadius: 8, padding: "8px 10px", fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#2D2A26", outline: "none", cursor: "pointer" }}
        />
      </div>

      {/* Payment type (expenses only) */}
      {entryType === "expense" && (
        <div style={{ marginTop: 10, display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#8B8580", marginRight: 2 }}>Paid via:</span>
          {PAYMENT_TYPES.map(pt => (
            <button
              key={pt.label}
              onClick={() => { setPayment(pt.label); setCustomPay(""); }}
              style={{ padding: "5px 12px", borderRadius: 20, border: payment === pt.label ? `2px solid ${pt.color}` : "1px solid #EDE8E1", background: payment === pt.label ? `${pt.color}14` : "#FAF6F1", fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: payment === pt.label ? 600 : 400, color: payment === pt.label ? pt.color : "#8B8580", cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}
            >
              {pt.icon} {pt.label}
            </button>
          ))}
          <button
            onClick={() => setPayment("Other")}
            style={{ padding: "5px 12px", borderRadius: 20, border: payment === "Other" ? "2px solid #3D405B" : "1px solid #EDE8E1", background: payment === "Other" ? "#3D405B14" : "#FAF6F1", fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: payment === "Other" ? 600 : 400, color: payment === "Other" ? "#3D405B" : "#8B8580", cursor: "pointer" }}
          >
            ✍️ Other
          </button>
          {payment === "Other" && (
            <input
              placeholder="e.g. Wallet, Bank Transfer..."
              value={customPay}
              onChange={e => setCustomPay(e.target.value)}
              style={{ flex: 1, minWidth: 140, padding: "5px 10px", borderRadius: 20, border: "1px solid #3D405B", background: "#FAF6F1", fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#2D2A26", outline: "none" }}
            />
          )}
        </div>
      )}
    </div>
  );
}

// ─── Budget Card ──────────────────────────────────────────────────────────────

function BudgetCard({ currency, expenses, totalBudget, categories }) {
  const now       = new Date();
  const monthStr  = todayStr().slice(0, 7);
  const daysLeft  = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate() - now.getDate();

  const monthExp = expenses.filter(e => e.date?.startsWith(monthStr));
  const totalExpenses = monthExp.filter(e => e.type !== "income").reduce((s, e) => s + e.amount, 0);
  const totalIncome   = monthExp.filter(e => e.type === "income").reduce((s, e) => s + e.amount, 0);
  const netBalance    = totalIncome - totalExpenses;

  const pct   = Math.min(100, Math.round((totalExpenses / totalBudget) * 100));
  const color = getBudgetColor(pct);

  const expCats = categories.filter(c => c.type !== "income" && c.budget > 0);

  return (
    <div style={{ margin: "0 16px 16px", background: "#fff", borderRadius: 16, padding: 16, boxShadow: "0 2px 12px rgba(45,42,38,0.06)", border: "1px solid #EDE8E1" }}>

      {/* Income / Expenses / Net row */}
      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        <div style={{ flex: 1, background: "#F0F9F5", borderRadius: 10, padding: "10px 12px" }}>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 10, color: "#81B29A", margin: "0 0 3px", fontWeight: 700, letterSpacing: 0.5 }}>INCOME</p>
          <p style={{ fontFamily: "'Crimson Pro', serif", fontSize: 17, fontWeight: 700, color: "#81B29A", margin: 0 }}>{currency}{totalIncome.toLocaleString()}</p>
        </div>
        <div style={{ flex: 1, background: "#FFF1EE", borderRadius: 10, padding: "10px 12px" }}>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 10, color: "#E07A5F", margin: "0 0 3px", fontWeight: 700, letterSpacing: 0.5 }}>EXPENSES</p>
          <p style={{ fontFamily: "'Crimson Pro', serif", fontSize: 17, fontWeight: 700, color: "#E07A5F", margin: 0 }}>{currency}{totalExpenses.toLocaleString()}</p>
        </div>
        <div style={{ flex: 1, background: netBalance >= 0 ? "#F0F9F5" : "#FFF1EE", borderRadius: 10, padding: "10px 12px" }}>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 10, color: netBalance >= 0 ? "#81B29A" : "#E07A5F", margin: "0 0 3px", fontWeight: 700, letterSpacing: 0.5 }}>NET</p>
          <p style={{ fontFamily: "'Crimson Pro', serif", fontSize: 17, fontWeight: 700, color: netBalance >= 0 ? "#81B29A" : "#E07A5F", margin: 0 }}>
            {netBalance >= 0 ? "+" : ""}{currency}{netBalance.toLocaleString()}
          </p>
        </div>
      </div>

      {/* Budget progress bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <span style={{ fontFamily: "'Caveat', cursive", fontSize: 16, color: "#8B8580" }}>📊 Monthly Budget</span>
        <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color, fontWeight: 600, background: `${color}18`, padding: "2px 7px", borderRadius: 6 }}>
          {pct}% used
        </span>
      </div>
      <div style={{ height: 8, background: "#EDE8E1", borderRadius: 10, overflow: "hidden", marginBottom: 6 }}>
        <div style={{ height: "100%", width: `${pct}%`, background: `linear-gradient(90deg, ${color}, ${color}cc)`, borderRadius: 10, transition: "width 0.8s ease" }} />
      </div>
      <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#8B8580", margin: "0 0 12px" }}>
        {currency}{totalExpenses.toLocaleString()} of {currency}{totalBudget.toLocaleString()} • {daysLeft} days left
      </p>

      {/* Per-category mini bars */}
      {expCats.length > 0 && (
        <div style={{ borderTop: "1px solid #EDE8E1", paddingTop: 10 }}>
          {expCats.slice(0, 4).map(c => {
            const spent   = monthExp.filter(e => e.category === c.name && e.type !== "income").reduce((s, e) => s + e.amount, 0);
            const catPct  = Math.min(100, Math.round((spent / c.budget) * 100));
            const catColor = catPct > 85 ? "#E07A5F" : c.color;
            return (
              <div key={c.name} style={{ marginBottom: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                  <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#5A5550" }}>{c.emoji} {c.name}</span>
                  <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: catPct > 85 ? "#E07A5F" : "#8B8580" }}>
                    {currency}{spent.toLocaleString()} / {currency}{c.budget.toLocaleString()}
                  </span>
                </div>
                <div style={{ height: 4, background: "#EDE8E1", borderRadius: 4, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${catPct}%`, background: catColor, borderRadius: 4, transition: "width 0.6s ease" }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Edit Modal ───────────────────────────────────────────────────────────────

function EditModal({ expense, categories, currency, onSave, onDelete, onClose }) {
  const [amount,  setAmount]  = useState(String(expense.amount));
  const [cat,     setCat]     = useState(expense.category);
  const [note,    setNote]    = useState(expense.note);
  const [payment, setPayment] = useState(expense.payment || "UPI");
  const [date,    setDate]    = useState(expense.date);

  const isIncome    = expense.type === "income";
  const filteredCats = categories.filter(c => c.type === (isIncome ? "income" : "expense"));

  const handleSave = () => {
    const num = parseFloat(amount);
    if (!num || num <= 0) return;
    const catObj = categories.find(c => c.name === cat);
    onSave({ ...expense, amount: num, category: cat, note: note || cat, payment, date, emoji: catObj?.emoji || expense.emoji });
    onClose();
  };

  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 300, display: "flex", alignItems: "flex-end", justifyContent: "center" }}
      onClick={onClose}
    >
      <div
        style={{ background: "#FAF6F1", borderRadius: "20px 20px 0 0", padding: "20px 20px 36px", width: "100%", maxWidth: 480, boxSizing: "border-box" }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <p style={{ fontFamily: "'Caveat', cursive", fontSize: 20, color: "#2D2A26", margin: 0 }}>
            {isIncome ? "✏️ Edit Income" : "✏️ Edit Expense"}
          </p>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 18, cursor: "pointer", color: "#8B8580" }}>✕</button>
        </div>

        {/* Amount + category */}
        <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
          <div style={{ flex: 1, display: "flex", alignItems: "center", background: "#fff", borderRadius: 10, padding: "10px 12px", border: "1px solid #EDE8E1" }}>
            <span style={{ fontSize: 18, marginRight: 6, color: "#8B8580" }}>{currency}</span>
            <input
              type="number"
              value={amount}
              onChange={e => setAmount(e.target.value)}
              style={{ border: "none", background: "transparent", fontSize: 20, fontFamily: "'Crimson Pro', serif", fontWeight: 600, color: "#2D2A26", width: "100%", outline: "none" }}
            />
          </div>
          <select
            value={cat}
            onChange={e => setCat(e.target.value)}
            style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, background: "#fff", border: "1px solid #EDE8E1", borderRadius: 10, padding: "10px", color: "#2D2A26", outline: "none" }}
          >
            {filteredCats.map(c => <option key={c.name} value={c.name}>{c.emoji} {c.name}</option>)}
          </select>
        </div>

        {/* Note + date */}
        <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
          <input
            value={note}
            onChange={e => setNote(e.target.value)}
            placeholder="Note..."
            style={{ flex: 1, border: "1px solid #EDE8E1", background: "#fff", borderRadius: 8, padding: "8px 12px", fontFamily: "'DM Sans', sans-serif", fontSize: 13, color: "#2D2A26", outline: "none" }}
          />
          <input
            type="date"
            value={date}
            max={todayStr()}
            onChange={e => setDate(e.target.value)}
            style={{ border: "1px solid #EDE8E1", background: "#fff", borderRadius: 8, padding: "8px 10px", fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#2D2A26", outline: "none" }}
          />
        </div>

        {/* Payment type (expenses only) */}
        {!isIncome && (
          <div style={{ display: "flex", gap: 6, marginBottom: 16, flexWrap: "wrap" }}>
            {PAYMENT_TYPES.map(pt => (
              <button
                key={pt.label}
                onClick={() => setPayment(pt.label)}
                style={{ padding: "5px 12px", borderRadius: 20, border: payment === pt.label ? `2px solid ${pt.color}` : "1px solid #EDE8E1", background: payment === pt.label ? `${pt.color}14` : "#fff", fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: payment === pt.label ? 600 : 400, color: payment === pt.label ? pt.color : "#8B8580", cursor: "pointer" }}
              >
                {pt.icon} {pt.label}
              </button>
            ))}
          </div>
        )}

        {/* Save + Delete buttons */}
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={handleSave}
            style={{ flex: 1, background: "#3D405B", color: "#FAF6F1", border: "none", borderRadius: 12, padding: "12px", fontFamily: "'DM Sans', sans-serif", fontSize: 14, fontWeight: 600, cursor: "pointer" }}
          >
            Save Changes
          </button>
          <button
            onClick={() => { onDelete(expense.id); onClose(); }}
            style={{ background: "#E07A5F18", border: "1px solid #E07A5F55", borderRadius: 12, padding: "12px 18px", fontFamily: "'DM Sans', sans-serif", fontSize: 13, color: "#E07A5F", cursor: "pointer", fontWeight: 600 }}
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Category Breakdown ───────────────────────────────────────────────────────

function CategoryBreakdown({ currency, categories, expenses, onAddCategory }) {
  const [chartType,   setChartType]   = useState("donut");
  const [showAddCat,  setShowAddCat]  = useState(false);
  const [newEmoji,    setNewEmoji]    = useState("");
  const [newName,     setNewName]     = useState("");
  const [newBudget,   setNewBudget]   = useState("");

  const catSpend = categories.map(c => ({
    ...c,
    spent: expenses.filter(e => e.category === c.name).reduce((s, e) => s + e.amount, 0),
  }));

  const pieData = catSpend.filter(c => c.spent > 0).map(c => ({ name: c.name, value: c.spent, color: c.color }));

  const handleSave = () => {
    if (!newName.trim()) return;
    onAddCategory({
      name:   newName.trim(),
      emoji:  newEmoji || "🏷️",
      color:  RAND_COLORS[Math.floor(Math.random() * RAND_COLORS.length)],
      budget: parseFloat(newBudget) || 1000,
    });
    setNewEmoji(""); setNewName(""); setNewBudget(""); setShowAddCat(false);
  };

  return (
    <div style={{ margin: "0 16px 16px", background: "#fff", borderRadius: 16, padding: 16, boxShadow: "0 2px 12px rgba(45,42,38,0.06)", border: "1px solid #EDE8E1" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <p style={{ fontFamily: "'Caveat', cursive", fontSize: 18, color: "#8B8580", margin: 0 }}>🏷️ By Category</p>
        <div style={{ display: "flex", background: "#FAF6F1", borderRadius: 8, padding: 2 }}>
          {["donut", "bar"].map(t => (
            <button key={t} onClick={() => setChartType(t)} style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, padding: "4px 10px", border: "none", borderRadius: 6, background: chartType === t ? "#3D405B" : "transparent", color: chartType === t ? "#FAF6F1" : "#8B8580", cursor: "pointer", fontWeight: 500 }}>
              {t === "donut" ? "Donut" : "Bar"}
            </button>
          ))}
        </div>
      </div>

      {chartType === "donut" ? (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <ResponsiveContainer width="50%" height={160}>
            <PieChart>
              <Pie data={pieData.length ? pieData : [{ name: "empty", value: 1, color: "#EDE8E1" }]} cx="50%" cy="50%" innerRadius={40} outerRadius={65} dataKey="value" stroke="none">
                {(pieData.length ? pieData : [{ color: "#EDE8E1" }]).map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div style={{ flex: 1 }}>
            {catSpend.map(c => (
              <div key={c.name} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: c.color, flexShrink: 0 }} />
                <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#5A5550", flex: 1 }}>{c.emoji} {c.name.split(" ")[0]}</span>
                <span style={{ fontFamily: "'Crimson Pro', serif", fontSize: 12, fontWeight: 600, color: "#2D2A26" }}>{currency}{c.spent.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={catSpend.map(c => ({ name: c.emoji, spent: c.spent, color: c.color }))}>
            <XAxis dataKey="name" tick={{ fontSize: 14 }} axisLine={false} tickLine={false} />
            <YAxis hide />
            <Tooltip formatter={v => [`${currency}${v.toLocaleString()}`, "Spent"]} contentStyle={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, borderRadius: 8, border: "1px solid #EDE8E1" }} />
            <Bar dataKey="spent" radius={[6, 6, 0, 0]}>
              {catSpend.map((c, i) => <Cell key={i} fill={c.color} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}

      <button onClick={() => setShowAddCat(!showAddCat)} style={{ marginTop: 10, width: "100%", padding: "8px", background: "transparent", border: "1px dashed #CCC5BB", borderRadius: 8, fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#8B8580", cursor: "pointer" }}>
        + Add Custom Category
      </button>

      {showAddCat && (
        <div style={{ marginTop: 8, padding: 12, background: "#FAF6F1", borderRadius: 10, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <input value={newEmoji} onChange={e => setNewEmoji(e.target.value)} placeholder="🏷️" maxLength={2} style={{ width: 40, padding: "6px", borderRadius: 6, border: "1px solid #EDE8E1", textAlign: "center", fontSize: 16, outline: "none", background: "#fff" }} />
          <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="Category name" style={{ flex: 1, padding: "6px 10px", borderRadius: 6, border: "1px solid #EDE8E1", fontFamily: "'DM Sans', sans-serif", fontSize: 13, outline: "none", background: "#fff" }} />
          <input type="number" value={newBudget} onChange={e => setNewBudget(e.target.value)} placeholder="Budget" style={{ width: 80, padding: "6px 10px", borderRadius: 6, border: "1px solid #EDE8E1", fontFamily: "'DM Sans', sans-serif", fontSize: 13, outline: "none", background: "#fff" }} />
          <button onClick={handleSave} style={{ background: "#81B29A", color: "#fff", border: "none", borderRadius: 6, padding: "6px 12px", fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Save</button>
        </div>
      )}
    </div>
  );
}

// ─── Weekly Trend ─────────────────────────────────────────────────────────────

function WeeklyTrend({ currency, expenses }) {
  const [activeTab, setActiveTab] = useState("daily");

  const weeklyData = Array.from({ length: 7 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - (6 - i));
    const dateStr = d.toISOString().slice(0, 10);
    const amount  = expenses.filter(e => e.date === dateStr).reduce((s, e) => s + e.amount, 0);
    return { day: d.toLocaleDateString("en-US", { weekday: "short" }), amount };
  });

  const totalWeek = weeklyData.reduce((s, d) => s + d.amount, 0);
  const avgDay    = Math.round(totalWeek / 7);
  const highest   = weeklyData.reduce((a, b) => a.amount >= b.amount ? a : b, { day: "—", amount: 0 });

  return (
    <div style={{ margin: "0 16px 16px", background: "#fff", borderRadius: 16, padding: 16, boxShadow: "0 2px 12px rgba(45,42,38,0.06)", border: "1px solid #EDE8E1" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <p style={{ fontFamily: "'Caveat', cursive", fontSize: 18, color: "#8B8580", margin: 0 }}>📈 This Week</p>
        <div style={{ display: "flex", background: "#FAF6F1", borderRadius: 8, padding: 2 }}>
          {["daily", "weekly", "monthly"].map(t => (
            <button key={t} onClick={() => setActiveTab(t)} style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, padding: "4px 8px", border: "none", borderRadius: 6, cursor: "pointer", fontWeight: 500, background: activeTab === t ? "#3D405B" : "transparent", color: activeTab === t ? "#FAF6F1" : "#8B8580" }}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={weeklyData}>
          <XAxis dataKey="day" tick={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, fill: "#8B8580" }} axisLine={false} tickLine={false} />
          <YAxis hide />
          <Tooltip formatter={v => [`${currency}${v.toLocaleString()}`, ""]} contentStyle={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, borderRadius: 8, border: "1px solid #EDE8E1" }} />
          <Bar dataKey="amount" fill="#3D405B" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
      <div style={{ display: "flex", justifyContent: "space-around", marginTop: 8, padding: "8px 0", borderTop: "1px solid #EDE8E1" }}>
        <div style={{ textAlign: "center" }}>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#8B8580", margin: 0 }}>Avg/day</p>
          <p style={{ fontFamily: "'Crimson Pro', serif", fontSize: 18, fontWeight: 700, color: "#2D2A26", margin: "2px 0 0" }}>{currency}{avgDay.toLocaleString()}</p>
        </div>
        <div style={{ textAlign: "center" }}>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#8B8580", margin: 0 }}>This week</p>
          <p style={{ fontFamily: "'Crimson Pro', serif", fontSize: 18, fontWeight: 700, color: "#2D2A26", margin: "2px 0 0" }}>{currency}{totalWeek.toLocaleString()}</p>
        </div>
        <div style={{ textAlign: "center" }}>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#8B8580", margin: 0 }}>Highest</p>
          <p style={{ fontFamily: "'Crimson Pro', serif", fontSize: 18, fontWeight: 700, color: "#E07A5F", margin: "2px 0 0" }}>{highest.amount > 0 ? highest.day : "—"}</p>
        </div>
      </div>
    </div>
  );
}

// ─── Expense List ─────────────────────────────────────────────────────────────

function ExpenseList({ currency, expenses, categories, onDelete, onEdit }) {
  const [search,    setSearch]    = useState("");
  const [filterCat, setFilterCat] = useState("All");
  const [sortBy,    setSortBy]    = useState("newest");

  // Filter
  let filtered = expenses.filter(e => {
    const matchSearch = !search ||
      e.note?.toLowerCase().includes(search.toLowerCase()) ||
      e.category?.toLowerCase().includes(search.toLowerCase());
    const matchCat = filterCat === "All" || e.category === filterCat;
    return matchSearch && matchCat;
  });

  // Sort
  filtered = filtered.slice().sort((a, b) => {
    if (sortBy === "newest")  return b.date.localeCompare(a.date) || b.id - a.id;
    if (sortBy === "oldest")  return a.date.localeCompare(b.date) || a.id - b.id;
    if (sortBy === "highest") return b.amount - a.amount;
    if (sortBy === "lowest")  return a.amount - b.amount;
    return 0;
  });

  // Group by date label
  const grouped = filtered.reduce((acc, exp) => {
    const label = dateLabel(exp.date);
    if (!acc[label]) acc[label] = [];
    acc[label].push(exp);
    return acc;
  }, {});

  const uniqueCats = ["All", ...new Set(expenses.map(e => e.category))];

  return (
    <div style={{ margin: "0 16px 16px" }}>

      {/* Search bar */}
      <div style={{ background: "#fff", borderRadius: 12, padding: "8px 12px", border: "1px solid #EDE8E1", display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 14 }}>🔍</span>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search expenses..."
          style={{ flex: 1, border: "none", background: "transparent", fontFamily: "'DM Sans', sans-serif", fontSize: 13, color: "#2D2A26", outline: "none" }}
        />
        <select
          value={sortBy}
          onChange={e => setSortBy(e.target.value)}
          style={{ border: "none", background: "transparent", fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#8B8580", cursor: "pointer", outline: "none" }}
        >
          <option value="newest">Newest</option>
          <option value="oldest">Oldest</option>
          <option value="highest">Highest</option>
          <option value="lowest">Lowest</option>
        </select>
      </div>

      {/* Category filter chips */}
      <div style={{ display: "flex", gap: 6, overflowX: "auto", paddingBottom: 6, marginBottom: 10 }}>
        {uniqueCats.slice(0, 7).map(c => {
          const catObj = categories.find(cat => cat.name === c);
          return (
            <button
              key={c}
              onClick={() => setFilterCat(c)}
              style={{
                padding: "4px 12px", borderRadius: 20, flexShrink: 0,
                border: filterCat === c ? "2px solid #3D405B" : "1px solid #EDE8E1",
                background: filterCat === c ? "#3D405B" : "#fff",
                fontFamily: "'DM Sans', sans-serif", fontSize: 11,
                fontWeight: filterCat === c ? 600 : 400,
                color: filterCat === c ? "#FAF6F1" : "#8B8580",
                cursor: "pointer", whiteSpace: "nowrap",
              }}
            >
              {c === "All" ? "All" : `${catObj?.emoji || ""} ${c.split(" ")[0]}`}
            </button>
          );
        })}
      </div>

      {/* List header */}
      <p style={{ fontFamily: "'Caveat', cursive", fontSize: 18, color: "#8B8580", margin: "0 0 10px" }}>📝 Recent Entries</p>

      {filtered.length === 0 ? (
        <div style={{ textAlign: "center", padding: 32, color: "#8B8580", fontFamily: "'DM Sans', sans-serif", fontSize: 14 }}>
          {expenses.length === 0 ? "No entries yet. Add your first one above! 👆" : "No entries match your filter."}
        </div>
      ) : (
        Object.entries(grouped).map(([date, exps]) => (
          <div key={date} style={{ marginBottom: 12 }}>
            <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: 600, color: "#8B8580", margin: "0 0 6px", textTransform: "uppercase", letterSpacing: 0.5 }}>
              {date}
            </p>
            {exps.map(exp => {
              const isIncome = exp.type === "income";
              const pc = paymentColor(exp.payment);
              return (
                <div
                  key={exp.id}
                  onClick={() => onEdit(exp)}
                  style={{
                    background: "#fff", borderRadius: 12, padding: "12px 14px", marginBottom: 6,
                    display: "flex", alignItems: "center", gap: 12,
                    boxShadow: "0 1px 4px rgba(45,42,38,0.04)",
                    border: `1px solid ${isIncome ? "#C8E6C9" : "#EDE8E1"}`,
                    cursor: "pointer",
                  }}
                >
                  <div style={{ width: 38, height: 38, borderRadius: 10, background: isIncome ? "#F0F9F5" : "#FAF6F1", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, flexShrink: 0 }}>
                    {exp.emoji}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 500, color: "#2D2A26", margin: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {exp.note}
                    </p>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3 }}>
                      <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#8B8580" }}>{exp.category}</span>
                      {!isIncome && exp.payment && exp.payment !== "—" && (
                        <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 9, fontWeight: 600, padding: "2px 7px", borderRadius: 10, background: pc.bg, color: pc.fg, letterSpacing: 0.3 }}>
                          {paymentIcon(exp.payment)} {exp.payment}
                        </span>
                      )}
                      {isIncome && (
                        <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 9, fontWeight: 600, padding: "2px 7px", borderRadius: 10, background: "#81B29A18", color: "#81B29A", letterSpacing: 0.3 }}>
                          Income
                        </span>
                      )}
                    </div>
                  </div>
                  <span style={{ fontFamily: "'Crimson Pro', serif", fontSize: 16, fontWeight: 700, color: isIncome ? "#81B29A" : "#E07A5F", flexShrink: 0 }}>
                    {isIncome ? "+" : "−"}{currency}{exp.amount.toLocaleString()}
                  </span>
                </div>
              );
            })}
          </div>
        ))
      )}
    </div>
  );
}

// ─── Weekly Letter ─────────────────────────────────────────────────────────────

function WeeklyLetter({ currency, expenses, streak, dailyNotes }) {
  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - i);
    return d.toISOString().slice(0, 10);
  });

  const weekExp    = expenses.filter(e => days.includes(e.date) && e.type !== "income");
  const weekInc    = expenses.filter(e => days.includes(e.date) && e.type === "income");
  const totalSpent = weekExp.reduce((s, e) => s + e.amount, 0);
  const totalEarned = weekInc.reduce((s, e) => s + e.amount, 0);

  const catTotals = weekExp.reduce((acc, e) => {
    acc[e.category] = (acc[e.category] || 0) + e.amount;
    return acc;
  }, {});
  const topCat = Object.entries(catTotals).sort((a, b) => b[1] - a[1])[0];

  const lightestDay = days
    .map(d => ({ label: dateLabel(d), spent: weekExp.filter(e => e.date === d).reduce((s, e) => s + e.amount, 0) }))
    .filter(d => d.spent > 0)
    .sort((a, b) => a.spent - b.spent)[0];

  const recentNoteDate = days.find(d => dailyNotes[d]);

  const start = new Date(days[6]).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const end   = new Date(days[0]).toLocaleDateString("en-US", { month: "short", day: "numeric" });

  return (
    <div style={{ margin: "0 16px 16px", background: "linear-gradient(135deg, #3D405B 0%, #2D2A26 100%)", borderRadius: 16, padding: 20, color: "#FAF6F1", boxShadow: "0 4px 20px rgba(45,42,38,0.2)" }}>
      <div style={{ textAlign: "center", marginBottom: 16 }}>
        <p style={{ fontFamily: "'Caveat', cursive", fontSize: 24, margin: "0 0 4px" }}>📬 Your Weekly Letter</p>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#CCC5BB", margin: 0 }}>{start} — {end}</p>
      </div>

      {weekExp.length === 0 ? (
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, color: "#CCC5BB", textAlign: "center", padding: "16px 0" }}>
          No entries this week yet. Start logging to see your story!
        </p>
      ) : (
        <div style={{ background: "rgba(255,255,255,0.08)", borderRadius: 10, padding: 14, fontFamily: "'DM Sans', sans-serif", fontSize: 13, lineHeight: 1.8 }}>
          <p style={{ margin: "0 0 6px" }}>
            This week you logged <strong>{weekExp.length} entries</strong> totalling <strong>{currency}{totalSpent.toLocaleString()}</strong>.
          </p>
          {topCat && (
            <p style={{ margin: "0 0 6px" }}>
              <strong>{topCat[0]}</strong> was your biggest category at <strong>{currency}{topCat[1].toLocaleString()}</strong> ({Math.round((topCat[1] / totalSpent) * 100)}%).
            </p>
          )}
          {lightestDay && (
            <p style={{ margin: "0 0 6px" }}>
              Your lightest day was <strong>{lightestDay.label}</strong> — just {currency}{lightestDay.spent.toLocaleString()}.
            </p>
          )}
          {totalEarned > 0 && (
            <p style={{ margin: "0 0 6px" }}>
              You earned <strong>{currency}{totalEarned.toLocaleString()}</strong> this week. 💚
            </p>
          )}
          {streak?.currentStreak > 0 && (
            <p style={{ margin: 0 }}>
              🔥 Your streak: <strong>{streak.currentStreak} days</strong> and counting!
            </p>
          )}
          {recentNoteDate && (
            <div style={{ marginTop: 12, padding: "8px 12px", background: "rgba(255,255,255,0.07)", borderRadius: 8, borderLeft: "3px solid #F2CC8F" }}>
              <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#F2CC8F", margin: "0 0 4px" }}>Your note this week:</p>
              <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#FAF6F1", margin: 0, fontStyle: "italic" }}>"{dailyNotes[recentNoteDate]}"</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Daily Money Note ─────────────────────────────────────────────────────────

function DailyMoneyNote({ currency, expenses, dailyNotes, onSaveNote }) {
  const today     = todayStr();
  const yesterday = yesterdayStr();
  const [note, setNote] = useState(dailyNotes[today] || "");

  // Update local state when dailyNotes changes externally
  useEffect(() => {
    setNote(dailyNotes[today] || "");
  }, [dailyNotes, today]);

  const todayExp   = expenses.filter(e => e.date === today && e.type !== "income");
  const todayTotal = todayExp.reduce((s, e) => s + e.amount, 0);

  const topCatEntry = Object.entries(
    todayExp.reduce((acc, e) => { acc[e.category] = (acc[e.category] || 0) + e.amount; return acc; }, {})
  ).sort((a, b) => b[1] - a[1])[0];

  const handleSave = () => onSaveNote(today, note);

  return (
    <div style={{ margin: "0 16px 16px", background: "#fff", borderRadius: 16, padding: 16, boxShadow: "0 2px 12px rgba(45,42,38,0.06)", border: "1px solid #EDE8E1" }}>
      <p style={{ fontFamily: "'Caveat', cursive", fontSize: 18, color: "#8B8580", margin: "0 0 10px" }}>📝 Today's Note</p>

      {todayTotal > 0 && (
        <div style={{ background: "#FAF6F1", borderRadius: 8, padding: "8px 12px", marginBottom: 10, fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#5A5550" }}>
          You spent <strong>{currency}{todayTotal.toLocaleString()}</strong> across {todayExp.length} {todayExp.length === 1 ? "entry" : "entries"}.
          {topCatEntry && <span> Top: {topCatEntry[0]} ({currency}{topCatEntry[1].toLocaleString()})</span>}
        </div>
      )}

      <textarea
        value={note}
        onChange={e => setNote(e.target.value)}
        placeholder="How was your spending today? Write a quick reflection..."
        rows={3}
        style={{ width: "100%", border: "1px solid #EDE8E1", background: "#FAF6F1", borderRadius: 8, padding: "10px 12px", fontFamily: "'DM Sans', sans-serif", fontSize: 13, color: "#2D2A26", outline: "none", resize: "none", boxSizing: "border-box", lineHeight: 1.6 }}
      />

      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
        <button
          onClick={handleSave}
          style={{ background: "#3D405B", color: "#FAF6F1", border: "none", borderRadius: 8, padding: "7px 16px", fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
        >
          Save Note 💾
        </button>
      </div>

      {dailyNotes[yesterday] && (
        <div style={{ marginTop: 10, padding: "8px 12px", background: "#FAF6F1", borderRadius: 8, borderLeft: "3px solid #E07A5F" }}>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#8B8580", margin: "0 0 3px" }}>Yesterday:</p>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#5A5550", margin: 0, fontStyle: "italic" }}>"{dailyNotes[yesterday]}"</p>
        </div>
      )}
    </div>
  );
}

// ─── Recurring View ───────────────────────────────────────────────────────────

const FREQ_LABELS = { daily: "Daily", weekly: "Weekly", monthly: "Monthly", yearly: "Yearly" };

function RecurringView({ currency, categories, recurring, onAdd, onToggle, onDelete }) {
  const [showForm,    setShowForm]    = useState(false);
  const [amount,      setAmount]      = useState("");
  const [cat,         setCat]         = useState("");
  const [note,        setNote]        = useState("");
  const [payment,     setPayment]     = useState("UPI");
  const [freq,        setFreq]        = useState("monthly");
  const [dayOfMonth,  setDayOfMonth]  = useState("1");

  const expCats = categories.filter(c => c.type !== "income");

  useEffect(() => {
    if (expCats.length && !cat) setCat(expCats[0].name);
  }, [categories]);

  const handleAdd = () => {
    const num = parseFloat(amount);
    if (!num || num <= 0 || !cat) return;
    const catObj = categories.find(c => c.name === cat);
    onAdd({
      id:        Date.now(),
      amount:    num,
      category:  cat,
      note:      note || cat,
      emoji:     catObj?.emoji || "💸",
      payment,
      type:      "expense",
      frequency: freq,
      dayOfMonth: parseInt(dayOfMonth) || 1,
      lastAdded: null,
      active:    true,
    });
    setAmount(""); setNote(""); setShowForm(false);
  };

  return (
    <div style={{ margin: "0 16px 16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <p style={{ fontFamily: "'Caveat', cursive", fontSize: 22, color: "#2D2A26", margin: 0 }}>🔄 Recurring</p>
        <button
          onClick={() => setShowForm(!showForm)}
          style={{ background: "#3D405B", color: "#FAF6F1", border: "none", borderRadius: 10, padding: "7px 14px", fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
        >
          + Add
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <div style={{ background: "#fff", borderRadius: 16, padding: 16, border: "1px solid #EDE8E1", marginBottom: 16 }}>
          <p style={{ fontFamily: "'Caveat', cursive", fontSize: 16, color: "#8B8580", margin: "0 0 12px" }}>New Recurring Expense</p>

          <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
            <div style={{ flex: 1, display: "flex", alignItems: "center", background: "#FAF6F1", borderRadius: 10, padding: "8px 12px", border: "1px solid #EDE8E1" }}>
              <span style={{ fontSize: 16, marginRight: 6, color: "#8B8580" }}>{currency}</span>
              <input
                type="number" value={amount} onChange={e => setAmount(e.target.value)} placeholder="0"
                style={{ border: "none", background: "transparent", fontSize: 18, fontFamily: "'Crimson Pro', serif", fontWeight: 600, color: "#2D2A26", width: "100%", outline: "none" }}
              />
            </div>
            <select
              value={cat} onChange={e => setCat(e.target.value)}
              style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, background: "#FAF6F1", border: "1px solid #EDE8E1", borderRadius: 10, padding: "8px 10px", color: "#2D2A26", outline: "none" }}
            >
              {expCats.map(c => <option key={c.name} value={c.name}>{c.emoji} {c.name}</option>)}
            </select>
          </div>

          <input
            value={note} onChange={e => setNote(e.target.value)} placeholder="Description (e.g. Rent, Netflix, Gym)"
            style={{ width: "100%", border: "1px solid #EDE8E1", background: "#FAF6F1", borderRadius: 8, padding: "8px 12px", fontFamily: "'DM Sans', sans-serif", fontSize: 13, color: "#2D2A26", outline: "none", boxSizing: "border-box", marginBottom: 8 }}
          />

          <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
            <select
              value={freq} onChange={e => setFreq(e.target.value)}
              style={{ flex: 1, fontFamily: "'DM Sans', sans-serif", fontSize: 12, background: "#FAF6F1", border: "1px solid #EDE8E1", borderRadius: 8, padding: "8px", color: "#2D2A26", outline: "none" }}
            >
              {Object.entries(FREQ_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            {freq === "monthly" && (
              <div style={{ display: "flex", alignItems: "center", gap: 4, background: "#FAF6F1", border: "1px solid #EDE8E1", borderRadius: 8, padding: "8px 12px" }}>
                <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#8B8580" }}>Day:</span>
                <input
                  type="number" value={dayOfMonth} onChange={e => setDayOfMonth(e.target.value)} min="1" max="31"
                  style={{ width: 36, border: "none", background: "transparent", fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#2D2A26", outline: "none" }}
                />
              </div>
            )}
          </div>

          <div style={{ display: "flex", gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
            {PAYMENT_TYPES.map(pt => (
              <button key={pt.label} onClick={() => setPayment(pt.label)}
                style={{ padding: "4px 10px", borderRadius: 16, border: payment === pt.label ? `2px solid ${pt.color}` : "1px solid #EDE8E1", background: payment === pt.label ? `${pt.color}14` : "#FAF6F1", fontFamily: "'DM Sans', sans-serif", fontSize: 11, fontWeight: payment === pt.label ? 600 : 400, color: payment === pt.label ? pt.color : "#8B8580", cursor: "pointer" }}>
                {pt.icon} {pt.label}
              </button>
            ))}
          </div>

          <button onClick={handleAdd}
            style={{ width: "100%", background: "#3D405B", color: "#FAF6F1", border: "none", borderRadius: 10, padding: "10px", fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
            Save Recurring Entry
          </button>
        </div>
      )}

      {/* Recurring list */}
      {recurring.length === 0 ? (
        <div style={{ textAlign: "center", padding: 32, color: "#8B8580", fontFamily: "'DM Sans', sans-serif", fontSize: 14, background: "#fff", borderRadius: 16, border: "1px solid #EDE8E1" }}>
          No recurring entries yet.<br />Set up rent, EMIs, subscriptions and more!
        </div>
      ) : (
        recurring.map(r => (
          <div key={r.id} style={{ background: "#fff", borderRadius: 12, padding: "14px 16px", marginBottom: 8, border: "1px solid #EDE8E1", display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 38, height: 38, borderRadius: 10, background: "#FAF6F1", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, flexShrink: 0 }}>
              {r.emoji}
            </div>
            <div style={{ flex: 1 }}>
              <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, color: "#2D2A26", margin: 0 }}>{r.note}</p>
              <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#8B8580", margin: "2px 0 0" }}>
                {currency}{r.amount.toLocaleString()} · {FREQ_LABELS[r.frequency]}{r.frequency === "monthly" ? ` (day ${r.dayOfMonth})` : ""}
              </p>
            </div>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <button
                onClick={() => onToggle(r.id)}
                style={{ padding: "4px 10px", borderRadius: 16, border: "none", background: r.active ? "#81B29A18" : "#EDE8E1", fontFamily: "'DM Sans', sans-serif", fontSize: 11, fontWeight: 600, color: r.active ? "#81B29A" : "#8B8580", cursor: "pointer" }}
              >
                {r.active ? "Active" : "Paused"}
              </button>
              <button onClick={() => onDelete(r.id)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 14, color: "#CCC5BB" }}>✕</button>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

// ─── Settings View ────────────────────────────────────────────────────────────

function SettingsView({ currency, setCurrency, totalBudget, setTotalBudget, expenses, categories, onAddCategory, onClearAll }) {
  const [budgetInput, setBudgetInput] = useState(totalBudget);

  const handleExport = () => {
    const data = { expenses, categories, currency, budget: totalBudget, exportedAt: new Date().toISOString() };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = `expense-journal-${todayStr()}.json`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ margin: "0 16px 16px" }}>
      <p style={{ fontFamily: "'Caveat', cursive", fontSize: 22, color: "#2D2A26", margin: "0 0 16px" }}>⚙️ Settings</p>

      {/* Currency */}
      <div style={{ background: "#fff", borderRadius: 16, padding: 16, border: "1px solid #EDE8E1", marginBottom: 12 }}>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, color: "#5A5550", margin: "0 0 8px" }}>Currency</p>
        <select value={currency} onChange={e => setCurrency(e.target.value)} style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 14, background: "#FAF6F1", border: "1px solid #EDE8E1", borderRadius: 10, padding: "8px 12px", color: "#2D2A26", outline: "none", width: "100%" }}>
          {Object.entries(CURRENCIES).map(([sym, code]) => (
            <option key={sym} value={sym}>{sym} {code}</option>
          ))}
        </select>
      </div>

      {/* Budget */}
      <div style={{ background: "#fff", borderRadius: 16, padding: 16, border: "1px solid #EDE8E1", marginBottom: 12 }}>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, color: "#5A5550", margin: "0 0 8px" }}>Monthly Budget</p>
        <div style={{ display: "flex", gap: 8 }}>
          <input type="number" value={budgetInput} onChange={e => setBudgetInput(e.target.value)} style={{ flex: 1, padding: "8px 12px", borderRadius: 10, border: "1px solid #EDE8E1", fontFamily: "'DM Sans', sans-serif", fontSize: 14, outline: "none", background: "#FAF6F1" }} />
          <button onClick={() => setTotalBudget(parseFloat(budgetInput) || DEFAULT_BUDGET)} style={{ background: "#3D405B", color: "#FAF6F1", border: "none", borderRadius: 10, padding: "8px 16px", fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>Save</button>
        </div>
      </div>

      {/* Categories */}
      <CategoryBreakdown currency={currency} categories={categories} expenses={expenses} onAddCategory={onAddCategory} />

      {/* Data */}
      <div style={{ background: "#fff", borderRadius: 16, padding: 16, border: "1px solid #EDE8E1", marginBottom: 12 }}>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, color: "#5A5550", margin: "0 0 10px" }}>Data</p>
        <button onClick={handleExport} style={{ width: "100%", padding: "10px", background: "#3D405B18", border: "1px solid #3D405B44", borderRadius: 10, fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, color: "#3D405B", cursor: "pointer", marginBottom: 8 }}>
          📤 Export Data (JSON)
        </button>
        <button onClick={onClearAll} style={{ width: "100%", padding: "10px", background: "#E07A5F18", border: "1px solid #E07A5F44", borderRadius: 10, fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, color: "#E07A5F", cursor: "pointer" }}>
          🗑️ Clear All Expenses
        </button>
      </div>

      <div style={{ background: "#fff", borderRadius: 16, padding: 16, border: "1px solid #EDE8E1" }}>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#81B29A", margin: 0 }}>✅ All data saved locally. No account needed. No internet required.</p>
      </div>
    </div>
  );
}

// ─── Bottom Nav ───────────────────────────────────────────────────────────────

function BottomNav({ selectedView, setSelectedView }) {
  const items = [
    { icon: "🏠", label: "Home",      key: "home"      },
    { icon: "📊", label: "Stats",     key: "stats"     },
    { icon: "🔄", label: "Recurring", key: "recurring" },
    { icon: "⚙️", label: "Settings",  key: "settings"  },
  ];
  return (
    <div style={{ position: "fixed", bottom: 0, left: "50%", transform: "translateX(-50%)", width: "100%", maxWidth: 480, background: "rgba(255,255,255,0.97)", backdropFilter: "blur(12px)", borderTop: "1px solid #EDE8E1", display: "flex", justifyContent: "space-around", padding: "8px 0 12px", zIndex: 100 }}>
      {items.map(item => {
        const active = selectedView === item.key;
        return (
          <button key={item.key} onClick={() => setSelectedView(item.key)} style={{ background: "none", border: "none", cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
            <span style={{ fontSize: 22, opacity: active ? 1 : 0.45 }}>{item.icon}</span>
            <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 10, color: active ? "#3D405B" : "#8B8580", fontWeight: active ? 700 : 400 }}>
              {item.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}

// ─── Root ─────────────────────────────────────────────────────────────────────

export default function App() {
  const [currency,     setCurrency]     = useLocalStorage("et_currency",    "₹");
  const [totalBudget,  setTotalBudget]  = useLocalStorage("et_budget",      DEFAULT_BUDGET);
  const [expenses,     setExpenses]     = useLocalStorage("et_expenses",    []);
  const [categories,   setCategories]   = useLocalStorage("et_categories",  DEFAULT_CATEGORIES);
  const [recurring,    setRecurring]    = useLocalStorage("et_recurring",   []);
  const [dailyNotes,   setDailyNotes]   = useLocalStorage("et_daily_notes", {});
  const [streak,       setStreak]       = useLocalStorage("et_streak",      { currentStreak: 0, longestStreak: 0, lastLogDate: null });
  const [selectedView, setSelectedView] = useState("home");
  const [editingExp,   setEditingExp]   = useState(null);

  // ── On mount: check streak integrity + auto-add recurring ──────────────────
  useEffect(() => {
    // Break streak if user missed yesterday
    setStreak(prev => {
      if (prev.lastLogDate && prev.lastLogDate < yesterdayStr()) {
        return { ...prev, currentStreak: 0 };
      }
      return prev;
    });

    // Auto-add active recurring entries that are due today
    const today = todayStr();
    const toAdd = [];
    const updatedIds = [];

    recurring.forEach(r => {
      if (!r.active || r.lastAdded === today) return;
      const due = () => {
        if (r.frequency === "daily") return true;
        if (r.frequency === "weekly")  return new Date().getDay() === 1;  // Monday
        if (r.frequency === "monthly") return new Date().getDate() === r.dayOfMonth;
        if (r.frequency === "yearly")  return new Date().getMonth() === 0 && new Date().getDate() === 1;
        return false;
      };
      if (due()) {
        toAdd.push({ id: Date.now() + Math.random(), amount: r.amount, category: r.category, note: r.note, date: today, emoji: r.emoji, payment: r.payment, type: "expense" });
        updatedIds.push(r.id);
      }
    });

    if (toAdd.length > 0) {
      setExpenses(prev => [...toAdd, ...prev]);
      setRecurring(prev => prev.map(r => updatedIds.includes(r.id) ? { ...r, lastAdded: today } : r));
    }
  }, []);

  // ── Streak update on expense add ───────────────────────────────────────────
  const updateStreak = () => {
    const today = todayStr();
    setStreak(prev => {
      if (prev.lastLogDate === today) return prev;
      const cont = prev.lastLogDate === yesterdayStr();
      const newStreak = cont ? prev.currentStreak + 1 : 1;
      return { currentStreak: newStreak, longestStreak: Math.max(newStreak, prev.longestStreak), lastLogDate: today };
    });
  };

  // ── CRUD helpers ───────────────────────────────────────────────────────────
  const addExpense  = (exp) => { setExpenses(prev => [exp, ...prev]); updateStreak(); };
  const delExpense  = (id)  => setExpenses(prev => prev.filter(e => e.id !== id));
  const editExpense = (exp) => setExpenses(prev => prev.map(e => e.id === exp.id ? exp : e));
  const addCategory = (cat) => setCategories(prev => [...prev, cat]);
  const saveNote    = (date, note) => setDailyNotes(prev => ({ ...prev, [date]: note }));

  const addRecurring    = (r)  => setRecurring(prev => [...prev, r]);
  const toggleRecurring = (id) => setRecurring(prev => prev.map(r => r.id === id ? { ...r, active: !r.active } : r));
  const deleteRecurring = (id) => setRecurring(prev => prev.filter(r => r.id !== id));

  const clearAll = () => {
    if (window.confirm("Clear all expenses? This cannot be undone.")) setExpenses([]);
  };

  return (
    <div style={{ minHeight: "100vh", background: "linear-gradient(180deg, #FAF6F1 0%, #F3EDE4 100%)", fontFamily: "'Crimson Pro', 'Georgia', serif", maxWidth: 480, margin: "0 auto", position: "relative", paddingBottom: 80 }}>
      <link href="https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@300;400;500;600;700&family=DM+Sans:wght@400;500;600&family=Caveat:wght@500;600&display=swap" rel="stylesheet" />

      <Header currency={currency} setCurrency={setCurrency} streak={streak} />

      {/* ── Home ── */}
      {selectedView === "home" && (
        <>
          <QuickAdd  currency={currency} categories={categories} onAdd={addExpense} />
          <BudgetCard currency={currency} expenses={expenses} totalBudget={totalBudget} categories={categories} />
          <ExpenseList currency={currency} expenses={expenses} categories={categories} onDelete={delExpense} onEdit={setEditingExp} />
          <DailyMoneyNote currency={currency} expenses={expenses} dailyNotes={dailyNotes} onSaveNote={saveNote} />
        </>
      )}

      {/* ── Stats ── */}
      {selectedView === "stats" && (
        <>
          <WeeklyLetter currency={currency} expenses={expenses} streak={streak} dailyNotes={dailyNotes} />
          <WeeklyTrend  currency={currency} expenses={expenses} />
          <CategoryBreakdown currency={currency} categories={categories} expenses={expenses} onAddCategory={addCategory} />
        </>
      )}

      {/* ── Recurring ── */}
      {selectedView === "recurring" && (
        <RecurringView
          currency={currency} categories={categories} recurring={recurring}
          onAdd={addRecurring} onToggle={toggleRecurring} onDelete={deleteRecurring}
        />
      )}

      {/* ── Settings ── */}
      {selectedView === "settings" && (
        <SettingsView
          currency={currency}      setCurrency={setCurrency}
          totalBudget={totalBudget} setTotalBudget={setTotalBudget}
          expenses={expenses}      categories={categories} onAddCategory={addCategory}
          onClearAll={clearAll}
        />
      )}

      <BottomNav selectedView={selectedView} setSelectedView={setSelectedView} />

      {/* ── Edit modal (global overlay) ── */}
      {editingExp && (
        <EditModal
          expense={editingExp}
          categories={categories}
          currency={currency}
          onSave={editExpense}
          onDelete={delExpense}
          onClose={() => setEditingExp(null)}
        />
      )}
    </div>
  );
}
