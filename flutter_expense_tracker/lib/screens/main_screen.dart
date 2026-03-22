import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_provider.dart';
import '../utils/constants.dart';
import 'home_screen.dart';
import 'stats_screen.dart';
import 'categories_screen.dart';
import 'settings_screen.dart';

class MainScreen extends StatelessWidget {
  const MainScreen({super.key});

  static const _screens = [
    HomeScreen(),
    StatsScreen(),
    CategoriesScreen(),
    SettingsScreen(),
  ];

  static const _navItems = [
    BottomNavigationBarItem(icon: Text('🏠', style: TextStyle(fontSize: 20)), label: 'Home'),
    BottomNavigationBarItem(icon: Text('📊', style: TextStyle(fontSize: 20)), label: 'Stats'),
    BottomNavigationBarItem(icon: Text('🏷️', style: TextStyle(fontSize: 20)), label: 'Categories'),
    BottomNavigationBarItem(icon: Text('⚙️', style: TextStyle(fontSize: 20)), label: 'Settings'),
  ];

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<AppProvider>();

    return Scaffold(
      backgroundColor: kBackground,
      appBar: _AppHeader(),
      body: _screens[provider.selectedTab],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: provider.selectedTab,
        onTap: provider.setSelectedTab,
        type: BottomNavigationBarType.fixed,
        backgroundColor: Colors.white.withOpacity(0.95),
        selectedItemColor: kNavy,
        unselectedItemColor: kSubtext,
        selectedLabelStyle: const TextStyle(fontSize: 10, fontWeight: FontWeight.w600),
        unselectedLabelStyle: const TextStyle(fontSize: 10),
        elevation: 0,
        items: _navItems,
      ),
    );
  }
}

class _AppHeader extends StatelessWidget implements PreferredSizeWidget {
  @override
  Size get preferredSize => const Size.fromHeight(72);

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<AppProvider>();
    final now      = DateTime.now();
    final month    = _monthName(now.month);

    return Container(
      decoration: const BoxDecoration(
        color: kBackground,
        border: Border(bottom: BorderSide(color: kBorder, width: 0.5)),
      ),
      padding: const EdgeInsets.fromLTRB(20, 16, 16, 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Text(
                'My Expenses',
                style: TextStyle(fontSize: 28, fontWeight: FontWeight.w600, color: kText, fontStyle: FontStyle.italic),
              ),
              Text(
                '$month ${now.year}',
                style: const TextStyle(fontSize: 13, color: kSubtext),
              ),
            ],
          ),
          Row(
            children: [
              // Currency dropdown
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: kBorder),
                ),
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<String>(
                    value: provider.currency,
                    isDense: true,
                    style: const TextStyle(fontSize: 14, color: kText),
                    items: kCurrencies.entries.map((e) => DropdownMenuItem(
                      value: e.key,
                      child: Text('${e.key} ${e.value}'),
                    )).toList(),
                    onChanged: (v) { if (v != null) provider.setCurrency(v); },
                  ),
                ),
              ),
              const SizedBox(width: 8),
              // Avatar
              Container(
                width: 36, height: 36,
                decoration: const BoxDecoration(color: kNavy, shape: BoxShape.circle),
                alignment: Alignment.center,
                child: const Text('H', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: kBackground)),
              ),
            ],
          ),
        ],
      ),
    );
  }

  String _monthName(int month) {
    const names = ['January','February','March','April','May','June',
                   'July','August','September','October','November','December'];
    return names[month - 1];
  }
}
