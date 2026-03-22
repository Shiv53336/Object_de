// ─── Date helpers ─────────────────────────────────────────────────────────────
export function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

export function yesterdayStr() {
  return new Date(Date.now() - 86400000).toISOString().slice(0, 10);
}

export function dateLabel(dateStr) {
  const today     = todayStr();
  const yesterday = yesterdayStr();
  if (dateStr === today)     return 'Today';
  if (dateStr === yesterday) return 'Yesterday';
  // Format: "Mar 21"
  const [, m, d] = dateStr.split('-');
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${months[parseInt(m, 10) - 1]} ${parseInt(d, 10)}`;
}

export function monthStr() {
  return todayStr().slice(0, 7); // "2026-03"
}

export function formatAmount(amount, currency = '₹') {
  return `${currency}${Number(amount).toLocaleString()}`;
}

// ─── Budget color ─────────────────────────────────────────────────────────────
export function getBudgetColor(pct) {
  if (pct < 60) return '#81B29A';
  if (pct < 85) return '#F2CC8F';
  return '#E07A5F';
}

// ─── Payment helpers ──────────────────────────────────────────────────────────
export function paymentColor(p) {
  if (p === 'UPI')  return { bg: '#6C63FF18', fg: '#6C63FF' };
  if (p === 'Card') return { bg: '#E07A5F18', fg: '#E07A5F' };
  if (p === 'Cash') return { bg: '#81B29A18', fg: '#81B29A' };
  return { bg: '#EDE8E1', fg: '#8B8580' };
}

export function paymentIcon(p) {
  if (p === 'UPI')  return '📱';
  if (p === 'Card') return '💳';
  if (p === 'Cash') return '💵';
  return '💸';
}

// ─── Week data ────────────────────────────────────────────────────────────────
export function getLast7Days() {
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - (6 - i));
    return d.toISOString().slice(0, 10);
  });
}

export function getDaysInMonth() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
}

export function getDaysLeft() {
  const now = new Date();
  return getDaysInMonth() - now.getDate();
}
