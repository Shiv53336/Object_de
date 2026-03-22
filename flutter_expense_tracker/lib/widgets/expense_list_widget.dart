import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_provider.dart';
import '../models/expense.dart';
import '../utils/constants.dart';
import 'edit_expense_modal.dart';

class ExpenseListWidget extends StatefulWidget {
  const ExpenseListWidget({super.key});

  @override
  State<ExpenseListWidget> createState() => _ExpenseListWidgetState();
}

class _ExpenseListWidgetState extends State<ExpenseListWidget> {
  final _searchCtrl = TextEditingController();
  String _searchQuery = '';
  String? _filterCat;

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<AppProvider>();

    var expenses = List<Expense>.from(provider.expenses)
      ..sort((a, b) {
        final d = b.date.compareTo(a.date);
        return d != 0 ? d : b.id.compareTo(a.id);
      });

    // Apply search
    if (_searchQuery.isNotEmpty) {
      expenses = expenses
          .where((e) => e.note.toLowerCase().contains(_searchQuery.toLowerCase()) ||
              e.category.toLowerCase().contains(_searchQuery.toLowerCase()))
          .toList();
    }

    // Apply category filter
    if (_filterCat != null) {
      expenses = expenses.where((e) => e.category == _filterCat).toList();
    }

    final allCategories = provider.expenses.map((e) => e.category).toSet().toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 0, 16, 10),
          child: Text('📝 Recent Entries',
              style: TextStyle(fontSize: 18, color: kSubtext, fontStyle: FontStyle.italic)),
        ),

        // Search bar
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
          child: TextField(
            controller: _searchCtrl,
            style: const TextStyle(fontSize: 13, color: kText),
            decoration: InputDecoration(
              hintText: 'Search expenses...',
              hintStyle: const TextStyle(color: kSubtext, fontSize: 13),
              prefixIcon: const Icon(Icons.search, size: 18, color: kSubtext),
              suffixIcon: _searchQuery.isNotEmpty
                  ? IconButton(
                      icon: const Icon(Icons.close, size: 16, color: kSubtext),
                      onPressed: () => setState(() { _searchCtrl.clear(); _searchQuery = ''; }),
                    )
                  : null,
              filled: true,
              fillColor: kCard,
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: kBorder)),
              enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: kBorder)),
              focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: kNavy)),
            ),
            onChanged: (v) => setState(() => _searchQuery = v),
          ),
        ),

        // Category filter chips
        if (allCategories.isNotEmpty)
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: Row(
              children: [
                _FilterChip(
                  label: 'All',
                  selected: _filterCat == null,
                  onTap: () => setState(() => _filterCat = null),
                ),
                const SizedBox(width: 6),
                ...allCategories.map((cat) {
                  final matching = [...provider.categories, ...kDefaultIncomeCategories]
                      .where((c) => c.name == cat).toList();
                  final emoji = matching.isNotEmpty ? matching.first.emoji : '•';
                  return Padding(
                    padding: const EdgeInsets.only(right: 6),
                    child: _FilterChip(
                      label: '$emoji ${cat.split(' ').first}',
                      selected: _filterCat == cat,
                      onTap: () => setState(() => _filterCat = _filterCat == cat ? null : cat),
                    ),
                  );
                }),
              ],
            ),
          ),

        if (expenses.isEmpty)
          Container(
            margin: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            padding: const EdgeInsets.all(32),
            alignment: Alignment.center,
            child: Text(
              _searchQuery.isNotEmpty || _filterCat != null
                  ? 'No matching entries found.'
                  : 'No expenses yet.\nAdd your first one above! 👆',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 14, color: kSubtext),
            ),
          )
        else ..._buildGrouped(expenses, provider.currency),
      ],
    );
  }

  List<Widget> _buildGrouped(List<Expense> expenses, String currency) {
    final Map<String, List<Expense>> grouped = {};
    for (final exp in expenses) {
      final label = dateLabel(exp.date);
      grouped.putIfAbsent(label, () => []).add(exp);
    }
    return grouped.entries.map((entry) => _DateGroup(
      label: entry.key,
      expenses: entry.value,
      currency: currency,
    )).toList();
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _FilterChip({required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
        decoration: BoxDecoration(
          color: selected ? kNavy : kCard,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: selected ? kNavy : kBorder),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 12,
            fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
            color: selected ? Colors.white : kSubtext,
          ),
        ),
      ),
    );
  }
}

class _DateGroup extends StatelessWidget {
  final String label;
  final List<Expense> expenses;
  final String currency;

  const _DateGroup({required this.label, required this.expenses, required this.currency});

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
          ...expenses.map((exp) => _ExpenseCard(exp: exp, currency: currency)),
        ],
      ),
    );
  }
}

class _ExpenseCard extends StatefulWidget {
  final Expense exp;
  final String currency;

  const _ExpenseCard({required this.exp, required this.currency});

  @override
  State<_ExpenseCard> createState() => _ExpenseCardState();
}

class _ExpenseCardState extends State<_ExpenseCard> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _opacity;
  late final Animation<Offset> _slide;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 400))..forward();
    _opacity = CurvedAnimation(parent: _ctrl, curve: Curves.easeOut);
    _slide   = Tween(begin: const Offset(0, -0.3), end: Offset.zero)
        .animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeOut));
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Expense get exp => widget.exp;
  String get currency => widget.currency;

  String _fmt(double v) => v.toStringAsFixed(0).replaceAllMapped(
      RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'), (m) => '${m[1]},');

  @override
  Widget build(BuildContext context) {
    final pc        = paymentColor(exp.payment);
    final isIncome  = exp.type == 'income';
    final amtColor  = isIncome ? kSage : kTerracotta;
    final amtPrefix = isIncome ? '+' : '−';

    return FadeTransition(
      opacity: _opacity,
      child: SlideTransition(
        position: _slide,
        child: GestureDetector(
          onTap: () => showEditExpenseModal(context, exp),
          child: Container(
            margin: const EdgeInsets.only(bottom: 6),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            decoration: BoxDecoration(
              color: kCard,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: isIncome ? kSage.withOpacity(0.3) : kBorder),
              boxShadow: const [BoxShadow(color: Color(0x0A2D2A26), blurRadius: 4, offset: Offset(0, 1))],
            ),
            child: Row(
              children: [
                Container(
                  width: 38, height: 38,
                  decoration: BoxDecoration(
                    color: isIncome ? kSage.withOpacity(0.1) : kBackground,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  alignment: Alignment.center,
                  child: Text(exp.emoji, style: const TextStyle(fontSize: 18)),
                ),
                const SizedBox(width: 12),
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
                Text(
                  '$amtPrefix$currency${_fmt(exp.amount)}',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: amtColor),
                ),
                const SizedBox(width: 4),
                const Icon(Icons.chevron_right, size: 16, color: kBorder),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
