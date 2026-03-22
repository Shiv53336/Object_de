import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView, StyleSheet, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useApp } from '../context/AppContext';
import { COLORS, CURRENCIES, RAND_COLORS } from '../constants';
import { todayStr } from '../utils/helpers';

// ─── Category Manager ─────────────────────────────────────────────────────────
function CategoryManager({ currency, categories, expenses, onAddCategory }) {
  const [showForm, setShowForm]   = useState(false);
  const [emoji,    setEmoji]      = useState('');
  const [name,     setName]       = useState('');
  const [budgetV,  setBudgetV]    = useState('');
  const [catType,  setCatType]    = useState('expense');
  const [tab,      setTab]        = useState('expense');

  const ms  = todayStr().slice(0, 7);
  const cats = categories.filter(c => c.type === tab);

  const handleSave = () => {
    if (!name.trim()) { Alert.alert('Enter a category name'); return; }
    onAddCategory({
      name:   name.trim(),
      emoji:  emoji || '🏷️',
      color:  RAND_COLORS[Math.floor(Math.random() * RAND_COLORS.length)],
      budget: parseFloat(budgetV) || 1000,
      type:   catType,
    });
    setEmoji(''); setName(''); setBudgetV(''); setShowForm(false);
  };

  return (
    <View style={cm.card}>
      <View style={cm.headerRow}>
        <Text style={cm.title}>🏷️  Categories</Text>
        <TouchableOpacity style={cm.addBtn} onPress={() => setShowForm(!showForm)}>
          <Text style={cm.addBtnText}>+ Add</Text>
        </TouchableOpacity>
      </View>

      {/* Tab */}
      <View style={cm.tabRow}>
        {['expense', 'income'].map(t => (
          <TouchableOpacity key={t} onPress={() => setTab(t)}
            style={[cm.tab, tab === t && { backgroundColor: COLORS.navy }]}>
            <Text style={[cm.tabText, tab === t && { color: '#fff', fontWeight: '700' }]}>{t}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Add form */}
      {showForm && (
        <View style={cm.form}>
          <View style={cm.typeRow}>
            {['expense', 'income'].map(t => (
              <TouchableOpacity key={t} onPress={() => setCatType(t)}
                style={[cm.typeBtn, catType === t && { backgroundColor: COLORS.navy }]}>
                <Text style={[cm.typeBtnText, catType === t && { color: '#fff' }]}>{t}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <View style={cm.formRow}>
            <TextInput value={emoji} onChangeText={setEmoji} placeholder="🏷️" maxLength={2}
              style={cm.emojiInput} />
            <TextInput value={name} onChangeText={setName} placeholder="Category name"
              placeholderTextColor={COLORS.textLight} style={[cm.textInput, { flex: 1, marginHorizontal: 6 }]} />
            <TextInput value={budgetV} onChangeText={setBudgetV} placeholder="Budget"
              keyboardType="decimal-pad" placeholderTextColor={COLORS.textLight}
              style={[cm.textInput, { width: 80 }]} />
          </View>
          <TouchableOpacity style={cm.saveBtn} onPress={handleSave}>
            <Text style={cm.saveBtnText}>Save</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Category list */}
      {cats.map(c => {
        const spent = expenses.filter(e => e.date?.startsWith(ms) && e.category === c.name).reduce((s, e) => s + e.amount, 0);
        return (
          <View key={c.name} style={cm.catRow}>
            <View style={[cm.dot, { backgroundColor: c.color }]} />
            <Text style={cm.catEmoji}>{c.emoji}</Text>
            <Text style={cm.catName}>{c.name}</Text>
            {c.budget > 0 && <Text style={cm.catBudget}>{spent.toLocaleString()} / {c.budget.toLocaleString()}</Text>}
          </View>
        );
      })}
    </View>
  );
}

const cm = StyleSheet.create({
  card:        { backgroundColor: COLORS.card, borderRadius: 16, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border },
  headerRow:   { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  title:       { fontSize: 15, fontWeight: '600', color: COLORS.textMid },
  addBtn:      { backgroundColor: COLORS.navy + '18', borderRadius: 8, paddingVertical: 4, paddingHorizontal: 10, borderWidth: 1, borderColor: COLORS.navy + '44' },
  addBtnText:  { fontSize: 12, fontWeight: '700', color: COLORS.navy },
  tabRow:      { flexDirection: 'row', backgroundColor: COLORS.bg, borderRadius: 10, padding: 2, marginBottom: 10 },
  tab:         { flex: 1, paddingVertical: 5, alignItems: 'center', borderRadius: 8 },
  tabText:     { fontSize: 12, color: COLORS.textLight },
  form:        { backgroundColor: COLORS.bg, borderRadius: 10, padding: 10, marginBottom: 10 },
  typeRow:     { flexDirection: 'row', gap: 6, marginBottom: 8 },
  typeBtn:     { flex: 1, paddingVertical: 5, alignItems: 'center', borderRadius: 8, borderWidth: 1, borderColor: COLORS.border },
  typeBtnText: { fontSize: 11, color: COLORS.textLight },
  formRow:     { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  emojiInput:  { width: 44, height: 44, borderRadius: 8, backgroundColor: COLORS.card, borderWidth: 1, borderColor: COLORS.border, textAlign: 'center', fontSize: 20 },
  textInput:   { backgroundColor: COLORS.card, borderRadius: 8, padding: 10, fontSize: 13, color: COLORS.textDark, borderWidth: 1, borderColor: COLORS.border },
  saveBtn:     { backgroundColor: COLORS.sage, borderRadius: 8, padding: 8, alignItems: 'center' },
  saveBtnText: { color: '#fff', fontWeight: '700', fontSize: 13 },
  catRow:      { flexDirection: 'row', alignItems: 'center', paddingVertical: 8, borderTopWidth: 1, borderTopColor: COLORS.border },
  dot:         { width: 8, height: 8, borderRadius: 4, marginRight: 6 },
  catEmoji:    { fontSize: 16, marginRight: 6 },
  catName:     { flex: 1, fontSize: 13, color: COLORS.textMid },
  catBudget:   { fontSize: 11, color: COLORS.textLight },
});

// ─── Settings Screen ──────────────────────────────────────────────────────────
export default function SettingsScreen() {
  const {
    currency, setCurrency,
    budget, setBudget,
    expenses, categories, addCategory,
    streak,
    clearAll,
  } = useApp();

  const [budgetInput, setBudgetInput] = useState(String(budget));

  const handleSaveBudget = () => {
    const n = parseFloat(budgetInput);
    if (!n || n <= 0) { Alert.alert('Enter a valid budget'); return; }
    setBudget(n);
    Alert.alert('Saved!', 'Monthly budget updated.');
  };

  const handleClearAll = () => {
    Alert.alert('Clear all expenses?', 'This cannot be undone.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Clear', style: 'destructive', onPress: clearAll },
    ]);
  };

  const handleExport = async () => {
    try {
      const data = JSON.stringify({ expenses, categories, currency, budget, exportedAt: new Date().toISOString() }, null, 2);
      // On mobile we can log it or show in alert (file system export needs expo-file-system + expo-sharing)
      Alert.alert('Export Data', `Exported ${expenses.length} expenses.\n\nInstall expo-file-system to save as file.`);
    } catch (e) {
      Alert.alert('Export failed', e.message);
    }
  };

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      <Text style={s.heading}>⚙️  Settings</Text>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>

        {/* Streak */}
        {streak?.currentStreak > 0 && (
          <View style={s.streakCard}>
            <Text style={s.streakTitle}>🔥 Current Streak</Text>
            <Text style={s.streakVal}>{streak.currentStreak} days</Text>
            <Text style={s.streakSub}>Longest: {streak.longestStreak} days</Text>
          </View>
        )}

        {/* Currency */}
        <View style={s.card}>
          <Text style={s.cardTitle}>Currency</Text>
          <View style={s.currencyRow}>
            {Object.entries(CURRENCIES).map(([sym]) => (
              <TouchableOpacity
                key={sym}
                onPress={() => setCurrency(sym)}
                style={[s.currencyChip, currency === sym && { backgroundColor: COLORS.navy, borderColor: COLORS.navy }]}
              >
                <Text style={[s.currencyText, currency === sym && { color: '#fff', fontWeight: '700' }]}>{sym}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Budget */}
        <View style={s.card}>
          <Text style={s.cardTitle}>Monthly Budget</Text>
          <View style={s.budgetRow}>
            <Text style={s.budgetCurrency}>{currency}</Text>
            <TextInput
              value={budgetInput}
              onChangeText={setBudgetInput}
              keyboardType="decimal-pad"
              style={s.budgetInput}
            />
            <TouchableOpacity style={s.saveBtn} onPress={handleSaveBudget}>
              <Text style={s.saveBtnText}>Save</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Categories */}
        <CategoryManager
          currency={currency}
          categories={categories}
          expenses={expenses}
          onAddCategory={addCategory}
        />

        {/* Data */}
        <View style={s.card}>
          <Text style={s.cardTitle}>Data</Text>
          <TouchableOpacity style={s.exportBtn} onPress={handleExport}>
            <Text style={s.exportText}>📤  Export Data</Text>
          </TouchableOpacity>
          <TouchableOpacity style={s.clearBtn} onPress={handleClearAll}>
            <Text style={s.clearText}>🗑️  Clear All Expenses</Text>
          </TouchableOpacity>
        </View>

        {/* Info */}
        <View style={s.infoCard}>
          <Text style={s.infoText}>✅  All data saved locally on your device. No account needed. No internet required.</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root:         { flex: 1, backgroundColor: COLORS.bg },
  heading:      { fontSize: 26, fontFamily: 'serif', fontWeight: '700', color: COLORS.textDark, paddingHorizontal: 20, paddingTop: 16, paddingBottom: 4 },
  streakCard:   { backgroundColor: '#FFF8E1', borderRadius: 16, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: '#F2CC8F', alignItems: 'center' },
  streakTitle:  { fontSize: 14, fontWeight: '600', color: '#C8960C', marginBottom: 4 },
  streakVal:    { fontSize: 32, fontFamily: 'serif', fontWeight: '700', color: '#C8960C' },
  streakSub:    { fontSize: 12, color: '#C8960C', marginTop: 4 },
  card:         { backgroundColor: COLORS.card, borderRadius: 16, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border },
  cardTitle:    { fontSize: 14, fontWeight: '600', color: COLORS.textMid, marginBottom: 10 },
  currencyRow:  { flexDirection: 'row', gap: 8 },
  currencyChip: { flex: 1, alignItems: 'center', padding: 10, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.bg },
  currencyText: { fontSize: 18, color: COLORS.textMid },
  budgetRow:    { flexDirection: 'row', alignItems: 'center', gap: 8 },
  budgetCurrency:{ fontSize: 18, fontWeight: '700', color: COLORS.textDark },
  budgetInput:  { flex: 1, backgroundColor: COLORS.bg, borderRadius: 10, padding: 10, fontSize: 16, fontFamily: 'serif', color: COLORS.textDark, borderWidth: 1, borderColor: COLORS.border },
  saveBtn:      { backgroundColor: COLORS.navy, borderRadius: 10, paddingVertical: 10, paddingHorizontal: 16 },
  saveBtnText:  { color: '#fff', fontWeight: '700', fontSize: 13 },
  exportBtn:    { padding: 12, backgroundColor: COLORS.navy + '18', borderRadius: 10, borderWidth: 1, borderColor: COLORS.navy + '44', alignItems: 'center', marginBottom: 8 },
  exportText:   { fontSize: 13, fontWeight: '700', color: COLORS.navy },
  clearBtn:     { padding: 12, backgroundColor: COLORS.terracotta + '18', borderRadius: 10, borderWidth: 1, borderColor: COLORS.terracotta + '44', alignItems: 'center' },
  clearText:    { fontSize: 13, fontWeight: '700', color: COLORS.terracotta },
  infoCard:     { backgroundColor: COLORS.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: COLORS.border },
  infoText:     { fontSize: 12, color: COLORS.sage, lineHeight: 18 },
});
