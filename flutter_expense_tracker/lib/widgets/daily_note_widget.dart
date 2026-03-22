import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_provider.dart';
import '../utils/constants.dart';

class DailyNoteWidget extends StatefulWidget {
  const DailyNoteWidget({super.key});

  @override
  State<DailyNoteWidget> createState() => _DailyNoteWidgetState();
}

class _DailyNoteWidgetState extends State<DailyNoteWidget> {
  late TextEditingController _ctrl;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _ctrl = TextEditingController();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  String _fmt(double v) => v.toStringAsFixed(0).replaceAllMapped(
      RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'), (m) => '${m[1]},');

  @override
  Widget build(BuildContext context) {
    final provider   = context.watch<AppProvider>();
    final currency   = provider.currency;
    final today      = todayStr();
    final yesterday  = _yesterday();

    // Today's stats
    final todayExpenses = provider.expenses.where((e) => e.date == today && e.type == 'expense').toList();
    final todayTotal    = todayExpenses.fold(0.0, (s, e) => s + e.amount);

    // Top category today
    final catTotals = <String, double>{};
    for (final e in todayExpenses) {
      catTotals[e.category] = (catTotals[e.category] ?? 0) + e.amount;
    }
    String? topCat;
    double topAmt = 0;
    catTotals.forEach((cat, amt) {
      if (amt > topAmt) { topAmt = amt; topCat = cat; }
    });

    // Notes
    final todayNote     = provider.getDailyNote(today);
    final yesterdayNote = provider.getDailyNote(yesterday);

    // Sync controller
    if (_ctrl.text.isEmpty && todayNote.isNotEmpty) {
      _ctrl.text = todayNote;
      _ctrl.selection = TextSelection.fromPosition(TextPosition(offset: _ctrl.text.length));
    }

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
          const Text('📝 Today\'s Note',
              style: TextStyle(fontSize: 18, color: kSubtext, fontStyle: FontStyle.italic)),
          const SizedBox(height: 10),

          // Today's summary
          if (todayTotal > 0) ...[
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: kBackground,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'You spent $currency${_fmt(todayTotal)} across ${todayExpenses.length} '
                    '${todayExpenses.length == 1 ? 'entry' : 'entries'}',
                    style: const TextStyle(fontSize: 13, color: kText, fontWeight: FontWeight.w500),
                  ),
                  if (topCat != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      'Top: $topCat ($currency${_fmt(topAmt)})',
                      style: const TextStyle(fontSize: 12, color: kSubtext),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 10),
          ],

          // Note input
          TextField(
            controller: _ctrl,
            maxLines: 3,
            style: const TextStyle(fontSize: 13, color: kText),
            decoration: InputDecoration(
              hintText: 'How was your spending today? Write a reflection...',
              hintStyle: const TextStyle(color: kSubtext, fontSize: 13),
              filled: true,
              fillColor: kBackground,
              contentPadding: const EdgeInsets.all(12),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: kBorder)),
              enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: kBorder)),
              focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: kNavy)),
            ),
          ),
          const SizedBox(height: 8),

          // Save button
          Align(
            alignment: Alignment.centerRight,
            child: ElevatedButton(
              onPressed: _saving ? null : () async {
                setState(() => _saving = true);
                await provider.saveDailyNote(today, _ctrl.text);
                setState(() => _saving = false);
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Note saved! 📝'), duration: Duration(seconds: 1)),
                  );
                }
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: kNavy,
                foregroundColor: kBackground,
                elevation: 0,
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              child: const Text('Save 💾', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
            ),
          ),

          // Yesterday's note
          if (yesterdayNote.isNotEmpty) ...[
            const Divider(color: kBorder, height: 20),
            const Text('Yesterday:', style: TextStyle(fontSize: 11, color: kSubtext, fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            Text(
              '"$yesterdayNote"',
              style: const TextStyle(fontSize: 12, color: kSubtext, fontStyle: FontStyle.italic),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ],
      ),
    );
  }

  String _yesterday() {
    final d = DateTime.now().subtract(const Duration(days: 1));
    return '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
  }
}
