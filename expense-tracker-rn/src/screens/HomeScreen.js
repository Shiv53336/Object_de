import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView,
  StyleSheet, Alert, Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useApp } from '../context/AppContext';
import { COLORS, PAYMENT_TYPES } from '../constants';
import { todayStr, yesterdayStr, dateLabel, getDaysLeft, getBudgetColor, paymentColor } from '../utils/helpers';
import EditModal from '../components/EditModal';

// ─── Header ───────────────────────────────────────────────────────────────────
function Header({ currency, setCurrency, streak }) {
  const [showCurrency, setShowCurrency] = useState(false);
  const currencies = ['₹', '$', '€', '£'];
  const monthName = new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

  return (
    <View style={h.container}>
      <View>
        <Text style={h.title}>My Expenses</Text>
        <Text style={h.subtitle}>{monthName}</Text>
      </View>
      <View style={h.right}>
        {streak?.currentStreak > 0 && (
          <View style={h.streakBadge}>
            <Text style={h.streakFire}>🔥</Text>
            <Text style={h.streakText}>{streak.currentStreak} {streak.currentStreak === 1 ? 'day' : 'days'}</Text>
          </View>
        )}
        <TouchableOpacity style={h.currencyBtn} onPress={() => setShowCurrency(true)}>
          <Text style={h.currencyText}>{currency}</Text>
        </TouchableOpacity>
      </View>

      <Modal visible={showCurrency} transparent animationType="fade" onRequestClose={() => setShowCurrency(false)}>
        <TouchableOpacity style={h.overlay} onPress={() => setShowCurrency(false)}>
          <View style={h.picker}>
            {currencies.map(c => (
              <TouchableOpacity key={c} style={h.pickerItem} onPress={() => { setCurrency(c); setShowCurrency(false); }}>
                <Text style={[h.pickerText, c === currency && { color: COLORS.navy, fontWeight: '700' }]}>{c}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </TouchableOpacity>
      </Modal>
    </View>
  );
}

const h = StyleSheet.create({
  container:   { paddingHorizontal: 20, paddingTop: 16, paddingBottom: 8, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  title:       { fontSize: 30, fontFamily: 'serif', fontWeight: '700', color: COLORS.textDark, letterSpacing: -0.5 },
  subtitle:    { fontSize: 13, color: COLORS.textLight, marginTop: 2 },
  right:       { flexDirection: 'row', alignItems: 'center', gap: 8 },
  streakBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#FFF8E1', borderWidth: 1, borderColor: '#F2CC8F', borderRadius: 20, paddingVertical: 5, paddingHorizontal: 10 },
  streakFire:  { fontSize: 14 },
  streakText:  { fontSize: 12, fontWeight: '700', color: '#C8960C' },
  currencyBtn: { backgroundColor: COLORS.card, borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingVertical: 6, paddingHorizontal: 12 },
  currencyText:{ fontSize: 16, fontWeight: '700', color: COLORS.navy },
  overlay:     { flex: 1, backgroundColor: 'rgba(0,0,0,0.3)', justifyContent: 'center', alignItems: 'center' },
  picker:      { backgroundColor: COLORS.card, borderRadius: 16, padding: 8, minWidth: 120 },
  pickerItem:  { padding: 14, alignItems: 'center' },
  pickerText:  { fontSize: 20, color: COLORS.textMid },
});

// ─── Quick Add ────────────────────────────────────────────────────────────────
function QuickAdd({ currency, categories, onAdd }) {
  const [amount,    setAmount]    = useState('');
  const [cat,       setCat]       = useState('');
  const [note,      setNote]      = useState('');
  const [payment,   setPayment]   = useState('UPI');
  const [entryType, setEntryType] = useState('expense');

  const filteredCats = categories.filter(c => c.type === entryType);
  const activeCat = cat || filteredCats[0]?.name || '';
  const accentColor = entryType === 'expense' ? COLORS.terracotta : COLORS.sage;

  const handleAdd = () => {
    const num = parseFloat(amount);
    if (!num || num <= 0) { Alert.alert('Enter a valid amount'); return; }
    const catObj = categories.find(c => c.name === activeCat) || filteredCats[0];
    onAdd({
      id:       Date.now(),
      amount:   num,
      category: activeCat,
      note:     note || activeCat,
      date:     todayStr(),
      emoji:    catObj?.emoji || '💸',
      payment:  entryType === 'income' ? '—' : payment,
      type:     entryType,
    });
    setAmount('');
    setNote('');
  };

  return (
    <View style={qa.card}>
      {/* Toggle expense / income */}
      <View style={qa.toggleRow}>
        <Text style={qa.sectionTitle}>✏️  Quick Entry</Text>
        <View style={qa.toggle}>
          {['expense', 'income'].map(t => (
            <TouchableOpacity
              key={t}
              onPress={() => { setEntryType(t); setCat(''); }}
              style={[qa.toggleBtn, entryType === t && { backgroundColor: t === 'expense' ? COLORS.terracotta : COLORS.sage }]}
            >
              <Text style={[qa.toggleText, entryType === t && { color: '#fff' }]}>
                {t === 'expense' ? 'Expense' : 'Income'}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Amount row */}
      <View style={[qa.amountRow, { borderColor: accentColor + '55' }]}>
        <Text style={[qa.currency, { color: accentColor }]}>{currency}</Text>
        <TextInput
          value={amount}
          onChangeText={setAmount}
          keyboardType="decimal-pad"
          placeholder="0"
          placeholderTextColor={COLORS.textFaint}
          style={qa.amountInput}
          returnKeyType="done"
          onSubmitEditing={handleAdd}
        />
        <TouchableOpacity style={[qa.addBtn, { backgroundColor: accentColor }]} onPress={handleAdd}>
          <Text style={qa.addBtnText}>Add</Text>
        </TouchableOpacity>
      </View>

      {/* Note */}
      <TextInput
        value={note}
        onChangeText={setNote}
        placeholder="Add a note..."
        placeholderTextColor={COLORS.textLight}
        style={qa.noteInput}
        returnKeyType="done"
        onSubmitEditing={handleAdd}
      />

      {/* Category chips */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={qa.catScroll}>
        {filteredCats.map(c => (
          <TouchableOpacity
            key={c.name}
            onPress={() => setCat(c.name)}
            style={[qa.catChip, activeCat === c.name && { backgroundColor: c.color + '22', borderColor: c.color, borderWidth: 2 }]}
          >
            <Text style={qa.catEmoji}>{c.emoji}</Text>
            <Text style={[qa.catName, activeCat === c.name && { color: c.color, fontWeight: '700' }]}>
              {c.name.split(' ')[0]}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Payment type (expenses only) */}
      {entryType === 'expense' && (
        <View style={qa.payRow}>
          <Text style={qa.payLabel}>Paid via:</Text>
          {PAYMENT_TYPES.filter(p => p.label !== 'Other').map(pt => (
            <TouchableOpacity
              key={pt.label}
              onPress={() => setPayment(pt.label)}
              style={[qa.payChip, payment === pt.label && { borderColor: pt.color, borderWidth: 2, backgroundColor: pt.color + '14' }]}
            >
              <Text style={qa.payIcon}>{pt.icon}</Text>
              <Text style={[qa.payText, payment === pt.label && { color: pt.color, fontWeight: '700' }]}>{pt.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}
    </View>
  );
}

const qa = StyleSheet.create({
  card:       { margin: 16, marginTop: 8, backgroundColor: COLORS.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: COLORS.border },
  toggleRow:  { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  sectionTitle:{ fontSize: 17, fontFamily: 'serif', color: COLORS.textLight },
  toggle:     { flexDirection: 'row', backgroundColor: COLORS.bg, borderRadius: 20, padding: 3, borderWidth: 1, borderColor: COLORS.border },
  toggleBtn:  { paddingVertical: 5, paddingHorizontal: 14, borderRadius: 16 },
  toggleText: { fontSize: 12, fontWeight: '600', color: COLORS.textLight },
  amountRow:  { flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.bg, borderRadius: 12, padding: 12, marginBottom: 10, borderWidth: 1.5 },
  currency:   { fontSize: 20, marginRight: 6, fontWeight: '700' },
  amountInput:{ flex: 1, fontSize: 26, fontFamily: 'serif', fontWeight: '700', color: COLORS.textDark },
  addBtn:     { borderRadius: 10, paddingVertical: 8, paddingHorizontal: 16 },
  addBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  noteInput:  { backgroundColor: COLORS.bg, borderRadius: 10, padding: 10, fontSize: 13, color: COLORS.textDark, borderWidth: 1, borderColor: COLORS.border, marginBottom: 10 },
  catScroll:  { marginBottom: 10 },
  catChip:    { alignItems: 'center', backgroundColor: COLORS.bg, borderRadius: 10, padding: 8, marginRight: 8, borderWidth: 1, borderColor: COLORS.border, minWidth: 60 },
  catEmoji:   { fontSize: 18, marginBottom: 2 },
  catName:    { fontSize: 10, color: COLORS.textMid },
  payRow:     { flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' },
  payLabel:   { fontSize: 12, color: COLORS.textLight, marginRight: 2 },
  payChip:    { flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 20, paddingVertical: 5, paddingHorizontal: 10, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.bg },
  payIcon:    { fontSize: 13 },
  payText:    { fontSize: 11, color: COLORS.textLight },
});

// ─── Budget Card ──────────────────────────────────────────────────────────────
function BudgetCard({ currency, expenses, budget, categories }) {
  const ms = todayStr().slice(0, 7);
  const monthExp     = expenses.filter(e => e.date?.startsWith(ms));
  const totalExpenses = monthExp.filter(e => e.type !== 'income').reduce((s, e) => s + e.amount, 0);
  const totalIncome   = monthExp.filter(e => e.type === 'income').reduce((s, e) => s + e.amount, 0);
  const net           = totalIncome - totalExpenses;
  const pct           = Math.min(100, Math.round((totalExpenses / budget) * 100));
  const barColor      = getBudgetColor(pct);
  const daysLeft      = getDaysLeft();
  const expCats       = categories.filter(c => c.type !== 'income' && c.budget > 0);

  return (
    <View style={bc.card}>
      {/* Income / Expenses / Net row */}
      <View style={bc.summaryRow}>
        <View style={[bc.summaryItem, { backgroundColor: '#F0F9F5' }]}>
          <Text style={[bc.summaryLabel, { color: COLORS.sage }]}>INCOME</Text>
          <Text style={[bc.summaryValue, { color: COLORS.sage }]}>{currency}{totalIncome.toLocaleString()}</Text>
        </View>
        <View style={[bc.summaryItem, { backgroundColor: '#FFF1EE' }]}>
          <Text style={[bc.summaryLabel, { color: COLORS.terracotta }]}>EXPENSES</Text>
          <Text style={[bc.summaryValue, { color: COLORS.terracotta }]}>{currency}{totalExpenses.toLocaleString()}</Text>
        </View>
        <View style={[bc.summaryItem, { backgroundColor: net >= 0 ? '#F0F9F5' : '#FFF1EE' }]}>
          <Text style={[bc.summaryLabel, { color: net >= 0 ? COLORS.sage : COLORS.terracotta }]}>NET</Text>
          <Text style={[bc.summaryValue, { color: net >= 0 ? COLORS.sage : COLORS.terracotta }]}>
            {net >= 0 ? '+' : ''}{currency}{net.toLocaleString()}
          </Text>
        </View>
      </View>

      {/* Budget bar */}
      <View style={bc.budgetHeader}>
        <Text style={bc.budgetLabel}>📊  Monthly Budget</Text>
        <View style={[bc.pctBadge, { backgroundColor: barColor + '22' }]}>
          <Text style={[bc.pctText, { color: barColor }]}>{pct}% used</Text>
        </View>
      </View>
      <View style={bc.barBg}>
        <View style={[bc.barFill, { width: `${pct}%`, backgroundColor: barColor }]} />
      </View>
      <Text style={bc.budgetMeta}>
        {currency}{totalExpenses.toLocaleString()} of {currency}{budget.toLocaleString()} • {daysLeft} days left
      </Text>

      {/* Per-category mini bars */}
      {expCats.slice(0, 4).map(c => {
        const spent  = monthExp.filter(e => e.category === c.name && e.type !== 'income').reduce((s, e) => s + e.amount, 0);
        const cPct   = Math.min(100, Math.round((spent / c.budget) * 100));
        const cColor = cPct > 85 ? COLORS.terracotta : c.color;
        return (
          <View key={c.name} style={bc.catRow}>
            <View style={bc.catInfo}>
              <Text style={bc.catName}>{c.emoji} {c.name}</Text>
              <Text style={[bc.catAmounts, cPct > 85 && { color: COLORS.terracotta }]}>
                {currency}{spent.toLocaleString()} / {currency}{c.budget.toLocaleString()}
              </Text>
            </View>
            <View style={bc.miniBarBg}>
              <View style={[bc.miniBarFill, { width: `${cPct}%`, backgroundColor: cColor }]} />
            </View>
          </View>
        );
      })}
    </View>
  );
}

const bc = StyleSheet.create({
  card:        { margin: 16, marginTop: 0, backgroundColor: COLORS.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: COLORS.border },
  summaryRow:  { flexDirection: 'row', gap: 8, marginBottom: 14 },
  summaryItem: { flex: 1, borderRadius: 10, padding: 10 },
  summaryLabel:{ fontSize: 10, fontWeight: '700', letterSpacing: 0.4, marginBottom: 3 },
  summaryValue:{ fontSize: 16, fontFamily: 'serif', fontWeight: '700' },
  budgetHeader:{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  budgetLabel: { fontSize: 14, fontFamily: 'serif', color: COLORS.textLight },
  pctBadge:    { borderRadius: 6, paddingVertical: 2, paddingHorizontal: 7 },
  pctText:     { fontSize: 11, fontWeight: '700' },
  barBg:       { height: 8, backgroundColor: COLORS.border, borderRadius: 6, marginBottom: 6, overflow: 'hidden' },
  barFill:     { height: '100%', borderRadius: 6 },
  budgetMeta:  { fontSize: 12, color: COLORS.textLight, marginBottom: 12 },
  catRow:      { marginBottom: 8 },
  catInfo:     { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 3 },
  catName:     { fontSize: 11, color: COLORS.textMid },
  catAmounts:  { fontSize: 11, color: COLORS.textLight },
  miniBarBg:   { height: 4, backgroundColor: COLORS.border, borderRadius: 4, overflow: 'hidden' },
  miniBarFill: { height: '100%', borderRadius: 4 },
});

// ─── Expense List ─────────────────────────────────────────────────────────────
function ExpenseList({ currency, expenses, categories, onEdit }) {
  const [search,    setSearch]    = useState('');
  const [filterCat, setFilterCat] = useState('All');
  const [sortBy,    setSortBy]    = useState('newest');

  let filtered = expenses.filter(e => {
    const ms = !search || e.note?.toLowerCase().includes(search.toLowerCase()) || e.category?.toLowerCase().includes(search.toLowerCase());
    const mc = filterCat === 'All' || e.category === filterCat;
    return ms && mc;
  });

  filtered = [...filtered].sort((a, b) => {
    if (sortBy === 'newest')  return b.date.localeCompare(a.date) || b.id - a.id;
    if (sortBy === 'oldest')  return a.date.localeCompare(b.date) || a.id - b.id;
    if (sortBy === 'highest') return b.amount - a.amount;
    if (sortBy === 'lowest')  return a.amount - b.amount;
    return 0;
  });

  const grouped = filtered.reduce((acc, exp) => {
    const lbl = dateLabel(exp.date);
    acc[lbl] = acc[lbl] || [];
    acc[lbl].push(exp);
    return acc;
  }, {});

  const uniqueCats = ['All', ...new Set(expenses.map(e => e.category))];

  return (
    <View style={el.container}>
      {/* Search */}
      <View style={el.searchRow}>
        <Text style={el.searchIcon}>🔍</Text>
        <TextInput
          value={search}
          onChangeText={setSearch}
          placeholder="Search..."
          placeholderTextColor={COLORS.textLight}
          style={el.searchInput}
        />
      </View>

      {/* Filter chips */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={el.filterScroll}>
        {uniqueCats.slice(0, 8).map(c => {
          const catObj = categories.find(x => x.name === c);
          return (
            <TouchableOpacity
              key={c}
              onPress={() => setFilterCat(c)}
              style={[el.filterChip, filterCat === c && { backgroundColor: COLORS.navy, borderColor: COLORS.navy }]}
            >
              <Text style={[el.filterText, filterCat === c && { color: '#fff', fontWeight: '700' }]}>
                {c === 'All' ? 'All' : `${catObj?.emoji || ''} ${c.split(' ')[0]}`}
              </Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      {/* List header */}
      <Text style={el.listHeader}>📝  Recent Entries</Text>

      {/* Entries */}
      {filtered.length === 0 ? (
        <Text style={el.empty}>
          {expenses.length === 0 ? 'No entries yet. Add your first one above! 👆' : 'No entries match your filter.'}
        </Text>
      ) : (
        Object.entries(grouped).map(([date, exps]) => (
          <View key={date}>
            <Text style={el.dateLabel}>{date.toUpperCase()}</Text>
            {exps.map(exp => {
              const isIncome = exp.type === 'income';
              const pc = paymentColor(exp.payment);
              return (
                <TouchableOpacity key={exp.id} style={[el.item, { borderColor: isIncome ? '#C8E6C9' : COLORS.border }]} onPress={() => onEdit(exp)} activeOpacity={0.7}>
                  <View style={[el.emoji, { backgroundColor: isIncome ? '#F0F9F5' : COLORS.bg }]}>
                    <Text style={el.emojiText}>{exp.emoji}</Text>
                  </View>
                  <View style={el.itemInfo}>
                    <Text style={el.itemNote} numberOfLines={1}>{exp.note}</Text>
                    <View style={el.itemMeta}>
                      <Text style={el.itemCat}>{exp.category}</Text>
                      {isIncome ? (
                        <View style={{ backgroundColor: '#81B29A18', borderRadius: 8, paddingVertical: 1, paddingHorizontal: 5 }}>
                          <Text style={{ fontSize: 9, color: COLORS.sage, fontWeight: '700' }}>Income</Text>
                        </View>
                      ) : exp.payment && exp.payment !== '—' ? (
                        <View style={[el.payBadge, { backgroundColor: pc.bg }]}>
                          <Text style={[el.payBadgeText, { color: pc.fg }]}>{exp.payment}</Text>
                        </View>
                      ) : null}
                    </View>
                  </View>
                  <Text style={[el.amount, { color: isIncome ? COLORS.sage : COLORS.terracotta }]}>
                    {isIncome ? '+' : '−'}{exp.amount.toLocaleString()}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        ))
      )}
    </View>
  );
}

const el = StyleSheet.create({
  container:   { marginHorizontal: 16 },
  searchRow:   { flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.card, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 8, borderWidth: 1, borderColor: COLORS.border, marginBottom: 8 },
  searchIcon:  { fontSize: 14, marginRight: 6 },
  searchInput: { flex: 1, fontSize: 13, color: COLORS.textDark },
  filterScroll:{ marginBottom: 10 },
  filterChip:  { paddingVertical: 4, paddingHorizontal: 12, borderRadius: 20, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.card, marginRight: 6 },
  filterText:  { fontSize: 11, color: COLORS.textLight },
  listHeader:  { fontSize: 17, fontFamily: 'serif', color: COLORS.textLight, marginBottom: 10 },
  empty:       { textAlign: 'center', padding: 32, color: COLORS.textLight, fontSize: 14 },
  dateLabel:   { fontSize: 11, fontWeight: '700', color: COLORS.textLight, marginBottom: 6, letterSpacing: 0.5 },
  item:        { flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.card, borderRadius: 12, padding: 12, marginBottom: 6, borderWidth: 1 },
  emoji:       { width: 38, height: 38, borderRadius: 10, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  emojiText:   { fontSize: 18 },
  itemInfo:    { flex: 1 },
  itemNote:    { fontSize: 13, fontWeight: '500', color: COLORS.textDark },
  itemMeta:    { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 2 },
  itemCat:     { fontSize: 11, color: COLORS.textLight },
  payBadge:    { borderRadius: 8, paddingVertical: 1, paddingHorizontal: 5 },
  payBadgeText:{ fontSize: 9, fontWeight: '700' },
  amount:      { fontSize: 15, fontFamily: 'serif', fontWeight: '700' },
});

// ─── Daily Note ───────────────────────────────────────────────────────────────
function DailyNote({ currency, expenses, dailyNotes, onSave }) {
  const today     = todayStr();
  const yesterday = yesterdayStr();
  const [note, setNote] = useState(dailyNotes[today] || '');

  const todayExp   = expenses.filter(e => e.date === today && e.type !== 'income');
  const todayTotal = todayExp.reduce((s, e) => s + e.amount, 0);
  const topCat     = Object.entries(
    todayExp.reduce((acc, e) => { acc[e.category] = (acc[e.category] || 0) + e.amount; return acc; }, {})
  ).sort((a, b) => b[1] - a[1])[0];

  return (
    <View style={dn.card}>
      <Text style={dn.title}>📝  Today's Note</Text>
      {todayTotal > 0 && (
        <View style={dn.summary}>
          <Text style={dn.summaryText}>
            You spent <Text style={{ fontWeight: '700' }}>{currency}{todayTotal.toLocaleString()}</Text> across {todayExp.length} {todayExp.length === 1 ? 'entry' : 'entries'}.
            {topCat ? ` Top: ${topCat[0]} (${currency}${topCat[1].toLocaleString()})` : ''}
          </Text>
        </View>
      )}
      <TextInput
        value={note}
        onChangeText={setNote}
        placeholder="How was your spending today? Write a quick reflection..."
        placeholderTextColor={COLORS.textLight}
        multiline
        numberOfLines={3}
        style={dn.textarea}
        textAlignVertical="top"
      />
      <TouchableOpacity style={dn.saveBtn} onPress={() => onSave(today, note)}>
        <Text style={dn.saveBtnText}>Save Note 💾</Text>
      </TouchableOpacity>
      {dailyNotes[yesterday] && (
        <View style={dn.yesterday}>
          <Text style={dn.yesterdayLabel}>Yesterday:</Text>
          <Text style={dn.yesterdayText}>"{dailyNotes[yesterday]}"</Text>
        </View>
      )}
    </View>
  );
}

const dn = StyleSheet.create({
  card:         { margin: 16, marginTop: 0, backgroundColor: COLORS.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: COLORS.border },
  title:        { fontSize: 17, fontFamily: 'serif', color: COLORS.textLight, marginBottom: 10 },
  summary:      { backgroundColor: COLORS.bg, borderRadius: 8, padding: 10, marginBottom: 10 },
  summaryText:  { fontSize: 12, color: COLORS.textMid, lineHeight: 18 },
  textarea:     { backgroundColor: COLORS.bg, borderRadius: 10, padding: 12, fontSize: 13, color: COLORS.textDark, borderWidth: 1, borderColor: COLORS.border, minHeight: 72, marginBottom: 10, lineHeight: 20 },
  saveBtn:      { alignSelf: 'flex-end', backgroundColor: COLORS.navy, borderRadius: 8, paddingVertical: 7, paddingHorizontal: 16 },
  saveBtnText:  { color: '#fff', fontWeight: '700', fontSize: 12 },
  yesterday:    { marginTop: 10, borderLeftWidth: 3, borderLeftColor: COLORS.terracotta, paddingLeft: 10, paddingVertical: 4, backgroundColor: COLORS.bg, borderRadius: 4 },
  yesterdayLabel:{ fontSize: 11, color: COLORS.textLight, marginBottom: 2 },
  yesterdayText: { fontSize: 12, color: COLORS.textMid, fontStyle: 'italic' },
});

// ─── Home Screen ──────────────────────────────────────────────────────────────
export default function HomeScreen() {
  const {
    currency, setCurrency, expenses, categories, budget, dailyNotes,
    streak, addExpense, deleteExpense, editExpense, saveNote,
  } = useApp();

  const [editingExp, setEditingExp] = useState(null);

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      <Header currency={currency} setCurrency={setCurrency} streak={streak} />
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 32 }}>
        <QuickAdd currency={currency} categories={categories} onAdd={addExpense} />
        <BudgetCard currency={currency} expenses={expenses} budget={budget} categories={categories} />
        <ExpenseList currency={currency} expenses={expenses} categories={categories} onEdit={setEditingExp} />
        <DailyNote currency={currency} expenses={expenses} dailyNotes={dailyNotes} onSave={saveNote} />
      </ScrollView>
      {editingExp && (
        <EditModal
          expense={editingExp}
          categories={categories}
          currency={currency}
          onSave={editExpense}
          onDelete={deleteExpense}
          onClose={() => setEditingExp(null)}
        />
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.bg },
});
