import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_provider.dart';
import '../utils/constants.dart';

class QuickAddWidget extends StatefulWidget {
  const QuickAddWidget({super.key});

  @override
  State<QuickAddWidget> createState() => _QuickAddWidgetState();
}

class _QuickAddWidgetState extends State<QuickAddWidget> {
  final _amountController = TextEditingController();
  final _noteController   = TextEditingController();
  String _selectedPayment = 'UPI';
  String _customPay       = '';
  String? _selectedCat;

  @override
  void dispose() {
    _amountController.dispose();
    _noteController.dispose();
    super.dispose();
  }

  void _handleAdd(AppProvider provider) {
    final amount = double.tryParse(_amountController.text);
    if (amount == null || amount <= 0) return;
    final cat     = _selectedCat ?? provider.categories.first.name;
    final payment = _selectedPayment == 'Other'
        ? (_customPay.isNotEmpty ? _customPay : 'Other')
        : _selectedPayment;

    provider.addExpense(provider.buildExpense(
      amount:   amount,
      category: cat,
      note:     _noteController.text,
      payment:  payment,
    ));

    _amountController.clear();
    _noteController.clear();
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<AppProvider>();
    final currency = provider.currency;
    final cats     = provider.categories;

    _selectedCat ??= cats.isNotEmpty ? cats.first.name : null;

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
          const Text('✏️ Quick Entry', style: TextStyle(fontSize: 18, color: kSubtext, fontStyle: FontStyle.italic)),
          const SizedBox(height: 12),

          // Amount + Category + Add
          Row(
            children: [
              Expanded(
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  decoration: BoxDecoration(
                    color: kBackground,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: kBorder),
                  ),
                  child: Row(
                    children: [
                      Text(currency, style: const TextStyle(fontSize: 18, color: kSubtext)),
                      const SizedBox(width: 6),
                      Expanded(
                        child: TextField(
                          controller: _amountController,
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: kText),
                          decoration: const InputDecoration(
                            hintText: '0',
                            hintStyle: TextStyle(color: kSubtext),
                            isDense: true,
                            border: InputBorder.none,
                            contentPadding: EdgeInsets.zero,
                          ),
                          onSubmitted: (_) => _handleAdd(provider),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 8),
              // Category dropdown
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
                decoration: BoxDecoration(
                  color: kBackground,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: kBorder),
                ),
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<String>(
                    value: _selectedCat,
                    isDense: true,
                    style: const TextStyle(fontSize: 13, color: kText, fontFamily: 'sans-serif'),
                    items: cats.map((c) => DropdownMenuItem(
                      value: c.name,
                      child: Text('${c.emoji} ${c.name.split(' ').first}'),
                    )).toList(),
                    onChanged: (v) => setState(() => _selectedCat = v),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              // Add button
              ElevatedButton(
                onPressed: () => _handleAdd(provider),
                style: ElevatedButton.styleFrom(
                  backgroundColor: kNavy,
                  foregroundColor: kBackground,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  elevation: 0,
                ),
                child: const Text('Add', style: TextStyle(fontWeight: FontWeight.w600)),
              ),
            ],
          ),
          const SizedBox(height: 8),

          // Note input
          TextField(
            controller: _noteController,
            style: const TextStyle(fontSize: 13, color: kText),
            decoration: InputDecoration(
              hintText: 'Add a note...',
              hintStyle: const TextStyle(color: kSubtext, fontSize: 13),
              filled: true,
              fillColor: kBackground,
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: kBorder),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: kBorder),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: kNavy),
              ),
            ),
            onSubmitted: (_) => _handleAdd(provider),
          ),
          const SizedBox(height: 10),

          // Payment method row
          Wrap(
            spacing: 6,
            runSpacing: 6,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              const Text('Paid via:', style: TextStyle(fontSize: 12, color: kSubtext)),
              ...kPaymentTypes.map((pt) => _PaymentChip(
                label: '${pt.icon} ${pt.label}',
                selected: _selectedPayment == pt.label,
                activeColor: pt.color,
                onTap: () => setState(() { _selectedPayment = pt.label; _customPay = ''; }),
              )),
              _PaymentChip(
                label: '✍️ Other',
                selected: _selectedPayment == 'Other',
                activeColor: kNavy,
                onTap: () => setState(() => _selectedPayment = 'Other'),
              ),
              if (_selectedPayment == 'Other')
                SizedBox(
                  width: 160,
                  child: TextField(
                    style: const TextStyle(fontSize: 12),
                    decoration: InputDecoration(
                      hintText: 'e.g. Wallet, Bank...',
                      hintStyle: const TextStyle(fontSize: 12, color: kSubtext),
                      isDense: true,
                      filled: true,
                      fillColor: kBackground,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(20),
                        borderSide: const BorderSide(color: kNavy),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(20),
                        borderSide: const BorderSide(color: kNavy),
                      ),
                    ),
                    onChanged: (v) => _customPay = v,
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _PaymentChip extends StatelessWidget {
  final String label;
  final bool selected;
  final Color activeColor;
  final VoidCallback onTap;

  const _PaymentChip({
    required this.label,
    required this.selected,
    required this.activeColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
        decoration: BoxDecoration(
          color: selected ? activeColor.withOpacity(0.08) : kBackground,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: selected ? activeColor : kBorder,
            width: selected ? 2 : 1,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 12,
            fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
            color: selected ? activeColor : kSubtext,
          ),
        ),
      ),
    );
  }
}
