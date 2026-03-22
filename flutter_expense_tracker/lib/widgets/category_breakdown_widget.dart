import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:fl_chart/fl_chart.dart';
import '../providers/app_provider.dart';
import '../models/expense_category.dart';
import '../utils/constants.dart';

class CategoryBreakdownWidget extends StatefulWidget {
  const CategoryBreakdownWidget({super.key});

  @override
  State<CategoryBreakdownWidget> createState() => _CategoryBreakdownWidgetState();
}

class _CategoryBreakdownWidgetState extends State<CategoryBreakdownWidget> {
  bool _showDonut = true;
  bool _showAddForm = false;
  final _emojiCtrl  = TextEditingController();
  final _nameCtrl   = TextEditingController();
  final _budgetCtrl = TextEditingController();

  @override
  void dispose() {
    _emojiCtrl.dispose();
    _nameCtrl.dispose();
    _budgetCtrl.dispose();
    super.dispose();
  }

  void _saveCategory(AppProvider provider) {
    if (_nameCtrl.text.trim().isEmpty) return;
    provider.addCategory(ExpenseCategory(
      name:   _nameCtrl.text.trim(),
      emoji:  _emojiCtrl.text.isNotEmpty ? _emojiCtrl.text : '🏷️',
      color:  provider.randomColor(),
      budget: double.tryParse(_budgetCtrl.text) ?? 1000,
    ));
    _emojiCtrl.clear();
    _nameCtrl.clear();
    _budgetCtrl.clear();
    setState(() => _showAddForm = false);
  }

  String _fmt(double v) => v.toStringAsFixed(0).replaceAllMapped(
      RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'), (m) => '${m[1]},');

  @override
  Widget build(BuildContext context) {
    final provider  = context.watch<AppProvider>();
    final currency  = provider.currency;
    final cats      = provider.categories;
    final expenses  = provider.expenses;

    const _incomeCategories = ['Salary', 'Freelance', 'Investment', 'Gift', 'Other Income'];
    final expenseCats = cats.where((c) => !_incomeCategories.contains(c.name)).toList();

    final catSpend = expenseCats.map((c) {
      final spent = expenses
          .where((e) => e.category == c.name && e.type == 'expense')
          .fold(0.0, (s, e) => s + e.amount);
      return _CatData(cat: c, spent: spent);
    }).toList();

    final pieData = catSpend.where((d) => d.spent > 0).toList();

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
          // Header + toggle
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('🏷️ By Category', style: TextStyle(fontSize: 18, color: kSubtext, fontStyle: FontStyle.italic)),
              Container(
                padding: const EdgeInsets.all(2),
                decoration: BoxDecoration(color: kBackground, borderRadius: BorderRadius.circular(8)),
                child: Row(
                  children: [
                    _ChartToggleBtn(label: 'Donut', active: _showDonut,  onTap: () => setState(() => _showDonut = true)),
                    _ChartToggleBtn(label: 'Bar',   active: !_showDonut, onTap: () => setState(() => _showDonut = false)),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Chart
          if (_showDonut)
            _DonutChart(catSpend: catSpend, pieData: pieData, currency: currency, fmt: _fmt)
          else
            _BarChartSection(catSpend: catSpend, currency: currency, fmt: _fmt),

          const SizedBox(height: 10),

          // Add custom category button
          GestureDetector(
            onTap: () => setState(() => _showAddForm = !_showAddForm),
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 8),
              decoration: BoxDecoration(
                border: Border.all(color: kBorder, style: BorderStyle.solid),
                borderRadius: BorderRadius.circular(8),
              ),
              alignment: Alignment.center,
              child: const Text('+ Add Custom Category', style: TextStyle(fontSize: 12, color: kSubtext)),
            ),
          ),

          if (_showAddForm) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: kBackground, borderRadius: BorderRadius.circular(10)),
              child: Wrap(
                spacing: 8,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  SizedBox(
                    width: 48,
                    child: TextField(
                      controller: _emojiCtrl,
                      maxLength: 2,
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontSize: 18),
                      decoration: InputDecoration(
                        counterText: '',
                        hintText: '🏷️',
                        filled: true,
                        fillColor: Colors.white,
                        contentPadding: const EdgeInsets.symmetric(vertical: 6),
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(6), borderSide: const BorderSide(color: kBorder)),
                        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(6), borderSide: const BorderSide(color: kBorder)),
                      ),
                    ),
                  ),
                  SizedBox(
                    width: 140,
                    child: TextField(
                      controller: _nameCtrl,
                      style: const TextStyle(fontSize: 13),
                      decoration: InputDecoration(
                        hintText: 'Category name',
                        hintStyle: const TextStyle(fontSize: 13, color: kSubtext),
                        filled: true,
                        fillColor: Colors.white,
                        contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(6), borderSide: const BorderSide(color: kBorder)),
                        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(6), borderSide: const BorderSide(color: kBorder)),
                      ),
                    ),
                  ),
                  SizedBox(
                    width: 90,
                    child: TextField(
                      controller: _budgetCtrl,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      style: const TextStyle(fontSize: 13),
                      decoration: InputDecoration(
                        hintText: 'Budget',
                        hintStyle: const TextStyle(fontSize: 13, color: kSubtext),
                        filled: true,
                        fillColor: Colors.white,
                        contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(6), borderSide: const BorderSide(color: kBorder)),
                        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(6), borderSide: const BorderSide(color: kBorder)),
                      ),
                    ),
                  ),
                  ElevatedButton(
                    onPressed: () => _saveCategory(provider),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: kSage,
                      foregroundColor: Colors.white,
                      elevation: 0,
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                    ),
                    child: const Text('Save', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _CatData {
  final ExpenseCategory cat;
  final double spent;
  _CatData({required this.cat, required this.spent});
}

class _DonutChart extends StatelessWidget {
  final List<_CatData> catSpend;
  final List<_CatData> pieData;
  final String currency;
  final String Function(double) fmt;

  const _DonutChart({required this.catSpend, required this.pieData, required this.currency, required this.fmt});

  @override
  Widget build(BuildContext context) {
    final sections = pieData.isNotEmpty
        ? pieData.map((d) => PieChartSectionData(
            value: d.spent,
            color: hexToColor(d.cat.color),
            radius: 30,
            title: '',
          )).toList()
        : [PieChartSectionData(value: 1, color: kBorder, radius: 30, title: '')];

    return Row(
      children: [
        SizedBox(
          width: 140, height: 140,
          child: PieChart(PieChartData(
            sections: sections,
            centerSpaceRadius: 40,
            sectionsSpace: 2,
          )),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            children: catSpend.map((d) => Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                children: [
                  Container(width: 8, height: 8, decoration: BoxDecoration(color: hexToColor(d.cat.color), shape: BoxShape.circle)),
                  const SizedBox(width: 6),
                  Expanded(child: Text('${d.cat.emoji} ${d.cat.name.split(' ').first}', style: const TextStyle(fontSize: 11, color: kMuted))),
                  Text('$currency${fmt(d.spent)}', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: kText)),
                ],
              ),
            )).toList(),
          ),
        ),
      ],
    );
  }
}

class _BarChartSection extends StatelessWidget {
  final List<_CatData> catSpend;
  final String currency;
  final String Function(double) fmt;

  const _BarChartSection({required this.catSpend, required this.currency, required this.fmt});

  @override
  Widget build(BuildContext context) {
    final groups = catSpend.asMap().entries.map((e) => BarChartGroupData(
      x: e.key,
      barRods: [BarChartRodData(
        toY: e.value.spent,
        color: hexToColor(e.value.cat.color),
        width: 28,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(6)),
      )],
    )).toList();

    return SizedBox(
      height: 160,
      child: BarChart(BarChartData(
        barGroups: groups,
        borderData: FlBorderData(show: false),
        gridData:   FlGridData(show: false),
        titlesData: FlTitlesData(
          leftTitles:   AxisTitles(sideTitles: SideTitles(showTitles: false)),
          rightTitles:  AxisTitles(sideTitles: SideTitles(showTitles: false)),
          topTitles:    AxisTitles(sideTitles: SideTitles(showTitles: false)),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              getTitlesWidget: (v, _) {
                final i = v.toInt();
                if (i < 0 || i >= catSpend.length) return const SizedBox.shrink();
                return Text(catSpend[i].cat.emoji, style: const TextStyle(fontSize: 14));
              },
            ),
          ),
        ),
        barTouchData: BarTouchData(
          touchTooltipData: BarTouchTooltipData(
            getTooltipItem: (group, _, rod, __) => BarTooltipItem(
              '$currency${fmt(rod.toY)}',
              const TextStyle(fontSize: 12, color: Colors.white, fontWeight: FontWeight.w600),
            ),
          ),
        ),
      )),
    );
  }
}

class _ChartToggleBtn extends StatelessWidget {
  final String label;
  final bool active;
  final VoidCallback onTap;

  const _ChartToggleBtn({required this.label, required this.active, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: active ? kNavy : Colors.transparent,
          borderRadius: BorderRadius.circular(6),
        ),
        child: Text(label, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: active ? kBackground : kSubtext)),
      ),
    );
  }
}
