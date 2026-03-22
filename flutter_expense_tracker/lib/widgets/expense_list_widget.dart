import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_provider.dart';
import '../models/expense.dart';
import '../utils/constants.dart';

class ExpenseListWidget extends StatelessWidget {
  const ExpenseListWidget({super.key});

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<AppProvider>();
    final expenses = List<Expense>.from(provider.expenses)
      ..sort((a, b) {
        final d = b.date.compareTo(a.date);
        return d != 0 ? d : b.id.compareTo(a.id);
      });

    if (expenses.isEmpty) {
      return Container(
        margin: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        padding: const EdgeInsets.all(32),
        alignment: Alignment.center,
        child: const Text(
          'No expenses yet.\nAdd your first one above! 👆',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 14, color: kSubtext),
        ),
      );
    }

    // Group by date label
    final Map<String, List<Expense>> grouped = {};
    for (final exp in expenses) {
      final label = dateLabel(exp.date);
      grouped.putIfAbsent(label, () => []).add(exp);
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 0, 16, 10),
          child: Text('📝 Recent Entries', style: TextStyle(fontSize: 18, color: kSubtext, fontStyle: FontStyle.italic)),
        ),
        ...grouped.entries.map((entry) => _DateGroup(
          label: entry.key,
          expenses: entry.value,
          currency: provider.currency,
          onDelete: provider.deleteExpense,
        )),
      ],
    );
  }
}

class _DateGroup extends StatelessWidget {
  final String label;
  final List<Expense> expenses;
  final String currency;
  final void Function(int id) onDelete;

  const _DateGroup({
    required this.label,
    required this.expenses,
    required this.currency,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label.toUpperCase(),
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: kSubtext, letterSpacing: 0.5),
          ),
          const SizedBox(height: 6),
          ...expenses.map((exp) => _ExpenseCard(exp: exp, currency: currency, onDelete: onDelete)),
        ],
      ),
    );
  }
}

class _ExpenseCard extends StatelessWidget {
  final Expense exp;
  final String currency;
  final void Function(int id) onDelete;

  const _ExpenseCard({required this.exp, required this.currency, required this.onDelete});

  String _fmt(double v) => v.toStringAsFixed(0).replaceAllMapped(
      RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'), (m) => '${m[1]},');

  @override
  Widget build(BuildContext context) {
    final pc = paymentColor(exp.payment);
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: kCard,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: kBorder),
        boxShadow: const [BoxShadow(color: Color(0x0A2D2A26), blurRadius: 4, offset: Offset(0, 1))],
      ),
      child: Row(
        children: [
          // Emoji box
          Container(
            width: 38, height: 38,
            decoration: BoxDecoration(color: kBackground, borderRadius: BorderRadius.circular(10)),
            alignment: Alignment.center,
            child: Text(exp.emoji, style: const TextStyle(fontSize: 18)),
          ),
          const SizedBox(width: 12),
          // Note + category + payment
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  exp.note,
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: kText),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 3),
                Row(
                  children: [
                    Text(exp.category, style: const TextStyle(fontSize: 11, color: kSubtext)),
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                      decoration: BoxDecoration(
                        color: pc['bg'],
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        '${paymentIcon(exp.payment)} ${exp.payment}',
                        style: TextStyle(fontSize: 9, fontWeight: FontWeight.w600, color: pc['fg']),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          // Amount
          Text(
            '−$currency${_fmt(exp.amount)}',
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: kTerracotta),
          ),
          const SizedBox(width: 4),
          // Delete
          IconButton(
            icon: const Icon(Icons.close, size: 14, color: kBorder),
            padding: const EdgeInsets.all(4),
            constraints: const BoxConstraints(),
            onPressed: () => onDelete(exp.id),
          ),
        ],
      ),
    );
  }
}
