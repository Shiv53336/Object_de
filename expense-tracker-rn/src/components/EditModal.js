import React, { useState } from 'react';
import {
  Modal, View, Text, TextInput, TouchableOpacity,
  ScrollView, StyleSheet, Alert,
} from 'react-native';
import { COLORS, PAYMENT_TYPES } from '../constants';
import { todayStr } from '../utils/helpers';

export default function EditModal({ expense, categories, currency, onSave, onDelete, onClose }) {
  const [amount,  setAmount]  = useState(String(expense.amount));
  const [cat,     setCat]     = useState(expense.category);
  const [note,    setNote]    = useState(expense.note || '');
  const [payment, setPayment] = useState(expense.payment || 'UPI');
  const [date,    setDate]    = useState(expense.date);

  const isIncome    = expense.type === 'income';
  const filteredCats = categories.filter(c => c.type === (isIncome ? 'income' : 'expense'));
  const accentColor  = isIncome ? COLORS.sage : COLORS.terracotta;

  const handleSave = () => {
    const num = parseFloat(amount);
    if (!num || num <= 0) { Alert.alert('Invalid amount'); return; }
    const catObj = categories.find(c => c.name === cat);
    onSave({ ...expense, amount: num, category: cat, note: note || cat, payment, date, emoji: catObj?.emoji || expense.emoji });
    onClose();
  };

  const handleDelete = () => {
    Alert.alert('Delete entry', 'Are you sure?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => { onDelete(expense.id); onClose(); } },
    ]);
  };

  return (
    <Modal visible animationType="slide" transparent onRequestClose={onClose}>
      <TouchableOpacity style={s.backdrop} activeOpacity={1} onPress={onClose} />
      <View style={s.sheet}>
        {/* Header */}
        <View style={s.header}>
          <Text style={s.headerTitle}>{isIncome ? '✏️ Edit Income' : '✏️ Edit Expense'}</Text>
          <TouchableOpacity onPress={onClose} style={s.closeBtn}>
            <Text style={s.closeText}>✕</Text>
          </TouchableOpacity>
        </View>

        <ScrollView showsVerticalScrollIndicator={false}>
          {/* Amount */}
          <View style={[s.amountRow, { borderColor: accentColor + '66' }]}>
            <Text style={[s.currencySign, { color: accentColor }]}>{currency}</Text>
            <TextInput
              value={amount}
              onChangeText={setAmount}
              keyboardType="decimal-pad"
              style={s.amountInput}
              placeholder="0"
            />
          </View>

          {/* Category picker */}
          <Text style={s.label}>Category</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.catRow}>
            {filteredCats.map(c => (
              <TouchableOpacity
                key={c.name}
                onPress={() => setCat(c.name)}
                style={[s.catChip, cat === c.name && { backgroundColor: c.color + '22', borderColor: c.color, borderWidth: 2 }]}
              >
                <Text style={s.catEmoji}>{c.emoji}</Text>
                <Text style={[s.catLabel, cat === c.name && { color: c.color, fontWeight: '700' }]}>
                  {c.name.split(' ')[0]}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          {/* Note */}
          <Text style={s.label}>Note</Text>
          <TextInput
            value={note}
            onChangeText={setNote}
            placeholder="Add a note..."
            style={s.noteInput}
            placeholderTextColor={COLORS.textLight}
          />

          {/* Date */}
          <Text style={s.label}>Date</Text>
          <TextInput
            value={date}
            onChangeText={setDate}
            placeholder="YYYY-MM-DD"
            style={s.noteInput}
            placeholderTextColor={COLORS.textLight}
            keyboardType="numeric"
          />

          {/* Payment (expenses only) */}
          {!isIncome && (
            <>
              <Text style={s.label}>Paid via</Text>
              <View style={s.paymentRow}>
                {PAYMENT_TYPES.filter(p => p.label !== 'Other').map(pt => (
                  <TouchableOpacity
                    key={pt.label}
                    onPress={() => setPayment(pt.label)}
                    style={[s.payChip, payment === pt.label && { backgroundColor: pt.color + '22', borderColor: pt.color, borderWidth: 2 }]}
                  >
                    <Text style={s.payIcon}>{pt.icon}</Text>
                    <Text style={[s.payLabel, payment === pt.label && { color: pt.color, fontWeight: '700' }]}>
                      {pt.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </>
          )}

          {/* Buttons */}
          <View style={s.btnRow}>
            <TouchableOpacity style={s.saveBtn} onPress={handleSave}>
              <Text style={s.saveBtnText}>Save Changes</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.deleteBtn} onPress={handleDelete}>
              <Text style={s.deleteBtnText}>Delete</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  backdrop:    { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)' },
  sheet:       { backgroundColor: COLORS.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 20, paddingBottom: 36, maxHeight: '85%' },
  header:      { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  headerTitle: { fontSize: 20, fontFamily: 'serif', fontWeight: '600', color: COLORS.textDark },
  closeBtn:    { padding: 4 },
  closeText:   { fontSize: 18, color: COLORS.textLight },
  amountRow:   { flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.card, borderRadius: 12, padding: 14, marginBottom: 14, borderWidth: 1.5 },
  currencySign:{ fontSize: 20, marginRight: 6, fontWeight: '600' },
  amountInput: { flex: 1, fontSize: 28, fontFamily: 'serif', fontWeight: '700', color: COLORS.textDark },
  label:       { fontSize: 12, fontWeight: '600', color: COLORS.textMid, marginBottom: 6, letterSpacing: 0.3 },
  catRow:      { flexDirection: 'row', marginBottom: 14 },
  catChip:     { alignItems: 'center', backgroundColor: COLORS.card, borderRadius: 10, padding: 10, marginRight: 8, borderWidth: 1, borderColor: COLORS.border, minWidth: 64 },
  catEmoji:    { fontSize: 20, marginBottom: 2 },
  catLabel:    { fontSize: 11, color: COLORS.textMid },
  noteInput:   { backgroundColor: COLORS.card, borderRadius: 10, padding: 12, fontFamily: 'sans-serif', fontSize: 14, color: COLORS.textDark, borderWidth: 1, borderColor: COLORS.border, marginBottom: 14 },
  paymentRow:  { flexDirection: 'row', gap: 8, marginBottom: 20 },
  payChip:     { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: COLORS.card, borderRadius: 20, paddingVertical: 6, paddingHorizontal: 12, borderWidth: 1, borderColor: COLORS.border },
  payIcon:     { fontSize: 14 },
  payLabel:    { fontSize: 12, color: COLORS.textLight },
  btnRow:      { flexDirection: 'row', gap: 10, marginBottom: 8 },
  saveBtn:     { flex: 1, backgroundColor: COLORS.navy, borderRadius: 12, padding: 14, alignItems: 'center' },
  saveBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
  deleteBtn:   { backgroundColor: COLORS.terracotta + '18', borderRadius: 12, padding: 14, paddingHorizontal: 18, borderWidth: 1, borderColor: COLORS.terracotta + '55' },
  deleteBtnText: { color: COLORS.terracotta, fontWeight: '700', fontSize: 14 },
});
