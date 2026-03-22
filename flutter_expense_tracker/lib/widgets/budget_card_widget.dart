import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_provider.dart';
import '../utils/constants.dart';

class BudgetCardWidget extends StatelessWidget {
  const BudgetCardWidget({super.key});

  @override
  Widget build(BuildContext context) {
    final provider    = context.watch<AppProvider>();
    final currency    = provider.currency;
    final totalSpent  = provider.totalSpent;
    final totalIncome = provider.totalIncome;
    final netBalance  = provider.netBalance;
    final totalBudget = provider.totalBudget;
    final remaining   = totalBudget - totalSpent;
    final pct         = (totalSpent / totalBudget * 100).clamp(0, 100);
    final color       = getBudgetColor(pct.toDouble());
    final now         = DateTime.now();
    final daysInMonth = DateTime(now.year, now.month + 1, 0).day;
    final daysLeft    = daysInMonth - now.day;

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      decoration: BoxDecoration(
        color: kCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: kBorder),
        boxShadow: const [BoxShadow(color: Color(0x0F2D2A26), blurRadius: 12, offset: Offset(0, 2))],
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('📊 Monthly Budget',
                  style: TextStyle(fontSize: 18, color: kSubtext, fontStyle: FontStyle.italic)),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  '${pct.round()}% used',
                  style: TextStyle(fontSize: 12, color: color, fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),

          // Income / Expense / Net row
          if (totalIncome > 0) ...[
            Row(
              children: [
                _StatPill(label: 'Income', value: '$currency${_fmt(totalIncome)}', color: kSage),
                const SizedBox(width: 8),
                _StatPill(label: 'Spent', value: '$currency${_fmt(totalSpent)}', color: kTerracotta),
                const SizedBox(width: 8),
                _StatPill(
                  label: 'Net',
                  value: '${netBalance >= 0 ? '+' : ''}$currency${_fmt(netBalance.abs())}',
                  color: netBalance >= 0 ? kSage : kTerracotta,
                ),
              ],
            ),
            const SizedBox(height: 10),
          ],

          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '$currency${_fmt(totalSpent)}',
                style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w700, color: kText),
              ),
              Text(
                'of $currency${_fmt(totalBudget)}',
                style: const TextStyle(fontSize: 13, color: kSubtext),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: LinearProgressIndicator(
              value: pct / 100,
              minHeight: 10,
              backgroundColor: kBorder,
              valueColor: AlwaysStoppedAnimation<Color>(color),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            remaining >= 0
                ? '💰 $currency${_fmt(remaining)} remaining • $daysLeft days left'
                : '⚠️ Over budget by $currency${_fmt(remaining.abs())} • $daysLeft days left',
            style: TextStyle(
              fontSize: 12,
              color: remaining >= 0 ? kSage : kTerracotta,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  String _fmt(double v) => v.abs().toStringAsFixed(0).replaceAllMapped(
      RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'), (m) => '${m[1]},');
}

class _StatPill extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _StatPill({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
        decoration: BoxDecoration(
          color: color.withOpacity(0.08),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withOpacity(0.2)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: TextStyle(fontSize: 10, color: color, fontWeight: FontWeight.w500)),
            const SizedBox(height: 2),
            Text(value,
                style: TextStyle(fontSize: 13, color: color, fontWeight: FontWeight.w700),
                overflow: TextOverflow.ellipsis),
          ],
        ),
      ),
    );
  }
}
