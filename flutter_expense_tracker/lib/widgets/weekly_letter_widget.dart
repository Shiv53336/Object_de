import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../providers/app_provider.dart';
import '../utils/constants.dart';

class WeeklyLetterWidget extends StatelessWidget {
  const WeeklyLetterWidget({super.key});

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<AppProvider>();
    final currency = provider.currency;

    // Calculate week range (Mon-Sun)
    final now       = DateTime.now();
    final monday    = now.subtract(Duration(days: now.weekday - 1));
    final sunday    = monday.add(const Duration(days: 6));
    final weekDates = List.generate(7, (i) => monday.add(Duration(days: i)));

    String _dateStr(DateTime d) =>
        '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

    final weekStrings  = weekDates.map(_dateStr).toSet();
    final weekExpenses = provider.expenses
        .where((e) => weekStrings.contains(e.date) && e.type == 'expense')
        .toList();

    final totalSpent  = weekExpenses.fold(0.0, (s, e) => s + e.amount);
    final entryCount  = weekExpenses.length;
    final streak      = provider.streak.currentStreak;

    // Top category
    final catTotals = <String, double>{};
    for (final e in weekExpenses) {
      catTotals[e.category] = (catTotals[e.category] ?? 0) + e.amount;
    }
    String? topCat;
    double topAmt = 0;
    catTotals.forEach((cat, amt) {
      if (amt > topAmt) { topAmt = amt; topCat = cat; }
    });
    final topPct = totalSpent > 0 ? (topAmt / totalSpent * 100).round() : 0;

    // Lightest spending day
    final dayTotals = <String, double>{};
    for (final e in weekExpenses) {
      dayTotals[e.date] = (dayTotals[e.date] ?? 0) + e.amount;
    }
    String? lightestDay;
    double lightestAmt = double.infinity;
    dayTotals.forEach((date, amt) {
      if (amt < lightestAmt) { lightestAmt = amt; lightestDay = date; }
    });

    // Best daily note
    String? bestNote;
    for (final d in weekStrings) {
      final note = provider.getDailyNote(d);
      if (note.isNotEmpty) { bestNote = note; break; }
    }

    String _monthShort(int m) => ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m-1];
    String _dayName(DateTime d) => ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][d.weekday - 1];
    String _fmt(double v) => v.toStringAsFixed(0).replaceAllMapped(
        RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'), (m) => '${m[1]},');

    final weekLabel =
        '${_monthShort(monday.month)} ${monday.day} — ${_monthShort(sunday.month)} ${sunday.day}';

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      decoration: BoxDecoration(
        color: kCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: kBorder),
        boxShadow: const [BoxShadow(color: Color(0x0F2D2A26), blurRadius: 12, offset: Offset(0, 2))],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: kNavy.withOpacity(0.05),
              borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
            ),
            child: Row(
              children: [
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('📬 Your Weekly Letter',
                          style: TextStyle(fontSize: 18, color: kNavy, fontWeight: FontWeight.w700)),
                    ],
                  ),
                ),
                Text(weekLabel, style: const TextStyle(fontSize: 11, color: kSubtext)),
              ],
            ),
          ),

          Padding(
            padding: const EdgeInsets.all(16),
            child: entryCount == 0
                ? const Text(
                    'No expenses logged this week yet. Start tracking to see your weekly story!',
                    style: TextStyle(fontSize: 13, color: kSubtext),
                  )
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Summary text
                      RichText(
                        text: TextSpan(
                          style: const TextStyle(fontSize: 14, color: kText, height: 1.6),
                          children: [
                            TextSpan(text: 'This week, you logged '),
                            TextSpan(text: '$entryCount ${entryCount == 1 ? "entry" : "entries"}',
                                style: const TextStyle(fontWeight: FontWeight.w700)),
                            TextSpan(text: ' totaling '),
                            TextSpan(text: '$currency${_fmt(totalSpent)}',
                                style: const TextStyle(fontWeight: FontWeight.w700, color: kTerracotta)),
                            TextSpan(text: '.'),
                          ],
                        ),
                      ),
                      const SizedBox(height: 8),

                      if (topCat != null)
                        _LetterLine(
                          emoji: '🏆',
                          text: '$topCat was your biggest companion at $currency${_fmt(topAmt)} ($topPct%).',
                        ),

                      if (lightestDay != null && lightestAmt != double.infinity)
                        _LetterLine(
                          emoji: '☀️',
                          text: 'Your lightest day was ${_dayName(DateTime.parse(lightestDay!))} — just $currency${_fmt(lightestAmt)}.',
                        ),

                      if (streak > 0)
                        _LetterLine(
                          emoji: '🔥',
                          text: 'Your streak: $streak ${streak == 1 ? "day" : "days"} and counting!',
                        ),

                      if (bestNote != null) ...[
                        const SizedBox(height: 4),
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: kBackground,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text('📝 ', style: TextStyle(fontSize: 14)),
                              Expanded(
                                child: Text(
                                  '"$bestNote"',
                                  style: const TextStyle(fontSize: 12, color: kSubtext, fontStyle: FontStyle.italic),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],

                      const SizedBox(height: 12),
                      const Divider(color: kBorder, height: 1),
                      const SizedBox(height: 12),

                      // Share button
                      SizedBox(
                        width: double.infinity,
                        child: OutlinedButton.icon(
                          onPressed: () => _copyToClipboard(context, _buildShareText(
                            weekLabel, entryCount, totalSpent, currency, topCat, topAmt, topPct,
                            lightestDay, lightestAmt, streak, bestNote, _fmt, _dayName,
                          )),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: kNavy,
                            side: const BorderSide(color: kNavy),
                            padding: const EdgeInsets.symmetric(vertical: 10),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                          icon: const Icon(Icons.share, size: 16),
                          label: const Text('Share This Week 📤',
                              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                        ),
                      ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  String _buildShareText(
    String weekLabel, int entryCount, double totalSpent, String currency,
    String? topCat, double topAmt, int topPct,
    String? lightestDay, double lightestAmt, int streak, String? bestNote,
    String Function(double) fmt, String Function(DateTime) dayName,
  ) {
    final sb = StringBuffer();
    sb.writeln('📬 My Weekly Money Letter');
    sb.writeln(weekLabel);
    sb.writeln();
    sb.writeln('This week I logged $entryCount ${entryCount == 1 ? "entry" : "entries"} totaling $currency${fmt(totalSpent)}.');
    if (topCat != null) sb.writeln('🏆 Top category: $topCat ($currency${fmt(topAmt)}, $topPct%)');
    if (lightestDay != null && lightestAmt != double.infinity) {
      sb.writeln('☀️ Lightest day: ${dayName(DateTime.parse(lightestDay))} ($currency${fmt(lightestAmt)})');
    }
    if (streak > 0) sb.writeln('🔥 Streak: $streak days!');
    if (bestNote != null) sb.writeln('\n"$bestNote"');
    sb.writeln('\nTracked with Money Journal ✏️');
    return sb.toString();
  }

  void _copyToClipboard(BuildContext context, String text) {
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Weekly letter copied to clipboard! 📋'),
        duration: Duration(seconds: 2),
      ),
    );
  }
}

class _LetterLine extends StatelessWidget {
  final String emoji;
  final String text;
  const _LetterLine({required this.emoji, required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('$emoji ', style: const TextStyle(fontSize: 14)),
          Expanded(
            child: Text(text, style: const TextStyle(fontSize: 13, color: kText, height: 1.5)),
          ),
        ],
      ),
    );
  }
}
