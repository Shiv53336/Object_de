import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView, StyleSheet, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useApp } from '../context/AppContext';
import { COLORS, PAYMENT_TYPES, FREQ_LABELS } from '../constants';

export default function RecurringScreen() {
  const { currency, categories, recurring, addRecurring, toggleRecurring, deleteRecurring } = useApp();
  const [showForm,   setShowForm]   = useState(false);
  const [amount,     setAmount]     = useState('');
  const [cat,        setCat]        = useState('');
  const [note,       setNote]       = useState('');
  const [payment,    setPayment]    = useState('UPI');
  const [freq,       setFreq]       = useState('monthly');
  const [dayOfMonth, setDayOfMonth] = useState('1');

  const expCats = categories.filter(c => c.type !== 'income');
  const activeCat = cat || expCats[0]?.name || '';

  const handleAdd = () => {
    const num = parseFloat(amount);
    if (!num || num <= 0) { Alert.alert('Enter a valid amount'); return; }
    if (!activeCat)       { Alert.alert('Select a category'); return; }
    const catObj = categories.find(c => c.name === activeCat);
    addRecurring({
      id:        Date.now(),
      amount:    num,
      category:  activeCat,
      note:      note || activeCat,
      emoji:     catObj?.emoji || '💸',
      payment,
      type:      'expense',
      frequency: freq,
      dayOfMonth: parseInt(dayOfMonth) || 1,
      lastAdded: null,
      active:    true,
    });
    setAmount(''); setNote(''); setShowForm(false);
  };

  const handleDelete = (id, name) => {
    Alert.alert(`Delete "${name}"?`, 'This cannot be undone.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => deleteRecurring(id) },
    ]);
  };

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      <View style={s.topRow}>
        <Text style={s.heading}>🔄  Recurring</Text>
        <TouchableOpacity style={s.addBtn} onPress={() => setShowForm(!showForm)}>
          <Text style={s.addBtnText}>+ Add</Text>
        </TouchableOpacity>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 32 }}>
        {/* Add form */}
        {showForm && (
          <View style={s.form}>
            <Text style={s.formTitle}>New Recurring Expense</Text>

            {/* Amount */}
            <View style={s.amountRow}>
              <Text style={s.currencySign}>{currency}</Text>
              <TextInput
                value={amount} onChangeText={setAmount}
                keyboardType="decimal-pad" placeholder="0"
                placeholderTextColor={COLORS.textLight}
                style={s.amountInput}
              />
            </View>

            {/* Note */}
            <TextInput
              value={note} onChangeText={setNote}
              placeholder="Description (e.g. Rent, Netflix, Gym)"
              placeholderTextColor={COLORS.textLight}
              style={s.textInput}
            />

            {/* Category */}
            <Text style={s.label}>Category</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
              {expCats.map(c => (
                <TouchableOpacity
                  key={c.name} onPress={() => setCat(c.name)}
                  style={[s.catChip, activeCat === c.name && { backgroundColor: c.color + '22', borderColor: c.color, borderWidth: 2 }]}
                >
                  <Text style={s.catEmoji}>{c.emoji}</Text>
                  <Text style={[s.catName, activeCat === c.name && { color: c.color, fontWeight: '700' }]}>{c.name.split(' ')[0]}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            {/* Frequency */}
            <Text style={s.label}>Frequency</Text>
            <View style={s.freqRow}>
              {Object.entries(FREQ_LABELS).map(([k, v]) => (
                <TouchableOpacity
                  key={k} onPress={() => setFreq(k)}
                  style={[s.freqChip, freq === k && { backgroundColor: COLORS.navy, borderColor: COLORS.navy }]}
                >
                  <Text style={[s.freqText, freq === k && { color: '#fff', fontWeight: '700' }]}>{v}</Text>
                </TouchableOpacity>
              ))}
            </View>

            {freq === 'monthly' && (
              <View style={s.dayRow}>
                <Text style={s.dayLabel}>Day of month:</Text>
                <TextInput
                  value={dayOfMonth} onChangeText={setDayOfMonth}
                  keyboardType="number-pad" style={s.dayInput}
                />
              </View>
            )}

            {/* Payment */}
            <Text style={s.label}>Paid via</Text>
            <View style={s.payRow}>
              {PAYMENT_TYPES.filter(p => p.label !== 'Other').map(pt => (
                <TouchableOpacity
                  key={pt.label} onPress={() => setPayment(pt.label)}
                  style={[s.payChip, payment === pt.label && { backgroundColor: pt.color + '14', borderColor: pt.color, borderWidth: 2 }]}
                >
                  <Text style={s.payIcon}>{pt.icon}</Text>
                  <Text style={[s.payText, payment === pt.label && { color: pt.color, fontWeight: '700' }]}>{pt.label}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <TouchableOpacity style={s.saveBtn} onPress={handleAdd}>
              <Text style={s.saveBtnText}>Save Recurring Entry</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* List */}
        {recurring.length === 0 ? (
          <View style={s.emptyBox}>
            <Text style={s.emptyText}>No recurring entries yet.</Text>
            <Text style={s.emptyHint}>Set up rent, EMIs, subscriptions and more!</Text>
          </View>
        ) : (
          <View style={{ paddingHorizontal: 16 }}>
            {recurring.map(r => (
              <View key={r.id} style={s.item}>
                <View style={s.itemEmoji}>
                  <Text style={s.itemEmojiText}>{r.emoji}</Text>
                </View>
                <View style={s.itemInfo}>
                  <Text style={s.itemNote}>{r.note}</Text>
                  <Text style={s.itemMeta}>
                    {currency}{r.amount.toLocaleString()} · {FREQ_LABELS[r.frequency]}
                    {r.frequency === 'monthly' ? ` (day ${r.dayOfMonth})` : ''}
                  </Text>
                </View>
                <TouchableOpacity
                  style={[s.statusBadge, { backgroundColor: r.active ? '#81B29A18' : '#EDE8E1' }]}
                  onPress={() => toggleRecurring(r.id)}
                >
                  <Text style={[s.statusText, { color: r.active ? COLORS.sage : COLORS.textLight }]}>
                    {r.active ? 'Active' : 'Paused'}
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => handleDelete(r.id, r.note)} style={{ padding: 4 }}>
                  <Text style={s.deleteIcon}>✕</Text>
                </TouchableOpacity>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root:       { flex: 1, backgroundColor: COLORS.bg },
  topRow:     { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 20, paddingTop: 16, paddingBottom: 8 },
  heading:    { fontSize: 26, fontFamily: 'serif', fontWeight: '700', color: COLORS.textDark },
  addBtn:     { backgroundColor: COLORS.navy, borderRadius: 10, paddingVertical: 7, paddingHorizontal: 14 },
  addBtnText: { color: '#fff', fontWeight: '700', fontSize: 13 },
  form:       { margin: 16, backgroundColor: COLORS.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: COLORS.border },
  formTitle:  { fontSize: 17, fontFamily: 'serif', color: COLORS.textLight, marginBottom: 12 },
  amountRow:  { flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.bg, borderRadius: 12, padding: 12, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  currencySign:{ fontSize: 18, color: COLORS.terracotta, marginRight: 6, fontWeight: '700' },
  amountInput:{ flex: 1, fontSize: 22, fontFamily: 'serif', fontWeight: '700', color: COLORS.textDark },
  textInput:  { backgroundColor: COLORS.bg, borderRadius: 10, padding: 12, fontSize: 13, color: COLORS.textDark, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 },
  label:      { fontSize: 12, fontWeight: '600', color: COLORS.textMid, marginBottom: 6, letterSpacing: 0.3 },
  catChip:    { alignItems: 'center', backgroundColor: COLORS.bg, borderRadius: 10, padding: 8, marginRight: 8, borderWidth: 1, borderColor: COLORS.border, minWidth: 60 },
  catEmoji:   { fontSize: 18, marginBottom: 2 },
  catName:    { fontSize: 10, color: COLORS.textMid },
  freqRow:    { flexDirection: 'row', gap: 6, marginBottom: 12, flexWrap: 'wrap' },
  freqChip:   { paddingVertical: 6, paddingHorizontal: 12, borderRadius: 20, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.bg },
  freqText:   { fontSize: 12, color: COLORS.textLight },
  dayRow:     { flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
  dayLabel:   { fontSize: 13, color: COLORS.textMid, marginRight: 8 },
  dayInput:   { backgroundColor: COLORS.bg, borderRadius: 8, padding: 8, borderWidth: 1, borderColor: COLORS.border, fontSize: 14, color: COLORS.textDark, width: 60, textAlign: 'center' },
  payRow:     { flexDirection: 'row', gap: 6, marginBottom: 14 },
  payChip:    { flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 20, paddingVertical: 5, paddingHorizontal: 10, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.bg },
  payIcon:    { fontSize: 13 },
  payText:    { fontSize: 11, color: COLORS.textLight },
  saveBtn:    { backgroundColor: COLORS.navy, borderRadius: 10, padding: 13, alignItems: 'center' },
  saveBtnText:{ color: '#fff', fontWeight: '700', fontSize: 14 },
  emptyBox:   { margin: 16, backgroundColor: COLORS.card, borderRadius: 16, padding: 32, alignItems: 'center', borderWidth: 1, borderColor: COLORS.border },
  emptyText:  { fontSize: 15, color: COLORS.textMid, fontWeight: '600', marginBottom: 6 },
  emptyHint:  { fontSize: 13, color: COLORS.textLight, textAlign: 'center' },
  item:       { flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.card, borderRadius: 12, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  itemEmoji:  { width: 38, height: 38, borderRadius: 10, backgroundColor: COLORS.bg, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  itemEmojiText:{ fontSize: 18 },
  itemInfo:   { flex: 1 },
  itemNote:   { fontSize: 13, fontWeight: '600', color: COLORS.textDark },
  itemMeta:   { fontSize: 11, color: COLORS.textLight, marginTop: 2 },
  statusBadge:{ borderRadius: 16, paddingVertical: 4, paddingHorizontal: 10, marginRight: 6 },
  statusText: { fontSize: 11, fontWeight: '700' },
  deleteIcon: { fontSize: 14, color: COLORS.textFaint },
});
