import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:fl_chart/fl_chart.dart';
import '../providers/app_provider.dart';
import '../utils/constants.dart';

class WeeklyTrendWidget extends StatefulWidget {
  const WeeklyTrendWidget({super.key});

  @override
  State<WeeklyTrendWidget> createState() => _WeeklyTrendWidgetState();
}

class _WeeklyTrendWidgetState extends State<WeeklyTrendWidget> {
  String _activeTab = 'daily';

  String _fmt(double v) => v.toStringAsFixed(0).replaceAllMapped(
      RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'), (m) => '${m[1]},');

  List<_DayData> _buildWeeklyData(List expenses) {
    return List.generate(7, (i) {
      final d = DateTime.now().subtract(Duration(days: 6 - i));
      final dateStr =
          '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
      final amount = expenses
          .where((e) => e.date == dateStr)
          .fold(0.0, (s, e) => s + e.amount);
      const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
      return _DayData(day: days[d.weekday - 1], amount: amount.toDouble());
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider    = context.watch<AppProvider>();
    final currency    = provider.currency;
    final expenses    = provider.expenses;
    final weeklyData  = _buildWeeklyData(expenses);
    final totalWeek   = weeklyData.fold(0.0, (s, d) => s + d.amount);
    final avgDay      = totalWeek / 7;
    final highest     = weeklyData.reduce((a, b) => a.amount >= b.amount ? a : b);

    final barGroups = weeklyData.asMap().entries.map((e) => BarChartGroupData(
      x: e.key,
      barRods: [BarChartRodData(
        toY: e.value.amount,
        color: kNavy,
        width: 22,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(4)),
      )],
    )).toList();

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
              const Text('📈 This Week', style: TextStyle(fontSize: 18, color: kSubtext, fontStyle: FontStyle.italic)),
              Container(
                padding: const EdgeInsets.all(2),
                decoration: BoxDecoration(color: kBackground, borderRadius: BorderRadius.circular(8)),
                child: Row(
                  children: ['daily', 'weekly', 'monthly'].map((t) => GestureDetector(
                    onTap: () => setState(() => _activeTab = t),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: _activeTab == t ? kNavy : Colors.transparent,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        t[0].toUpperCase() + t.substring(1),
                        style: TextStyle(fontSize: 11, fontWeight: FontWeight.w500,
                            color: _activeTab == t ? kBackground : kSubtext),
                      ),
                    ),
                  )).toList(),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),

          SizedBox(
            height: 120,
            child: BarChart(BarChartData(
              barGroups: barGroups,
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
                      if (i < 0 || i >= weeklyData.length) return const SizedBox.shrink();
                      return Text(weeklyData[i].day,
                          style: const TextStyle(fontSize: 11, color: kSubtext));
                    },
                  ),
                ),
              ),
              barTouchData: BarTouchData(
                touchTooltipData: BarTouchTooltipData(
                  getTooltipItem: (group, _, rod, __) => BarTooltipItem(
                    '$currency${_fmt(rod.toY)}',
                    const TextStyle(fontSize: 12, color: Colors.white, fontWeight: FontWeight.w600),
                  ),
                ),
              ),
            )),
          ),

          const Divider(color: kBorder, height: 16),

          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _Stat(label: 'Avg/day',   value: '$currency${_fmt(avgDay)}',   color: kText),
              _Stat(label: 'This week', value: '$currency${_fmt(totalWeek)}', color: kText),
              _Stat(label: 'Highest',   value: highest.amount > 0 ? highest.day : '—', color: kTerracotta),
            ],
          ),
        ],
      ),
    );
  }
}

class _DayData {
  final String day;
  final double amount;
  const _DayData({required this.day, required this.amount});
}

class _Stat extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _Stat({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(label, style: const TextStyle(fontSize: 11, color: kSubtext)),
        const SizedBox(height: 2),
        Text(value, style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: color)),
      ],
    );
  }
}
