import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_provider.dart';
import '../utils/constants.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late TextEditingController _budgetCtrl;

  @override
  void initState() {
    super.initState();
    _budgetCtrl = TextEditingController();
  }

  @override
  void dispose() {
    _budgetCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<AppProvider>();

    if (_budgetCtrl.text.isEmpty) {
      _budgetCtrl.text = provider.totalBudget.toStringAsFixed(0);
    }

    return SingleChildScrollView(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('⚙️ Settings',
                style: TextStyle(fontSize: 22, color: kText, fontStyle: FontStyle.italic)),
            const SizedBox(height: 16),

            // Currency
            _Card(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Currency', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: kMuted)),
                  const SizedBox(height: 8),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                    decoration: BoxDecoration(
                      color: kBackground,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: kBorder),
                    ),
                    child: DropdownButtonHideUnderline(
                      child: DropdownButton<String>(
                        value: provider.currency,
                        isExpanded: true,
                        style: const TextStyle(fontSize: 14, color: kText),
                        items: kCurrencies.entries.map((e) => DropdownMenuItem(
                          value: e.key,
                          child: Text('${e.key} ${e.value}'),
                        )).toList(),
                        onChanged: (v) {
                          if (v != null) provider.setCurrency(v);
                        },
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),

            // Monthly Budget
            _Card(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Monthly Budget', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: kMuted)),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _budgetCtrl,
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          style: const TextStyle(fontSize: 14, color: kText),
                          decoration: InputDecoration(
                            filled: true,
                            fillColor: kBackground,
                            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: kBorder)),
                            enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: kBorder)),
                            focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: kNavy)),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      ElevatedButton(
                        onPressed: () {
                          final v = double.tryParse(_budgetCtrl.text) ?? kDefaultBudget;
                          provider.setTotalBudget(v);
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Budget saved!'), duration: Duration(seconds: 1)),
                          );
                        },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: kNavy,
                          foregroundColor: kBackground,
                          elevation: 0,
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                        ),
                        child: const Text('Save', style: TextStyle(fontWeight: FontWeight.w600)),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),

            // Sound & Haptic
            _Card(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Preferences', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: kMuted)),
                  const SizedBox(height: 8),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Row(
                        children: [
                          Text('🔊', style: TextStyle(fontSize: 16)),
                          SizedBox(width: 8),
                          Text('Sound effects', style: TextStyle(fontSize: 13, color: kText)),
                        ],
                      ),
                      Switch(
                        value: provider.soundEnabled,
                        onChanged: provider.setSoundEnabled,
                        activeColor: kNavy,
                      ),
                    ],
                  ),
                  const Divider(color: kBorder, height: 12),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Row(
                        children: [
                          Text('📳', style: TextStyle(fontSize: 16)),
                          SizedBox(width: 8),
                          Text('Haptic feedback', style: TextStyle(fontSize: 13, color: kText)),
                        ],
                      ),
                      Switch(
                        value: provider.hapticEnabled,
                        onChanged: provider.setHapticEnabled,
                        activeColor: kNavy,
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),

            // Offline status
            _Card(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: const [
                  Text('Offline Ready', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: kMuted)),
                  SizedBox(height: 4),
                  Text('✅ All data saved locally on your device. No internet needed.',
                      style: TextStyle(fontSize: 12, color: kSage)),
                ],
              ),
            ),
            const SizedBox(height: 12),

            // Clear data
            _Card(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Data', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: kMuted)),
                  const SizedBox(height: 8),
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton(
                      onPressed: () async {
                        final confirmed = await showDialog<bool>(
                          context: context,
                          builder: (_) => AlertDialog(
                            title: const Text('Clear All Expenses?'),
                            content: const Text('This cannot be undone.'),
                            actions: [
                              TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
                              TextButton(
                                onPressed: () => Navigator.pop(context, true),
                                child: const Text('Clear', style: TextStyle(color: Colors.red)),
                              ),
                            ],
                          ),
                        );
                        if (confirmed == true) {
                          provider.clearAll();
                        }
                      },
                      style: OutlinedButton.styleFrom(
                        foregroundColor: kTerracotta,
                        side: const BorderSide(color: kTerracotta, width: 1),
                        backgroundColor: kTerracotta.withOpacity(0.06),
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      child: const Text('🗑️ Clear All Expenses', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Card extends StatelessWidget {
  final Widget child;
  const _Card({required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: kCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: kBorder),
      ),
      child: child,
    );
  }
}
