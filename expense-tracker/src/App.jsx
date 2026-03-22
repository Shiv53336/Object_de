import { useState, useEffect } from "react";
import {
  PieChart, Pie, Cell,
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer
} from "recharts";

// ─── Constants ────────────────────────────────────────────────────────────────

const CURRENCIES = { "₹": "INR", "$": "USD", "€": "EUR", "£": "GBP" };

const DEFAULT_CATEGORIES = [
  { name: "Food & Dining",     emoji: "🍜", color: "#E07A5F", budget: 8000 },
  { name: "Transport",         emoji: "🛺", color: "#3D405B", budget: 3000 },
  { name: "Shopping",          emoji: "🛍️", color: "#81B29A", budget: 5000 },
  { name: "Bills & Utilities", emoji: "💡", color: "#F2CC8F", budget: 6000 },
  { name: "Entertainment",     emoji: "🎮", color: "#7B68EE", budget: 2000 },
  { name: "Health",            emoji: "💊", color: "#E88D97", budget: 2000 },
];

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

const DEFAULT_MEMBERS = ["Dad", "Mom", "Kid"];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function exportCSV(expenses, currency) {
  const header = ["Date", "Category", "Note", "Amount", "Payment", "Member"];
  const rows = expenses
    .slice()
    .sort((a, b) => b.date.localeCompare(a.date))
    .map(e => [
      e.date,
      e.category,
      `"${(e.note || "").replace(/"/g, '""')}"`,
      e.amount,
      e.payment || "",
      e.member  || "",
    ]);
  const csv = [header, ...rows].map(r => r.join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = `expenses-${new Date().toISOString().slice(0, 7)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

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

function dateLabel(dateStr) {
  const today     = todayStr();
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
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

function Header({ currency, setCurrency }) {
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
        <select
          value={currency}
          onChange={e => setCurrency(e.target.value)}
          style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 14, background: "#fff", border: "1px solid #E0D8CF", borderRadius: 10, padding: "6px 10px", color: "#2D2A26", cursor: "pointer", outline: "none" }}
        >
          {Object.entries(CURRENCIES).map(([sym, code]) => (
            <option key={sym} value={sym}>{sym} {code}</option>
          ))}
        </select>
        <div style={{ width: 36, height: 36, borderRadius: "50%", background: "#3D405B", display: "flex", alignItems: "center", justifyContent: "center", color: "#FAF6F1", fontFamily: "'DM Sans', sans-serif", fontSize: 14, fontWeight: 600 }}>
          H
        </div>
      </div>
    </div>
  );
}

// ─── Quick Add ────────────────────────────────────────────────────────────────

function QuickAdd({ currency, categories, members, onAdd, onAddRecurring }) {
  const [amount,      setAmount]      = useState("");
  const [cat,         setCat]         = useState(categories[0]?.name || "");
  const [note,        setNote]        = useState("");
  const [payment,     setPayment]     = useState("UPI");
  const [customPay,   setCustomPay]   = useState("");
  const [isRecurring, setIsRecurring] = useState(false);
  const [member,      setMember]      = useState("");

  useEffect(() => {
    if (categories.length && !categories.find(c => c.name === cat)) {
      setCat(categories[0].name);
    }
  }, [categories]);

  const handleAdd = () => {
    const num = parseFloat(amount);
    if (!num || num <= 0) return;
    const catObj = categories.find(c => c.name === cat) || categories[0];
    const payFinal = payment === "Other" ? (customPay || "Other") : payment;
    onAdd({
      id:        Date.now(),
      amount:    num,
      category:  cat,
      note:      note || cat,
      date:      todayStr(),
      emoji:     catObj?.emoji || "💸",
      payment:   payFinal,
      recurring: isRecurring,
      member:    member,
    });
    if (isRecurring) {
      onAddRecurring({
        id:        Date.now() + 1,
        amount:    num,
        category:  cat,
        note:      note || cat,
        emoji:     catObj?.emoji || "💸",
        payment:   payFinal,
        lastLogged: new Date().toISOString().slice(0, 7),
      });
      setIsRecurring(false);
    }
    setAmount("");
    setNote("");
  };

  return (
    <div style={{ margin: "0 16px 16px", background: "#fff", borderRadius: 16, padding: 16, boxShadow: "0 2px 12px rgba(45,42,38,0.06)", border: "1px solid #EDE8E1" }}>
      <p style={{ fontFamily: "'Caveat', cursive", fontSize: 18, color: "#8B8580", margin: "0 0 12px" }}>✏️ Quick Entry</p>

      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <div style={{ flex: 1, display: "flex", alignItems: "center", background: "#FAF6F1", borderRadius: 10, padding: "10px 12px", border: "1px solid #EDE8E1" }}>
          <span style={{ fontSize: 18, marginRight: 6, color: "#8B8580" }}>{currency}</span>
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
          {categories.map(c => (
            <option key={c.name} value={c.name}>{c.emoji} {c.name.split(" ")[0]}</option>
          ))}
        </select>
        <button
          onClick={handleAdd}
          style={{ background: "#3D405B", color: "#FAF6F1", border: "none", borderRadius: 10, padding: "10px 16px", fontFamily: "'DM Sans', sans-serif", fontSize: 14, fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap" }}
        >
          Add
        </button>
      </div>

      <input
        value={note}
        onChange={e => setNote(e.target.value)}
        onKeyDown={e => e.key === "Enter" && handleAdd()}
        placeholder="Add a note..."
        style={{ marginTop: 8, width: "100%", border: "1px solid #EDE8E1", background: "#FAF6F1", borderRadius: 8, padding: "8px 12px", fontFamily: "'DM Sans', sans-serif", fontSize: 13, color: "#2D2A26", outline: "none", boxSizing: "border-box" }}
      />

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

      {members.length > 0 && (
        <div style={{ marginTop: 8, display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#8B8580", marginRight: 2 }}>For:</span>
          <button
            onClick={() => setMember("")}
            style={{ padding: "5px 12px", borderRadius: 20, border: member === "" ? "2px solid #3D405B" : "1px solid #EDE8E1", background: member === "" ? "#3D405B14" : "#FAF6F1", fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: member === "" ? 600 : 400, color: member === "" ? "#3D405B" : "#8B8580", cursor: "pointer" }}
          >
            👨‍👩‍👧 All
          </button>
          {members.map(m => (
            <button
              key={m}
              onClick={() => setMember(m)}
              style={{ padding: "5px 12px", borderRadius: 20, border: member === m ? "2px solid #6C63FF" : "1px solid #EDE8E1", background: member === m ? "#6C63FF14" : "#FAF6F1", fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: member === m ? 600 : 400, color: member === m ? "#6C63FF" : "#8B8580", cursor: "pointer" }}
            >
              {m}
            </button>
          ))}
        </div>
      )}

      <button
        onClick={() => setIsRecurring(r => !r)}
        style={{ marginTop: 8, padding: "6px 14px", borderRadius: 20, border: isRecurring ? "2px solid #2A9D8F" : "1px solid #EDE8E1", background: isRecurring ? "#2A9D8F14" : "#FAF6F1", fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: isRecurring ? 600 : 400, color: isRecurring ? "#2A9D8F" : "#8B8580", cursor: "pointer" }}
      >
        🔄 {isRecurring ? "Will auto-repeat monthly" : "Set as recurring"}
      </button>
    </div>
  );
}

// ─── Budget Card ──────────────────────────────────────────────────────────────

function BudgetCard({ currency, totalSpent, totalBudget }) {
  const remaining = totalBudget - totalSpent;
  const pct       = Math.min(100, Math.round((totalSpent / totalBudget) * 100));
  const color     = getBudgetColor(pct);
  const now       = new Date();
  const daysLeft  = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate() - now.getDate();

  return (
    <div style={{ margin: "0 16px 16px", background: "#fff", borderRadius: 16, padding: 16, boxShadow: "0 2px 12px rgba(45,42,38,0.06)", border: "1px solid #EDE8E1" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
        <p style={{ fontFamily: "'Caveat', cursive", fontSize: 18, color: "#8B8580", margin: 0 }}>📊 Monthly Budget</p>
        <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color, fontWeight: 600, background: `${color}18`, padding: "3px 8px", borderRadius: 6 }}>
          {pct}% used
        </span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ fontFamily: "'Crimson Pro', serif", fontSize: 26, fontWeight: 700, color: "#2D2A26" }}>
          {currency}{totalSpent.toLocaleString()}
        </span>
        <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, color: "#8B8580", alignSelf: "flex-end" }}>
          of {currency}{totalBudget.toLocaleString()}
        </span>
      </div>
      <div style={{ height: 10, background: "#EDE8E1", borderRadius: 10, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: `linear-gradient(90deg, ${color}, ${color}cc)`, borderRadius: 10, transition: "width 0.8s ease" }} />
      </div>
      <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: remaining >= 0 ? "#81B29A" : "#E07A5F", margin: "8px 0 0", fontWeight: 500 }}>
        {remaining >= 0
          ? `💰 ${currency}${remaining.toLocaleString()} remaining`
          : `⚠️ Over budget by ${currency}${Math.abs(remaining).toLocaleString()}`}
        {" "}• {daysLeft} days left
      </p>
    </div>
  );
}

// ─── Category Breakdown ───────────────────────────────────────────────────────

function CategoryBreakdown({ currency, categories, expenses, onAddCategory, onUpdateCategory }) {
  const [chartType,   setChartType]   = useState("donut");
  const [showAddCat,  setShowAddCat]  = useState(false);
  const [newEmoji,    setNewEmoji]    = useState("");
  const [newName,     setNewName]     = useState("");
  const [newBudget,   setNewBudget]   = useState("");
  const [editingBudget, setEditingBudget] = useState(null); // category name being edited
  const [editBudgetVal, setEditBudgetVal] = useState("");

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
        <ResponsiveContainer width="100%" height={140}>
          <PieChart>
            <Pie data={pieData.length ? pieData : [{ name: "empty", value: 1, color: "#EDE8E1" }]} cx="50%" cy="50%" innerRadius={40} outerRadius={65} dataKey="value" stroke="none">
              {(pieData.length ? pieData : [{ color: "#EDE8E1" }]).map((entry, i) => <Cell key={i} fill={entry.color} />)}
            </Pie>
            <Tooltip formatter={v => [`${currency}${v.toLocaleString()}`, "Spent"]} contentStyle={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, borderRadius: 8, border: "1px solid #EDE8E1" }} />
          </PieChart>
        </ResponsiveContainer>
      ) : (
        <ResponsiveContainer width="100%" height={140}>
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

      {/* Per-category budget rows */}
      <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
        {catSpend.map(c => {
          const budget = c.budget || 0;
          const pct    = budget > 0 ? Math.min(100, Math.round((c.spent / budget) * 100)) : 0;
          const color  = getBudgetColor(pct);
          const over   = c.spent > budget && budget > 0;
          const isEditing = editingBudget === c.name;
          return (
            <div key={c.name}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#2D2A26", fontWeight: 500 }}>
                  {c.emoji} {c.name}
                </span>
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ fontFamily: "'Crimson Pro', serif", fontSize: 13, color: "#5A5550" }}>
                    {currency}{c.spent.toLocaleString()}
                  </span>
                  <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#8B8580" }}>/</span>
                  {isEditing ? (
                    <input
                      type="number"
                      autoFocus
                      value={editBudgetVal}
                      onChange={e => setEditBudgetVal(e.target.value)}
                      onBlur={() => {
                        const val = parseFloat(editBudgetVal);
                        if (val > 0) onUpdateCategory(c.name, { budget: val });
                        setEditingBudget(null);
                      }}
                      onKeyDown={e => {
                        if (e.key === "Enter") {
                          const val = parseFloat(editBudgetVal);
                          if (val > 0) onUpdateCategory(c.name, { budget: val });
                          setEditingBudget(null);
                        }
                        if (e.key === "Escape") setEditingBudget(null);
                      }}
                      style={{ width: 64, padding: "2px 6px", borderRadius: 6, border: `1px solid ${color}`, fontFamily: "'DM Sans', sans-serif", fontSize: 12, outline: "none", background: "#fff", color: "#2D2A26" }}
                    />
                  ) : (
                    <button
                      title="Click to edit budget"
                      onClick={() => { setEditingBudget(c.name); setEditBudgetVal(String(budget)); }}
                      style={{ background: "none", border: "none", cursor: "pointer", fontFamily: "'Crimson Pro', serif", fontSize: 13, color: "#8B8580", padding: 0, textDecoration: "underline dotted", textUnderlineOffset: 2 }}
                    >
                      {currency}{(budget || 0).toLocaleString()}
                    </button>
                  )}
                </div>
              </div>
              <div style={{ height: 7, background: "#EDE8E1", borderRadius: 6, overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${pct}%`, background: `linear-gradient(90deg, ${color}, ${color}cc)`, borderRadius: 6, transition: "width 0.5s ease" }} />
              </div>
              {over && (
                <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#E07A5F", margin: "3px 0 0", fontWeight: 500 }}>
                  ⚠️ Over by {currency}{(c.spent - budget).toLocaleString()}
                </p>
              )}
              {!over && pct >= 85 && (
                <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#F2CC8F", margin: "3px 0 0", fontWeight: 500 }}>
                  Almost at limit ({pct}%)
                </p>
              )}
            </div>
          );
        })}
      </div>

      <button onClick={() => setShowAddCat(!showAddCat)} style={{ marginTop: 12, width: "100%", padding: "8px", background: "transparent", border: "1px dashed #CCC5BB", borderRadius: 8, fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#8B8580", cursor: "pointer" }}>
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

// ─── Spending Alerts ──────────────────────────────────────────────────────────

function SpendingAlerts({ currency, categories, expenses }) {
  const [dismissed, setDismissed] = useState(new Set());

  const alerts = categories
    .map(c => {
      const budget = c.budget || 0;
      if (budget <= 0) return null;
      const spent = expenses.filter(e => e.category === c.name).reduce((s, e) => s + e.amount, 0);
      const pct   = Math.round((spent / budget) * 100);
      if (pct < 80) return null;
      return { name: c.name, emoji: c.emoji, pct, spent, budget, over: spent > budget };
    })
    .filter(Boolean)
    .filter(a => !dismissed.has(a.name));

  if (!alerts.length) return null;

  return (
    <div style={{ margin: "0 16px 12px", display: "flex", flexDirection: "column", gap: 8 }}>
      {alerts.map(a => (
        <div
          key={a.name}
          style={{
            display: "flex", alignItems: "center", gap: 10,
            padding: "10px 14px", borderRadius: 12,
            background: a.over ? "#E07A5F12" : "#F2CC8F14",
            border:     `1px solid ${a.over ? "#E07A5F55" : "#F2CC8F88"}`,
          }}
        >
          <span style={{ fontSize: 20 }}>{a.emoji}</span>
          <div style={{ flex: 1 }}>
            <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: 600, color: a.over ? "#E07A5F" : "#B8860B", margin: 0 }}>
              {a.over ? "🚨 Over budget!" : `⚠️ ${a.pct}% used`} — {a.name}
            </p>
            <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#8B8580", margin: "2px 0 0" }}>
              {currency}{a.spent.toLocaleString()} of {currency}{a.budget.toLocaleString()}
              {a.over && ` · over by ${currency}${(a.spent - a.budget).toLocaleString()}`}
            </p>
          </div>
          <button
            onClick={() => setDismissed(d => new Set([...d, a.name]))}
            style={{ background: "none", border: "none", cursor: "pointer", fontSize: 14, color: "#CCC5BB", padding: 0, flexShrink: 0 }}
          >
            ✕
          </button>
        </div>
      ))}
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

function ExpenseList({ currency, expenses, categories, members, onDelete }) {
  const [search,     setSearch]     = useState("");
  const [filterCat,  setFilterCat]  = useState("");
  const [filterMember, setFilterMember] = useState("");

  const filtered = expenses
    .slice()
    .sort((a, b) => b.date.localeCompare(a.date) || b.id - a.id)
    .filter(e => {
      const q = search.toLowerCase();
      if (q && !e.note.toLowerCase().includes(q) && !e.category.toLowerCase().includes(q)) return false;
      if (filterCat && e.category !== filterCat) return false;
      if (filterMember && e.member !== filterMember) return false;
      return true;
    });

  const grouped = filtered.reduce((acc, exp) => {
    const label = dateLabel(exp.date);
    if (!acc[label]) acc[label] = [];
    acc[label].push(exp);
    return acc;
  }, {});

  const hasFilters = search || filterCat || filterMember;

  if (expenses.length === 0) {
    return (
      <div style={{ margin: "0 16px 16px", textAlign: "center", padding: 32, color: "#8B8580", fontFamily: "'DM Sans', sans-serif", fontSize: 14 }}>
        No expenses yet. Add your first one above! 👆
      </div>
    );
  }

  return (
    <div style={{ margin: "0 16px 16px" }}>
      <p style={{ fontFamily: "'Caveat', cursive", fontSize: 18, color: "#8B8580", margin: "0 0 10px" }}>📝 Recent Entries</p>

      {/* Search bar */}
      <div style={{ position: "relative", marginBottom: 8 }}>
        <span style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", fontSize: 14, color: "#8B8580" }}>🔍</span>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search notes or category..."
          style={{ width: "100%", padding: "8px 12px 8px 32px", borderRadius: 10, border: "1px solid #EDE8E1", fontFamily: "'DM Sans', sans-serif", fontSize: 13, color: "#2D2A26", outline: "none", background: "#FAF6F1", boxSizing: "border-box" }}
        />
      </div>

      {/* Filter pills row */}
      <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap" }}>
        <select
          value={filterCat}
          onChange={e => setFilterCat(e.target.value)}
          style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, background: filterCat ? "#3D405B" : "#FAF6F1", color: filterCat ? "#FAF6F1" : "#8B8580", border: "1px solid #EDE8E1", borderRadius: 20, padding: "4px 10px", outline: "none", cursor: "pointer" }}
        >
          <option value="">All categories</option>
          {categories.map(c => <option key={c.name} value={c.name}>{c.emoji} {c.name}</option>)}
        </select>

        {members.length > 0 && (
          <select
            value={filterMember}
            onChange={e => setFilterMember(e.target.value)}
            style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, background: filterMember ? "#6C63FF" : "#FAF6F1", color: filterMember ? "#FAF6F1" : "#8B8580", border: "1px solid #EDE8E1", borderRadius: 20, padding: "4px 10px", outline: "none", cursor: "pointer" }}
          >
            <option value="">All members</option>
            {members.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        )}

        {hasFilters && (
          <button
            onClick={() => { setSearch(""); setFilterCat(""); setFilterMember(""); }}
            style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, padding: "4px 10px", borderRadius: 20, border: "1px solid #E07A5F44", background: "#E07A5F12", color: "#E07A5F", cursor: "pointer" }}
          >
            ✕ Clear
          </button>
        )}
      </div>

      {filtered.length === 0 && (
        <div style={{ textAlign: "center", padding: "24px 0", color: "#8B8580", fontFamily: "'DM Sans', sans-serif", fontSize: 13 }}>
          No results found.
        </div>
      )}

      {Object.entries(grouped).map(([date, exps]) => (
        <div key={date} style={{ marginBottom: 12 }}>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: 600, color: "#8B8580", margin: "0 0 6px", textTransform: "uppercase", letterSpacing: 0.5 }}>
            {date}
          </p>
          {exps.map(exp => {
            const pc = paymentColor(exp.payment);
            return (
              <div key={exp.id} style={{ background: "#fff", borderRadius: 12, padding: "12px 14px", marginBottom: 6, display: "flex", alignItems: "center", gap: 12, boxShadow: "0 1px 4px rgba(45,42,38,0.04)", border: "1px solid #EDE8E1" }}>
                <div style={{ width: 38, height: 38, borderRadius: 10, background: "#FAF6F1", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, flexShrink: 0 }}>
                  {exp.emoji}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 500, color: "#2D2A26", margin: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {exp.note}
                  </p>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3 }}>
                    <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#8B8580" }}>{exp.category}</span>
                    <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 9, fontWeight: 600, padding: "2px 7px", borderRadius: 10, background: pc.bg, color: pc.fg, letterSpacing: 0.3 }}>
                      {paymentIcon(exp.payment)} {exp.payment}
                    </span>
                    {exp.recurring && (
                      <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 9, fontWeight: 600, padding: "2px 7px", borderRadius: 10, background: "#2A9D8F14", color: "#2A9D8F", letterSpacing: 0.3 }}>
                        🔄 Recurring
                      </span>
                    )}
                    {exp.member && (
                      <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 9, fontWeight: 600, padding: "2px 7px", borderRadius: 10, background: "#6C63FF14", color: "#6C63FF", letterSpacing: 0.3 }}>
                        👤 {exp.member}
                      </span>
                    )}
                  </div>
                </div>
                <span style={{ fontFamily: "'Crimson Pro', serif", fontSize: 16, fontWeight: 700, color: "#E07A5F", flexShrink: 0 }}>
                  −{currency}{exp.amount.toLocaleString()}
                </span>
                <button onClick={() => onDelete(exp.id)} title="Delete" style={{ background: "none", border: "none", cursor: "pointer", fontSize: 14, color: "#CCC5BB", padding: "0 0 0 4px", flexShrink: 0 }}>
                  ✕
                </button>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

// ─── Settings View ────────────────────────────────────────────────────────────

function SettingsView({ currency, setCurrency, totalBudget, setTotalBudget, onClearAll, recurring, onDeleteRecurring, members, onAddMember, onDeleteMember, expenses }) {
  const [budgetInput, setBudgetInput] = useState(totalBudget);
  const [newMember,   setNewMember]   = useState("");

  return (
    <div style={{ margin: "0 16px 16px" }}>
      <p style={{ fontFamily: "'Caveat', cursive", fontSize: 22, color: "#2D2A26", margin: "0 0 16px" }}>⚙️ Settings</p>

      <div style={{ background: "#fff", borderRadius: 16, padding: 16, border: "1px solid #EDE8E1", marginBottom: 12 }}>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, color: "#5A5550", margin: "0 0 8px" }}>Currency</p>
        <select value={currency} onChange={e => setCurrency(e.target.value)} style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 14, background: "#FAF6F1", border: "1px solid #EDE8E1", borderRadius: 10, padding: "8px 12px", color: "#2D2A26", outline: "none", width: "100%" }}>
          {Object.entries(CURRENCIES).map(([sym, code]) => (
            <option key={sym} value={sym}>{sym} {code}</option>
          ))}
        </select>
      </div>

      <div style={{ background: "#fff", borderRadius: 16, padding: 16, border: "1px solid #EDE8E1", marginBottom: 12 }}>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, color: "#5A5550", margin: "0 0 8px" }}>Monthly Budget</p>
        <div style={{ display: "flex", gap: 8 }}>
          <input type="number" value={budgetInput} onChange={e => setBudgetInput(e.target.value)} style={{ flex: 1, padding: "8px 12px", borderRadius: 10, border: "1px solid #EDE8E1", fontFamily: "'DM Sans', sans-serif", fontSize: 14, outline: "none", background: "#FAF6F1" }} />
          <button onClick={() => setTotalBudget(parseFloat(budgetInput) || DEFAULT_BUDGET)} style={{ background: "#3D405B", color: "#FAF6F1", border: "none", borderRadius: 10, padding: "8px 16px", fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>Save</button>
        </div>
      </div>

      {/* Recurring Expenses */}
      <div style={{ background: "#fff", borderRadius: 16, padding: 16, border: "1px solid #EDE8E1", marginBottom: 12 }}>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, color: "#5A5550", margin: "0 0 4px" }}>🔄 Recurring Expenses</p>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#8B8580", margin: "0 0 10px" }}>
          Auto-logged every month. Add via the 🔄 toggle in Quick Entry.
        </p>
        {recurring.length === 0 ? (
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#CCC5BB", textAlign: "center", padding: "8px 0" }}>
            No recurring expenses yet.
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {recurring.map(r => (
              <div key={r.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", background: "#FAF6F1", borderRadius: 10, border: "1px solid #EDE8E1" }}>
                <span style={{ fontSize: 18 }}>{r.emoji}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, fontWeight: 500, color: "#2D2A26", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.note}</p>
                  <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#8B8580", margin: "2px 0 0" }}>{r.category} • monthly</p>
                </div>
                <span style={{ fontFamily: "'Crimson Pro', serif", fontSize: 14, fontWeight: 700, color: "#E07A5F", flexShrink: 0 }}>{currency}{r.amount.toLocaleString()}</span>
                <button onClick={() => onDeleteRecurring(r.id)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 14, color: "#CCC5BB", padding: 0, flexShrink: 0 }}>✕</button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Family Members */}
      <div style={{ background: "#fff", borderRadius: 16, padding: 16, border: "1px solid #EDE8E1", marginBottom: 12 }}>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, color: "#5A5550", margin: "0 0 4px" }}>👨‍👩‍👧 Family Members</p>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#8B8580", margin: "0 0 10px" }}>Tag expenses per person in Quick Entry.</p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
          {members.map(m => (
            <div key={m} style={{ display: "flex", alignItems: "center", gap: 4, padding: "4px 10px", background: "#6C63FF14", borderRadius: 20, border: "1px solid #6C63FF44" }}>
              <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#6C63FF", fontWeight: 600 }}>{m}</span>
              <button onClick={() => onDeleteMember(m)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 11, color: "#6C63FF99", padding: 0, lineHeight: 1 }}>✕</button>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            value={newMember}
            onChange={e => setNewMember(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && newMember.trim()) { onAddMember(newMember.trim()); setNewMember(""); } }}
            placeholder="Add member name..."
            style={{ flex: 1, padding: "7px 12px", borderRadius: 10, border: "1px solid #EDE8E1", fontFamily: "'DM Sans', sans-serif", fontSize: 13, outline: "none", background: "#FAF6F1" }}
          />
          <button
            onClick={() => { if (newMember.trim()) { onAddMember(newMember.trim()); setNewMember(""); } }}
            style={{ background: "#6C63FF", color: "#fff", border: "none", borderRadius: 10, padding: "7px 14px", fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, cursor: "pointer" }}
          >
            Add
          </button>
        </div>
      </div>

      <div style={{ background: "#fff", borderRadius: 16, padding: 16, border: "1px solid #EDE8E1", marginBottom: 12 }}>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, color: "#5A5550", margin: "0 0 4px" }}>Offline Ready</p>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#81B29A", margin: "0 0 0" }}>✅ All data saved locally on your device. No internet needed.</p>
      </div>

      <div style={{ background: "#fff", borderRadius: 16, padding: 16, border: "1px solid #EDE8E1" }}>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, color: "#5A5550", margin: "0 0 8px" }}>Data</p>
        <button
          onClick={() => exportCSV(expenses, currency)}
          disabled={expenses.length === 0}
          style={{ width: "100%", padding: "10px", background: expenses.length ? "#81B29A18" : "#FAF6F1", border: `1px solid ${expenses.length ? "#81B29A66" : "#EDE8E1"}`, borderRadius: 10, fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, color: expenses.length ? "#81B29A" : "#CCC5BB", cursor: expenses.length ? "pointer" : "default", marginBottom: 8 }}
        >
          📥 Export CSV
        </button>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#8B8580", margin: "0 0 10px" }}>
          Downloads all expenses as a spreadsheet — handy for insurance claims or yearly review.
        </p>
        <button onClick={onClearAll} style={{ width: "100%", padding: "10px", background: "#E07A5F18", border: "1px solid #E07A5F44", borderRadius: 10, fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 600, color: "#E07A5F", cursor: "pointer" }}>
          🗑️ Clear All Expenses
        </button>
      </div>
    </div>
  );
}

// ─── Bottom Nav ───────────────────────────────────────────────────────────────

function BottomNav({ selectedView, setSelectedView }) {
  const items = [
    { icon: "🏠", label: "Home",       key: "home"     },
    { icon: "📊", label: "Stats",      key: "stats"    },
    { icon: "🏷️", label: "Categories", key: "cats"     },
    { icon: "⚙️", label: "Settings",   key: "settings" },
  ];
  return (
    <div style={{ position: "fixed", bottom: 0, left: "50%", transform: "translateX(-50%)", width: "100%", maxWidth: 480, background: "rgba(255,255,255,0.95)", backdropFilter: "blur(10px)", borderTop: "1px solid #EDE8E1", display: "flex", justifyContent: "space-around", padding: "8px 0 12px", zIndex: 100 }}>
      {items.map(item => (
        <button key={item.key} onClick={() => setSelectedView(item.key)} style={{ background: "none", border: "none", cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "center", gap: 2, opacity: selectedView === item.key ? 1 : 0.5 }}>
          <span style={{ fontSize: 20 }}>{item.icon}</span>
          <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 10, color: selectedView === item.key ? "#3D405B" : "#8B8580", fontWeight: selectedView === item.key ? 600 : 400 }}>
            {item.label}
          </span>
        </button>
      ))}
    </div>
  );
}

// ─── Root ─────────────────────────────────────────────────────────────────────

export default function App() {
  const [currency,     setCurrency]     = useLocalStorage("et_currency",   "₹");
  const [totalBudget,  setTotalBudget]  = useLocalStorage("et_budget",     DEFAULT_BUDGET);
  const [expenses,     setExpenses]     = useLocalStorage("et_expenses",   []);
  const [categories,   setCategories]   = useLocalStorage("et_categories", DEFAULT_CATEGORIES);
  const [recurring,    setRecurring]    = useLocalStorage("et_recurring",  []);
  const [members,      setMembers]      = useLocalStorage("et_members",    DEFAULT_MEMBERS);
  const [selectedView, setSelectedView] = useState("home");

  // Auto-log recurring expenses once per month on app load
  useEffect(() => {
    if (!recurring.length) return;
    const currentMonth = new Date().toISOString().slice(0, 7);
    const today = todayStr();
    const toLog = recurring.filter(r => r.lastLogged !== currentMonth);
    if (!toLog.length) return;
    setExpenses(prev => [
      ...toLog.map(r => ({
        id:        Date.now() + Math.random(),
        amount:    r.amount,
        category:  r.category,
        note:      r.note,
        date:      today,
        emoji:     r.emoji,
        payment:   r.payment,
        recurring: true,
      })),
      ...prev,
    ]);
    setRecurring(prev => prev.map(r => ({ ...r, lastLogged: currentMonth })));
  }, []);

  const totalSpent  = expenses.reduce((s, e) => s + e.amount, 0);
  const addExpense  = (exp) => setExpenses(prev => [exp, ...prev]);
  const delExpense  = (id)  => setExpenses(prev => prev.filter(e => e.id !== id));
  const addCategory    = (cat) => setCategories(prev => [...prev, cat]);
  const updateCategory = (name, patch) =>
    setCategories(prev => prev.map(c => c.name === name ? { ...c, ...patch } : c));
  const addRecurring    = (r)   => setRecurring(prev => [...prev, r]);
  const deleteRecurring = (id)  => setRecurring(prev => prev.filter(r => r.id !== id));
  const addMember       = (m)   => setMembers(prev => prev.includes(m) ? prev : [...prev, m]);
  const deleteMember    = (m)   => setMembers(prev => prev.filter(x => x !== m));
  const clearAll    = () => {
    if (window.confirm("Clear all expenses? This cannot be undone.")) setExpenses([]);
  };

  return (
    <div style={{ minHeight: "100vh", background: "linear-gradient(180deg, #FAF6F1 0%, #F3EDE4 100%)", fontFamily: "'Crimson Pro', 'Georgia', serif", maxWidth: 480, margin: "0 auto", position: "relative", paddingBottom: 80 }}>
      <link href="https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@300;400;500;600;700&family=DM+Sans:wght@400;500;600&family=Caveat:wght@500;600&display=swap" rel="stylesheet" />

      <Header currency={currency} setCurrency={setCurrency} />

      {selectedView === "home" && (
        <>
          <QuickAdd        currency={currency} categories={categories} members={members} onAdd={addExpense} onAddRecurring={addRecurring} />
          <BudgetCard      currency={currency} totalSpent={totalSpent} totalBudget={totalBudget} />
          <SpendingAlerts  currency={currency} categories={categories} expenses={expenses} />
          <CategoryBreakdown currency={currency} categories={categories} expenses={expenses} onAddCategory={addCategory} onUpdateCategory={updateCategory} />
          <WeeklyTrend   currency={currency} expenses={expenses} />
          <ExpenseList   currency={currency} expenses={expenses} categories={categories} members={members} onDelete={delExpense} />
        </>
      )}

      {selectedView === "stats" && (
        <>
          <BudgetCard        currency={currency} totalSpent={totalSpent} totalBudget={totalBudget} />
          <WeeklyTrend       currency={currency} expenses={expenses} />
          <CategoryBreakdown currency={currency} categories={categories} expenses={expenses} onAddCategory={addCategory} onUpdateCategory={updateCategory} />
        </>
      )}

      {selectedView === "cats" && (
        <CategoryBreakdown currency={currency} categories={categories} expenses={expenses} onAddCategory={addCategory} onUpdateCategory={updateCategory} />
      )}

      {selectedView === "settings" && (
        <SettingsView
          currency={currency}       setCurrency={setCurrency}
          totalBudget={totalBudget} setTotalBudget={setTotalBudget}
          onClearAll={clearAll}     expenses={expenses}
          recurring={recurring}     onDeleteRecurring={deleteRecurring}
          members={members}         onAddMember={addMember}  onDeleteMember={deleteMember}
        />
      )}

      <BottomNav selectedView={selectedView} setSelectedView={setSelectedView} />
    </div>
  );
}
