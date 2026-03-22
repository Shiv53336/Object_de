import 'package:flutter/material.dart';
import '../models/expense_category.dart';

// ─── Colors ────────────────────────────────────────────────────────────────

const Color kBackground   = Color(0xFFFAF6F1);
const Color kNavy         = Color(0xFF3D405B);
const Color kTerracotta   = Color(0xFFE07A5F);
const Color kSage         = Color(0xFF81B29A);
const Color kGold         = Color(0xFFF2CC8F);
const Color kPurple       = Color(0xFF7B68EE);
const Color kText         = Color(0xFF2D2A26);
const Color kSubtext      = Color(0xFF8B8580);
const Color kBorder       = Color(0xFFEDE8E1);
const Color kCard         = Colors.white;
const Color kMuted        = Color(0xFF5A5550);

// ─── Currencies ────────────────────────────────────────────────────────────

const Map<String, String> kCurrencies = {
  '₹': 'INR',
  '\$': 'USD',
  '€': 'EUR',
  '£': 'GBP',
};

// ─── Default Categories ────────────────────────────────────────────────────

final List<ExpenseCategory> kDefaultCategories = [
  ExpenseCategory(name: 'Food & Dining',     emoji: '🍜', color: '#E07A5F', budget: 8000),
  ExpenseCategory(name: 'Transport',         emoji: '🛺', color: '#3D405B', budget: 3000),
  ExpenseCategory(name: 'Shopping',          emoji: '🛍️', color: '#81B29A', budget: 5000),
  ExpenseCategory(name: 'Bills & Utilities', emoji: '💡', color: '#F2CC8F', budget: 6000),
  ExpenseCategory(name: 'Entertainment',     emoji: '🎮', color: '#7B68EE', budget: 2000),
  ExpenseCategory(name: 'Health',            emoji: '💊', color: '#E88D97', budget: 2000),
];

// ─── Default Income Categories ─────────────────────────────────────────────

final List<ExpenseCategory> kDefaultIncomeCategories = [
  ExpenseCategory(name: 'Salary',      emoji: '💼', color: '#81B29A', budget: 0),
  ExpenseCategory(name: 'Freelance',   emoji: '💻', color: '#3D405B', budget: 0),
  ExpenseCategory(name: 'Investment',  emoji: '📈', color: '#F2CC8F', budget: 0),
  ExpenseCategory(name: 'Gift',        emoji: '🎁', color: '#E07A5F', budget: 0),
  ExpenseCategory(name: 'Other Income',emoji: '💰', color: '#7B68EE', budget: 0),
];

// ─── Random Colors ─────────────────────────────────────────────────────────

const List<String> kRandColors = [
  '#E07A5F', '#3D405B', '#81B29A', '#F2CC8F', '#7B68EE',
  '#E88D97', '#6C63FF', '#F4A261', '#2A9D8F', '#E76F51',
];

// ─── Payment Types ─────────────────────────────────────────────────────────

class PaymentType {
  final String label;
  final String icon;
  final Color color;
  const PaymentType({required this.label, required this.icon, required this.color});
}

const List<PaymentType> kPaymentTypes = [
  PaymentType(label: 'UPI',  icon: '📱', color: Color(0xFF6C63FF)),
  PaymentType(label: 'Card', icon: '💳', color: Color(0xFFE07A5F)),
  PaymentType(label: 'Cash', icon: '💵', color: Color(0xFF81B29A)),
];

// ─── Helpers ───────────────────────────────────────────────────────────────

const double kDefaultBudget = 26000;

Color hexToColor(String hex) {
  final buffer = StringBuffer();
  if (hex.length == 6 || hex.length == 7) buffer.write('ff');
  buffer.write(hex.replaceFirst('#', ''));
  return Color(int.parse(buffer.toString(), radix: 16));
}

String todayStr() {
  final now = DateTime.now();
  return '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
}

String dateLabel(String dateStr) {
  final today = todayStr();
  final yesterday = () {
    final d = DateTime.now().subtract(const Duration(days: 1));
    return '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
  }();
  if (dateStr == today) return 'Today';
  if (dateStr == yesterday) return 'Yesterday';
  return dateStr;
}

Color getBudgetColor(double pct) {
  if (pct < 60) return kSage;
  if (pct < 85) return kGold;
  return kTerracotta;
}

Map<String, Color> paymentColor(String p) {
  switch (p) {
    case 'UPI':
      return {'bg': const Color(0xFF6C63FF).withOpacity(0.1), 'fg': const Color(0xFF6C63FF)};
    case 'Card':
      return {'bg': kTerracotta.withOpacity(0.1), 'fg': kTerracotta};
    case 'Cash':
      return {'bg': kSage.withOpacity(0.1), 'fg': kSage};
    default:
      return {'bg': const Color(0xFFEDE8E1), 'fg': kSubtext};
  }
}

String paymentIcon(String p) {
  switch (p) {
    case 'UPI':  return '📱';
    case 'Card': return '💳';
    case 'Cash': return '💵';
    default:     return '💸';
  }
}
