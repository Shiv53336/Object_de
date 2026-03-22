import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/expense.dart';
import '../providers/app_provider.dart';
import '../utils/constants.dart';

void showEditExpenseModal(BuildContext context, Expense expense) {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _EditExpenseModal(expense: expense),
  );
}

class _EditExpenseModal extends StatefulWidget {
  final Expense expense;
  const _EditExpenseModal({required this.expense});

  @override
  State<_EditExpenseModal> createState() => _EditExpenseModalState();
}

class _EditExpenseModalState extends State<_EditExpenseModal> {
  late TextEditingController _amountCtrl;
  late TextEditingController _noteCtrl;
  late String _selectedCat;
  late String _selectedPayment;
  late String _type;
  String _customPay = '';

  static const _incomeCategories = ['Salary', 'Freelance', 'Investment', 'Gift', 'Other Income'];

  @override
  void initState() {
    super.initState();
    _amountCtrl      = TextEditingController(text: widget.expense.amount.toStringAsFixed(0));
    _noteCtrl        = TextEditingController(text: widget.expense.note);
    _selectedCat     = widget.expense.category;
    _selectedPayment = kPaymentTypes.any((p) => p.label == widget.expense.payment)
        ? widget.expense.payment
        : 'Other';
    _customPay       = kPaymentTypes.any((p) => p.label == widget.expense.payment)
        ? ''
        : widget.expense.payment;
    _type            = widget.expense.type;
  }

  @override
  void dispose() {
    _amountCtrl.dispose();
    _noteCtrl.dispose();
    super.dispose();
  }

  void _handleSave(AppProvider provider) {
    final amount = double.tryParse(_amountCtrl.text);
    if (amount == null || amount <= 0) return;

    final payment = _selectedPayment == 'Other'
        ? (_customPay.isNotEmpty ? _customPay : 'Other')
        : _selectedPayment;

    final allCats = [...provider.categories, ...kDefaultIncomeCategories];
    final catObj = allCats.firstWhere(
      (c) => c.name == _selectedCat,
      orElse: () => provider.categories.first,
    );

    provider.updateExpense(widget.expense.copyWith(
      amount:   amount,
      category: _selectedCat,
      note:     _noteCtrl.text.isNotEmpty ? _noteCtrl.text : _selectedCat,
      payment:  payment,
      emoji:    catObj.emoji,
      type:     _type,
    ));

    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    final provider  = context.watch<AppProvider>();
    final isIncome  = _type == 'income';
    final typeColor = isIncome ? kSage : kTerracotta;

    final cats = isIncome
        ? kDefaultIncomeCategories
        : provider.categories.where((c) => !_incomeCategories.contains(c.name)).toList();

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
            // Handle
            Center(
              child: Container(
                width: 40, height: 4,
                decoration: BoxDecoration(color: kBorder, borderRadius: BorderRadius.circular(2)),
              ),
            ),
            const SizedBox(height: 16),

            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Edit Entry',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: kText)),
                // Type toggle
                _TypeToggle(
                  value: _type,
                  onChanged: (v) => setState(() {
                    _type = v;
                    final newCats = v == 'income'
                        ? kDefaultIncomeCategories
                        : provider.categories.where((c) => !_incomeCategories.contains(c.name)).toList();
                    _selectedCat = newCats.isNotEmpty ? newCats.first.name : _selectedCat;
                  }),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Amount
            TextField(
              controller: _amountCtrl,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              autofocus: true,
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: typeColor),
              decoration: InputDecoration(
                prefixText: provider.currency,
                prefixStyle: const TextStyle(fontSize: 18, color: kSubtext),
                hintText: '0',
                filled: true,
                fillColor: kBackground,
                contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: typeColor)),
                enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: kBorder)),
                focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: typeColor, width: 2)),
              ),
            ),
            const SizedBox(height: 10),

            // Category
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              decoration: BoxDecoration(
                color: kBackground,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: kBorder),
              ),
              child: DropdownButtonHideUnderline(
                child: DropdownButton<String>(
                  value: cats.any((c) => c.name == _selectedCat) ? _selectedCat : cats.first.name,
                  isExpanded: true,
                  style: const TextStyle(fontSize: 14, color: kText, fontFamily: 'sans-serif'),
                  items: cats.map((c) => DropdownMenuItem(
                    value: c.name,
                    child: Text('${c.emoji} ${c.name}'),
                  )).toList(),
                  onChanged: (v) => setState(() => _selectedCat = v!),
                ),
              ),
            ),
            const SizedBox(height: 10),

            // Note
            TextField(
              controller: _noteCtrl,
              style: const TextStyle(fontSize: 14, color: kText),
              decoration: InputDecoration(
                hintText: 'Note...',
                hintStyle: const TextStyle(color: kSubtext),
                filled: true,
                fillColor: kBackground,
                contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: kBorder)),
                enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: kBorder)),
                focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: typeColor)),
              ),
            ),
            const SizedBox(height: 10),

            // Payment
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                const Text('Paid via:', style: TextStyle(fontSize: 12, color: kSubtext)),
                ...kPaymentTypes.map((pt) => _PayChip(
                  label: '${pt.icon} ${pt.label}',
                  selected: _selectedPayment == pt.label,
                  color: pt.color,
                  onTap: () => setState(() { _selectedPayment = pt.label; _customPay = ''; }),
                )),
                _PayChip(
                  label: '✍️ Other',
                  selected: _selectedPayment == 'Other',
                  color: kNavy,
                  onTap: () => setState(() => _selectedPayment = 'Other'),
                ),
                if (_selectedPayment == 'Other')
                  SizedBox(
                    width: 140,
                    child: TextField(
                      initialValue: _customPay,
                      style: const TextStyle(fontSize: 12),
                      decoration: const InputDecoration(
                        hintText: 'e.g. Wallet...',
                        isDense: true,
                        contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      ),
                      onChanged: (v) => _customPay = v,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 16),

            // Actions
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () {
                      showDialog(
                        context: context,
                        builder: (_) => AlertDialog(
                          title: const Text('Delete Entry?'),
                          content: const Text('This cannot be undone.'),
                          actions: [
                            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
                            TextButton(
                              onPressed: () {
                                Navigator.pop(context);
                                context.read<AppProvider>().deleteExpense(widget.expense.id);
                                Navigator.pop(context);
                              },
                              child: const Text('Delete', style: TextStyle(color: Colors.red)),
                            ),
                          ],
                        ),
                      );
                    },
                    style: OutlinedButton.styleFrom(
                      foregroundColor: kTerracotta,
                      side: const BorderSide(color: kTerracotta),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    child: const Text('Delete', style: TextStyle(fontWeight: FontWeight.w600)),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  flex: 2,
                  child: ElevatedButton(
                    onPressed: () => _handleSave(provider),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: typeColor,
                      foregroundColor: Colors.white,
                      elevation: 0,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    child: const Text('Save Changes', style: TextStyle(fontWeight: FontWeight.w600)),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}

class _TypeToggle extends StatelessWidget {
  final String value;
  final ValueChanged<String> onChanged;
  const _TypeToggle({required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: kBackground,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: kBorder),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _Btn(label: '− Exp', active: value == 'expense', color: kTerracotta, onTap: () => onChanged('expense')),
          _Btn(label: '+ Inc', active: value == 'income', color: kSage, onTap: () => onChanged('income')),
        ],
      ),
    );
  }
}

class _Btn extends StatelessWidget {
  final String label;
  final bool active;
  final Color color;
  final VoidCallback onTap;
  const _Btn({required this.label, required this.active, required this.color, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: active ? color : Colors.transparent,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(label, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600,
            color: active ? Colors.white : kSubtext)),
      ),
    );
  }
}

class _PayChip extends StatelessWidget {
  final String label;
  final bool selected;
  final Color color;
  final VoidCallback onTap;
  const _PayChip({required this.label, required this.selected, required this.color, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: selected ? color.withOpacity(0.08) : kBackground,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: selected ? color : kBorder, width: selected ? 2 : 1),
        ),
        child: Text(label,
            style: TextStyle(fontSize: 11, fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                color: selected ? color : kSubtext)),
      ),
    );
  }
}
