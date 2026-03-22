import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../providers/app_provider.dart';
import '../utils/constants.dart';
import 'main_screen.dart';

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final _pageCtrl   = PageController();
  final _amountCtrl = TextEditingController();
  int _page         = 0;

  @override
  void dispose() {
    _pageCtrl.dispose();
    _amountCtrl.dispose();
    super.dispose();
  }

  void _next() {
    if (_page < 3) {
      _pageCtrl.nextPage(duration: const Duration(milliseconds: 350), curve: Curves.easeInOut);
    } else {
      _finish();
    }
  }

  Future<void> _finish() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('et_onboarded', true);
    if (mounted) {
      Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => const MainScreen()));
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.read<AppProvider>();

    return Scaffold(
      backgroundColor: kBackground,
      body: SafeArea(
        child: Column(
          children: [
            // Progress dots
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 20),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(4, (i) => AnimatedContainer(
                  duration: const Duration(milliseconds: 300),
                  margin: const EdgeInsets.symmetric(horizontal: 4),
                  width: _page == i ? 24 : 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: _page == i ? kNavy : kBorder,
                    borderRadius: BorderRadius.circular(4),
                  ),
                )),
              ),
            ),

            Expanded(
              child: PageView(
                controller: _pageCtrl,
                onPageChanged: (p) => setState(() => _page = p),
                physics: const NeverScrollableScrollPhysics(),
                children: [
                  // Page 1: Welcome
                  _OnboardPage(
                    emoji: '✏️',
                    title: 'Welcome to\nMoney Journal',
                    subtitle: 'Your personal money diary.\nTrack spending, build habits, journal your money.',
                    action: _OnboardButton(label: 'Get Started →', onTap: _next),
                  ),

                  // Page 2: Currency
                  _OnboardPage(
                    emoji: '💱',
                    title: 'What currency\ndo you use?',
                    subtitle: 'You can change this later in settings.',
                    action: Column(
                      children: [
                        Wrap(
                          spacing: 12,
                          runSpacing: 12,
                          alignment: WrapAlignment.center,
                          children: kCurrencies.keys.map((c) => _CurrencyChip(
                            symbol: c,
                            code: kCurrencies[c]!,
                            selected: provider.currency == c,
                            onTap: () {
                              provider.setCurrency(c);
                              setState(() {});
                            },
                          )).toList(),
                        ),
                        const SizedBox(height: 24),
                        _OnboardButton(label: 'Next →', onTap: _next),
                      ],
                    ),
                  ),

                  // Page 3: Budget
                  _OnboardPage(
                    emoji: '🎯',
                    title: 'Set a monthly\nbudget',
                    subtitle: "We'll help you stay on track.",
                    action: Column(
                      children: [
                        Container(
                          decoration: BoxDecoration(
                            color: kCard,
                            borderRadius: BorderRadius.circular(14),
                            border: Border.all(color: kBorder),
                          ),
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                          child: Row(
                            children: [
                              Text(provider.currency,
                                  style: const TextStyle(fontSize: 22, color: kSubtext)),
                              const SizedBox(width: 8),
                              Expanded(
                                child: TextField(
                                  controller: _amountCtrl,
                                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                  style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: kNavy),
                                  decoration: const InputDecoration(
                                    hintText: '26,000',
                                    hintStyle: TextStyle(color: kBorder, fontSize: 22),
                                    border: InputBorder.none,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                        Row(
                          children: [
                            Expanded(
                              child: OutlinedButton(
                                onPressed: _next,
                                style: OutlinedButton.styleFrom(
                                  foregroundColor: kSubtext,
                                  side: const BorderSide(color: kBorder),
                                  padding: const EdgeInsets.symmetric(vertical: 12),
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                                ),
                                child: const Text('Skip for now'),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              flex: 2,
                              child: ElevatedButton(
                                onPressed: () {
                                  final v = double.tryParse(_amountCtrl.text);
                                  if (v != null && v > 0) provider.setTotalBudget(v);
                                  _next();
                                },
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: kNavy,
                                  foregroundColor: kBackground,
                                  elevation: 0,
                                  padding: const EdgeInsets.symmetric(vertical: 12),
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                                ),
                                child: const Text('Set Budget →', style: TextStyle(fontWeight: FontWeight.w600)),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),

                  // Page 4: Done
                  _OnboardPage(
                    emoji: '🎉',
                    title: "You're all set!",
                    subtitle: 'Come back daily to build your streak.\nEvery entry counts. ✏️',
                    action: _OnboardButton(label: 'Start Journaling →', onTap: _finish),
                  ),
                ],
              ),
            ),

            // Skip link
            if (_page < 3)
              Padding(
                padding: const EdgeInsets.only(bottom: 20),
                child: TextButton(
                  onPressed: _finish,
                  child: const Text('Skip onboarding', style: TextStyle(color: kSubtext, fontSize: 13)),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _OnboardPage extends StatelessWidget {
  final String emoji;
  final String title;
  final String subtitle;
  final Widget action;

  const _OnboardPage({
    required this.emoji,
    required this.title,
    required this.subtitle,
    required this.action,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(emoji, style: const TextStyle(fontSize: 72)),
          const SizedBox(height: 24),
          Text(
            title,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 32, fontWeight: FontWeight.w700, color: kText,
              fontStyle: FontStyle.italic, height: 1.2,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            subtitle,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 15, color: kSubtext, height: 1.5),
          ),
          const SizedBox(height: 40),
          action,
        ],
      ),
    );
  }
}

class _OnboardButton extends StatelessWidget {
  final String label;
  final VoidCallback onTap;
  const _OnboardButton({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton(
        onPressed: onTap,
        style: ElevatedButton.styleFrom(
          backgroundColor: kNavy,
          foregroundColor: kBackground,
          elevation: 0,
          padding: const EdgeInsets.symmetric(vertical: 16),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
        child: Text(label, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
      ),
    );
  }
}

class _CurrencyChip extends StatelessWidget {
  final String symbol;
  final String code;
  final bool selected;
  final VoidCallback onTap;
  const _CurrencyChip({required this.symbol, required this.code, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
        decoration: BoxDecoration(
          color: selected ? kNavy : kCard,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: selected ? kNavy : kBorder, width: selected ? 2 : 1),
        ),
        child: Column(
          children: [
            Text(symbol, style: TextStyle(fontSize: 24, color: selected ? Colors.white : kText)),
            Text(code, style: TextStyle(fontSize: 11, color: selected ? kBackground : kSubtext, fontWeight: FontWeight.w500)),
          ],
        ),
      ),
    );
  }
}
