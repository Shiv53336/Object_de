import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/recurring_expense.dart';
import '../providers/app_provider.dart';
import '../utils/constants.dart';

class RecurringScreen extends StatelessWidget {
  const RecurringScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final provider  = context.watch<AppProvider>();
    final recurring = provider.recurring;

    return SingleChildScrollView(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('🔄 Recurring',
                style: TextStyle(fontSize: 22, color: kText, fontStyle: FontStyle.italic)),
            const SizedBox(height: 4),
            const Text('Auto-add expenses and income on schedule',
                style: TextStyle(fontSize: 12, color: kSubtext)),
            const SizedBox(height: 16),

            // Add new button
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: () => _showAddRecurringModal(context, provider),
                style: ElevatedButton.styleFrom(
                  backgroundColor: kNavy,
                  foregroundColor: kBackground,
                  elevation: 0,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                icon: const Icon(Icons.add, size: 18),
                label: const Text('Add Recurring Entry', style: TextStyle(fontWeight: FontWeight.w600)),
              ),
            ),
            const SizedBox(height: 16),

            if (recurring.isEmpty)
              Container(
                padding: const EdgeInsets.all(32),
                alignment: Alignment.center,
                child: const Text(
                  'No recurring entries yet.\nAdd rent, subscriptions, salary, etc.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 14, color: kSubtext),
                ),
              )
            else
              ...recurring.map((r) => _RecurringCard(item: r)),
          ],
        ),
      ),
    );
  }

  void _showAddRecurringModal(BuildContext context, AppProvider provider) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _AddRecurringModal(provider: provider),
    );
  }
}

class _RecurringCard extends StatelessWidget {
  final RecurringExpense item;
  const _RecurringCard({required this.item});

  String _fmt(double v) => v.toStringAsFixed(0).replaceAllMapped(
      RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'), (m) => '${m[1]},');

  @override
  Widget build(BuildContext context) {
    final provider   = context.read<AppProvider>();
    final currency   = provider.currency;
    final isIncome   = item.type == 'income';
    final typeColor  = isIncome ? kSage : kTerracotta;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: kCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: item.active ? kBorder : kBorder.withOpacity(0.5)),
        boxShadow: const [BoxShadow(color: Color(0x0A2D2A26), blurRadius: 4)],
      ),
      child: Row(
        children: [
          // Emoji
          Container(
            width: 42, height: 42,
            decoration: BoxDecoration(
              color: typeColor.withOpacity(0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            alignment: Alignment.center,
            child: Text(item.emoji, style: const TextStyle(fontSize: 20)),
          ),
          const SizedBox(width: 12),

          // Details
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(item.note,
                    style: TextStyle(
                      fontSize: 14, fontWeight: FontWeight.w600,
                      color: item.active ? kText : kSubtext,
                    )),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Text('${item.category} • ${_freqLabel(item)}',
                        style: const TextStyle(fontSize: 11, color: kSubtext)),
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                      decoration: BoxDecoration(
                        color: typeColor.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(isIncome ? 'Income' : 'Expense',
                          style: TextStyle(fontSize: 9, color: typeColor, fontWeight: FontWeight.w600)),
                    ),
                  ],
                ),
              ],
            ),
          ),

          // Amount
          Text(
            '$currency${_fmt(item.amount)}',
            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: typeColor),
          ),
          const SizedBox(width: 8),

          // Toggle active
          Column(
            children: [
              Switch(
                value: item.active,
                onChanged: (v) => provider.updateRecurring(item.copyWith(active: v)),
                activeColor: kNavy,
                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
              GestureDetector(
                onTap: () => showDialog(
                  context: context,
                  builder: (_) => AlertDialog(
                    title: const Text('Delete Recurring?'),
                    content: const Text('This will stop auto-adding this entry.'),
                    actions: [
                      TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
                      TextButton(
                        onPressed: () { Navigator.pop(context); provider.deleteRecurring(item.id); },
                        child: const Text('Delete', style: TextStyle(color: Colors.red)),
                      ),
                    ],
                  ),
                ),
                child: const Text('Delete', style: TextStyle(fontSize: 10, color: kTerracotta)),
              ),
            ],
          ),
        ],
      ),
    );
  }

  String _freqLabel(RecurringExpense r) {
    switch (r.frequency) {
      case 'daily':   return 'Daily';
      case 'weekly':  return 'Weekly (Mon)';
      case 'monthly': return 'Monthly (day ${r.dayOfMonth})';
      case 'yearly':  return 'Yearly';
      default:        return r.frequency;
    }
  }
}

class _AddRecurringModal extends StatefulWidget {
  final AppProvider provider;
  const _AddRecurringModal({required this.provider});

  @override
  State<_AddRecurringModal> createState() => _AddRecurringModalState();
}

class _AddRecurringModalState extends State<_AddRecurringModal> {
  final _amountCtrl = TextEditingController();
  final _noteCtrl   = TextEditingController();
  String _type      = 'expense';
  String _frequency = 'monthly';
  int _dayOfMonth   = 1;
  String _payment   = 'UPI';
  String? _cat;

  static const _incomeCategories = ['Salary', 'Freelance', 'Investment', 'Gift', 'Other Income'];

  @override
  void dispose() {
    _amountCtrl.dispose();
    _noteCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isIncome  = _type == 'income';
    final typeColor = isIncome ? kSage : kTerracotta;
    final cats = isIncome
        ? kDefaultIncomeCategories
        : widget.provider.categories.where((c) => !_incomeCategories.contains(c.name)).toList();
    _cat ??= cats.isNotEmpty ? cats.first.name : null;

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        decoration: const BoxDecoration(
          color: kCard,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40, height: 4,
                decoration: BoxDecoration(color: kBorder, borderRadius: BorderRadius.circular(2)),
              ),
            ),
            const SizedBox(height: 16),
            const Text('New Recurring Entry',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: kText)),
            const SizedBox(height: 16),

            // Type toggle
            Row(
              children: [
                _ToggleBtn(label: '− Expense', active: _type == 'expense', color: kTerracotta,
                    onTap: () => setState(() { _type = 'expense'; _cat = null; })),
                const SizedBox(width: 8),
                _ToggleBtn(label: '+ Income', active: _type == 'income', color: kSage,
                    onTap: () => setState(() { _type = 'income'; _cat = null; })),
              ],
            ),
            const SizedBox(height: 12),

            // Amount + Category row
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _amountCtrl,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: typeColor),
                    decoration: InputDecoration(
                      prefixText: widget.provider.currency,
                      prefixStyle: const TextStyle(fontSize: 14, color: kSubtext),
                      hintText: '0',
                      filled: true, fillColor: kBackground,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: kBorder)),
                      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: kBorder)),
                      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: typeColor)),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
                  decoration: BoxDecoration(color: kBackground, borderRadius: BorderRadius.circular(10), border: Border.all(color: kBorder)),
                  child: DropdownButtonHideUnderline(
                    child: DropdownButton<String>(
                      value: _cat,
                      isDense: true,
                      style: const TextStyle(fontSize: 13, color: kText, fontFamily: 'sans-serif'),
                      items: cats.map((c) => DropdownMenuItem(value: c.name, child: Text('${c.emoji} ${c.name.split(' ').first}'))).toList(),
                      onChanged: (v) => setState(() => _cat = v),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),

            // Note
            TextField(
              controller: _noteCtrl,
              style: const TextStyle(fontSize: 13, color: kText),
              decoration: InputDecoration(
                hintText: 'e.g. Rent, Netflix, Salary...',
                hintStyle: const TextStyle(color: kSubtext, fontSize: 13),
                filled: true, fillColor: kBackground,
                contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: kBorder)),
                enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: kBorder)),
                focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: typeColor)),
              ),
            ),
            const SizedBox(height: 10),

            // Frequency
            Row(
              children: [
                const Text('Repeat:', style: TextStyle(fontSize: 12, color: kSubtext)),
                const SizedBox(width: 8),
                ...['daily', 'weekly', 'monthly', 'yearly'].map((f) => Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: _ToggleBtn(
                    label: f[0].toUpperCase() + f.substring(1),
                    active: _frequency == f,
                    color: kNavy,
                    onTap: () => setState(() => _frequency = f),
                  ),
                )),
              ],
            ),

            if (_frequency == 'monthly') ...[
              const SizedBox(height: 10),
              Row(
                children: [
                  const Text('Day of month:', style: TextStyle(fontSize: 12, color: kSubtext)),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(color: kBackground, borderRadius: BorderRadius.circular(8), border: Border.all(color: kBorder)),
                    child: DropdownButtonHideUnderline(
                      child: DropdownButton<int>(
                        value: _dayOfMonth,
                        isDense: true,
                        style: const TextStyle(fontSize: 13, color: kText),
                        items: List.generate(28, (i) => i + 1).map((d) => DropdownMenuItem(value: d, child: Text('$d'))).toList(),
                        onChanged: (v) => setState(() => _dayOfMonth = v!),
                      ),
                    ),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 16),

            // Save
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () {
                  final amount = double.tryParse(_amountCtrl.text);
                  if (amount == null || amount <= 0 || _cat == null) return;

                  final allCats = [...widget.provider.categories, ...kDefaultIncomeCategories];
                  final catObj  = allCats.firstWhere((c) => c.name == _cat!, orElse: () => allCats.first);

                  widget.provider.addRecurring(RecurringExpense(
                    id:         DateTime.now().millisecondsSinceEpoch,
                    amount:     amount,
                    category:   _cat!,
                    note:       _noteCtrl.text.isNotEmpty ? _noteCtrl.text : _cat!,
                    emoji:      catObj.emoji,
                    payment:    _payment,
                    type:       _type,
                    frequency:  _frequency,
                    dayOfMonth: _dayOfMonth,
                  ));
                  Navigator.pop(context);
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: typeColor,
                  foregroundColor: Colors.white,
                  elevation: 0,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: const Text('Add Recurring Entry', style: TextStyle(fontWeight: FontWeight.w600)),
              ),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}

class _ToggleBtn extends StatelessWidget {
  final String label;
  final bool active;
  final Color color;
  final VoidCallback onTap;
  const _ToggleBtn({required this.label, required this.active, required this.color, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: active ? color : kBackground,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: active ? color : kBorder),
        ),
        child: Text(label,
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600,
                color: active ? Colors.white : kSubtext)),
      ),
    );
  }
}
