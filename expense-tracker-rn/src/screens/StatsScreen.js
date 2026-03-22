import React, { useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useApp } from '../context/AppContext';
import { COLORS } from '../constants';
import { todayStr, dateLabel, getLast7Days } from '../utils/helpers';

// ─── Weekly Letter ─────────────────────────────────────────────────────────────
function WeeklyLetter({ currency, expenses, streak, dailyNotes }) {
  const days       = getLast7Days();
  const weekExp    = expenses.filter(e => days.includes(e.date) && e.type !== 'income');
  const weekInc    = expenses.filter(e => days.includes(e.date) && e.type === 'income');
  const totalSpent = weekExp.reduce((s, e) => s + e.amount, 0);
  const totalEarned = weekInc.reduce((s, e) => s + e.amount, 0);

  const catTotals = weekExp.reduce((acc, e) => {
    acc[e.category] = (acc[e.category] || 0) + e.amount;
    return acc;
  }, {});
  const topCat = Object.entries(catTotals).sort((a, b) => b[1] - a[1])[0];

  const lightestDay = days
    .map(d => ({ label: dateLabel(d), spent: weekExp.filter(e => e.date === d).reduce((s, e) => s + e.amount, 0) }))
    .filter(d => d.spent > 0).sort((a, b) => a.spent - b.spent)[0];

  const noteDate    = days.find(d => dailyNotes[d]);
  const d0 = new Date(days[0]);
  const d6 = new Date(days[6]);
  const fmt = d => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  return (
    <View style={wl.card}>
      <Text style={wl.title}>📬 Your Weekly Letter</Text>
      <Text style={wl.dateRange}>{fmt(d6)} — {fmt(d0)}</Text>

      {weekExp.length === 0 ? (
        <Text style={wl.empty}>No entries this week yet. Start logging to see your story!</Text>
      ) : (
        <View style={wl.body}>
          <Text style={wl.line}>
            This week you logged <Text style={wl.bold}>{weekExp.length} entries</Text> totalling{' '}
            <Text style={wl.bold}>{currency}{totalSpent.toLocaleString()}</Text>.
          </Text>
          {topCat && (
            <Text style={wl.line}>
              <Text style={wl.bold}>{topCat[0]}</Text> was your biggest category at{' '}
              <Text style={wl.bold}>{currency}{topCat[1].toLocaleString()}</Text>{' '}
              ({Math.round((topCat[1] / totalSpent) * 100)}%).
            </Text>
          )}
          {lightestDay && (
            <Text style={wl.line}>
              Your lightest day was <Text style={wl.bold}>{lightestDay.label}</Text> — just {currency}{lightestDay.spent.toLocaleString()}.
            </Text>
          )}
          {totalEarned > 0 && (
            <Text style={wl.line}>
              You earned <Text style={wl.bold}>{currency}{totalEarned.toLocaleString()}</Text> this week. 💚
            </Text>
          )}
          {streak?.currentStreak > 0 && (
            <Text style={wl.line}>
              🔥 Your streak: <Text style={wl.bold}>{streak.currentStreak} days</Text> and counting!
            </Text>
          )}
          {noteDate && (
            <View style={wl.noteBlock}>
              <Text style={wl.noteLabel}>Your note this week:</Text>
              <Text style={wl.noteText}>"{dailyNotes[noteDate]}"</Text>
            </View>
          )}
        </View>
      )}
    </View>
  );
}

const wl = StyleSheet.create({
  card:      { margin: 16, marginTop: 8, backgroundColor: '#2D2A26', borderRadius: 16, padding: 20 },
  title:     { fontSize: 22, fontFamily: 'serif', fontWeight: '700', color: '#FAF6F1', textAlign: 'center', marginBottom: 4 },
  dateRange: { fontSize: 12, color: '#CCC5BB', textAlign: 'center', marginBottom: 16 },
  empty:     { fontSize: 13, color: '#CCC5BB', textAlign: 'center', paddingVertical: 16 },
  body:      { backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: 10, padding: 14 },
  line:      { fontSize: 13, color: '#FAF6F1', lineHeight: 22, marginBottom: 6 },
  bold:      { fontWeight: '700' },
  noteBlock: { marginTop: 10, borderLeftWidth: 3, borderLeftColor: '#F2CC8F', paddingLeft: 10 },
  noteLabel: { fontSize: 11, color: '#F2CC8F', marginBottom: 3 },
  noteText:  { fontSize: 12, color: '#FAF6F1', fontStyle: 'italic' },
});

// ─── Simple Bar Chart ─────────────────────────────────────────────────────────
function SimpleBarChart({ data, currency, maxVal }) {
  const max = maxVal || Math.max(...data.map(d => d.value), 1);
  return (
    <View style={bc.container}>
      {data.map((item, i) => (
        <View key={i} style={bc.barGroup}>
          <View style={bc.barWrapper}>
            <View style={[bc.bar, { height: `${Math.round((item.value / max) * 100)}%`, backgroundColor: item.color || COLORS.terracotta }]} />
          </View>
          <Text style={bc.label}>{item.label}</Text>
          {item.value > 0 && <Text style={bc.value}>{currency}{item.value >= 1000 ? Math.round(item.value / 1000) + 'k' : item.value}</Text>}
        </View>
      ))}
    </View>
  );
}

const bc = StyleSheet.create({
  container:  { flexDirection: 'row', alignItems: 'flex-end', height: 120, gap: 4 },
  barGroup:   { flex: 1, alignItems: 'center' },
  barWrapper: { flex: 1, width: '100%', justifyContent: 'flex-end' },
  bar:        { borderRadius: 4, width: '100%' },
  label:      { fontSize: 10, color: COLORS.textLight, marginTop: 4 },
  value:      { fontSize: 9, color: COLORS.textLight },
});

// ─── Weekly Trend ─────────────────────────────────────────────────────────────
function WeeklyTrend({ currency, expenses }) {
  const days = getLast7Days();

  const data = days.map(d => {
    const day = new Date(d + 'T12:00:00');
    return {
      label: day.toLocaleDateString('en-US', { weekday: 'short' }),
      value: expenses.filter(e => e.date === d && e.type !== 'income').reduce((s, e) => s + e.amount, 0),
      color: COLORS.terracotta,
    };
  });

  const totalWeek = data.reduce((s, d) => s + d.value, 0);
  const avgDay    = Math.round(totalWeek / 7);
  const highest   = data.reduce((a, b) => a.value >= b.value ? a : b, { label: '—', value: 0 });

  return (
    <View style={wt.card}>
      <Text style={wt.title}>📈  This Week</Text>
      <SimpleBarChart data={data} currency={currency} />
      <View style={wt.statsRow}>
        <View style={wt.stat}>
          <Text style={wt.statLabel}>Avg/day</Text>
          <Text style={wt.statValue}>{currency}{avgDay.toLocaleString()}</Text>
        </View>
        <View style={wt.stat}>
          <Text style={wt.statLabel}>Total</Text>
          <Text style={wt.statValue}>{currency}{totalWeek.toLocaleString()}</Text>
        </View>
        <View style={wt.stat}>
          <Text style={wt.statLabel}>Highest</Text>
          <Text style={[wt.statValue, { color: COLORS.terracotta }]}>{highest.value > 0 ? highest.label : '—'}</Text>
        </View>
      </View>
    </View>
  );
}

const wt = StyleSheet.create({
  card:      { marginHorizontal: 16, marginBottom: 16, backgroundColor: COLORS.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: COLORS.border },
  title:     { fontSize: 17, fontFamily: 'serif', color: COLORS.textLight, marginBottom: 12 },
  statsRow:  { flexDirection: 'row', justifyContent: 'space-around', marginTop: 12, paddingTop: 12, borderTopWidth: 1, borderTopColor: COLORS.border },
  stat:      { alignItems: 'center' },
  statLabel: { fontSize: 11, color: COLORS.textLight, marginBottom: 2 },
  statValue: { fontSize: 17, fontFamily: 'serif', fontWeight: '700', color: COLORS.textDark },
});

// ─── Category Breakdown ───────────────────────────────────────────────────────
function CategoryBreakdown({ currency, expenses, categories }) {
  const ms     = todayStr().slice(0, 7);
  const expCats = categories.filter(c => c.type !== 'income');
  const data    = expCats.map(c => ({
    label: c.emoji,
    value: expenses.filter(e => e.date?.startsWith(ms) && e.category === c.name && e.type !== 'income').reduce((s, e) => s + e.amount, 0),
    color: c.color,
    name:  c.name,
  })).filter(d => d.value > 0);

  const total = data.reduce((s, d) => s + d.value, 0);

  return (
    <View style={cb.card}>
      <Text style={cb.title}>🏷️  By Category (This Month)</Text>
      {data.length === 0 ? (
        <Text style={cb.empty}>No expenses this month yet.</Text>
      ) : (
        <>
          <SimpleBarChart data={data} currency={currency} />
          <View style={cb.legend}>
            {data.map(d => (
              <View key={d.name} style={cb.legendRow}>
                <View style={[cb.dot, { backgroundColor: d.color }]} />
                <Text style={cb.legendName}>{d.name}</Text>
                <Text style={cb.legendPct}>{Math.round((d.value / total) * 100)}%</Text>
                <Text style={cb.legendAmt}>{currency}{d.value.toLocaleString()}</Text>
              </View>
            ))}
          </View>
        </>
      )}
    </View>
  );
}

const cb = StyleSheet.create({
  card:       { marginHorizontal: 16, marginBottom: 16, backgroundColor: COLORS.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: COLORS.border },
  title:      { fontSize: 17, fontFamily: 'serif', color: COLORS.textLight, marginBottom: 12 },
  empty:      { textAlign: 'center', color: COLORS.textLight, padding: 16 },
  legend:     { marginTop: 12, borderTopWidth: 1, borderTopColor: COLORS.border, paddingTop: 10 },
  legendRow:  { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  dot:        { width: 8, height: 8, borderRadius: 4, marginRight: 8 },
  legendName: { flex: 1, fontSize: 12, color: COLORS.textMid },
  legendPct:  { fontSize: 11, color: COLORS.textLight, marginRight: 8 },
  legendAmt:  { fontSize: 12, fontFamily: 'serif', fontWeight: '700', color: COLORS.textDark },
});

// ─── Stats Screen ─────────────────────────────────────────────────────────────
export default function StatsScreen() {
  const { currency, expenses, categories, streak, dailyNotes } = useApp();
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: COLORS.bg }} edges={['top']}>
      <Text style={ss.heading}>📊  Stats</Text>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 32 }}>
        <WeeklyLetter currency={currency} expenses={expenses} streak={streak} dailyNotes={dailyNotes} />
        <WeeklyTrend  currency={currency} expenses={expenses} />
        <CategoryBreakdown currency={currency} expenses={expenses} categories={categories} />
      </ScrollView>
    </SafeAreaView>
  );
}

const ss = StyleSheet.create({
  heading: { fontSize: 26, fontFamily: 'serif', fontWeight: '700', color: COLORS.textDark, paddingHorizontal: 20, paddingTop: 16, paddingBottom: 4 },
});
