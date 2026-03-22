import 'dart:convert';
import 'dart:math';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/expense.dart';
import '../models/expense_category.dart';
import '../models/streak_model.dart';
import '../models/recurring_expense.dart';
import '../utils/constants.dart';

class AppProvider extends ChangeNotifier {
  String _currency = '₹';
  double _totalBudget = kDefaultBudget;
  List<Expense> _expenses = [];
  List<ExpenseCategory> _categories = [];
  List<RecurringExpense> _recurring = [];
  Map<String, String> _dailyNotes = {};
  StreakModel _streak = const StreakModel();
  int _selectedTab = 0;
  bool _loaded = false;
  bool _soundEnabled = true;
  bool _hapticEnabled = true;

  String get currency => _currency;
  double get totalBudget => _totalBudget;
  List<Expense> get expenses => List.unmodifiable(_expenses);
  List<ExpenseCategory> get categories => List.unmodifiable(_categories);
  List<RecurringExpense> get recurring => List.unmodifiable(_recurring);
  Map<String, String> get dailyNotes => Map.unmodifiable(_dailyNotes);
  StreakModel get streak => _streak;
  int get selectedTab => _selectedTab;
  bool get loaded => _loaded;
  bool get soundEnabled => _soundEnabled;
  bool get hapticEnabled => _hapticEnabled;

  double get totalSpent => _expenses
      .where((e) => e.type == 'expense')
      .fold(0.0, (sum, e) => sum + e.amount);

  double get totalIncome => _expenses
      .where((e) => e.type == 'income')
      .fold(0.0, (sum, e) => sum + e.amount);

  double get netBalance => totalIncome - totalSpent;

  AppProvider() {
    _loadFromPrefs();
  }

  Future<void> _loadFromPrefs() async {
    final prefs = await SharedPreferences.getInstance();

    _currency    = prefs.getString('et_currency') ?? '₹';
    _totalBudget = prefs.getDouble('et_budget') ?? kDefaultBudget;
    _soundEnabled  = prefs.getBool('et_sound') ?? true;
    _hapticEnabled = prefs.getBool('et_haptic') ?? true;

    final expensesJson = prefs.getString('et_expenses');
    if (expensesJson != null) {
      final List<dynamic> decoded = jsonDecode(expensesJson);
      _expenses = decoded.map((e) => Expense.fromJson(e as Map<String, dynamic>)).toList();
    }

    final categoriesJson = prefs.getString('et_categories');
    if (categoriesJson != null) {
      final List<dynamic> decoded = jsonDecode(categoriesJson);
      _categories = decoded.map((c) => ExpenseCategory.fromJson(c as Map<String, dynamic>)).toList();
    } else {
      _categories = [
        ...List.from(kDefaultCategories),
        ...List.from(kDefaultIncomeCategories),
      ];
    }

    final recurringJson = prefs.getString('et_recurring');
    if (recurringJson != null) {
      final List<dynamic> decoded = jsonDecode(recurringJson);
      _recurring = decoded.map((r) => RecurringExpense.fromJson(r as Map<String, dynamic>)).toList();
    }

    final notesJson = prefs.getString('et_daily_notes');
    if (notesJson != null) {
      final Map<String, dynamic> decoded = jsonDecode(notesJson);
      _dailyNotes = decoded.map((k, v) => MapEntry(k, v as String));
    }

    final streakJson = prefs.getString('et_streak');
    if (streakJson != null) {
      _streak = StreakModel.fromJson(jsonDecode(streakJson) as Map<String, dynamic>);
    }

    // Check if streak is broken (missed a day)
    _checkStreakOnOpen();

    // Auto-add recurring expenses if due
    _processRecurring();

    _loaded = true;
    notifyListeners();
  }

  void _checkStreakOnOpen() {
    if (_streak.lastLogDate.isEmpty) return;
    final today = todayStr();
    final yesterday = _dateOffset(-1);
    if (_streak.lastLogDate != today && _streak.lastLogDate != yesterday) {
      _streak = _streak.copyWith(currentStreak: 0);
    }
  }

  void _processRecurring() {
    final today = DateTime.now();
    final todayString = todayStr();
    bool changed = false;

    for (int i = 0; i < _recurring.length; i++) {
      final r = _recurring[i];
      if (!r.active) continue;

      bool shouldAdd = false;

      switch (r.frequency) {
        case 'daily':
          shouldAdd = r.lastAdded != todayString;
          break;
        case 'monthly':
          shouldAdd = today.day == r.dayOfMonth && r.lastAdded != todayString;
          break;
        case 'weekly':
          // Add on Mondays
          shouldAdd = today.weekday == DateTime.monday && r.lastAdded != todayString;
          break;
        case 'yearly':
          final lastDate = r.lastAdded.isNotEmpty ? DateTime.tryParse(r.lastAdded) : null;
          shouldAdd = lastDate == null ||
              (today.month == r.dayOfMonth && today.year != lastDate.year);
          break;
      }

      if (shouldAdd) {
        final expense = Expense(
          id: DateTime.now().millisecondsSinceEpoch + i,
          amount: r.amount,
          category: r.category,
          note: r.note,
          date: todayString,
          emoji: r.emoji,
          payment: r.payment,
          type: r.type,
        );
        _expenses.insert(0, expense);
        _recurring[i] = r.copyWith(lastAdded: todayString);
        changed = true;
      }
    }

    if (changed) {
      _saveExpenses();
      _saveRecurring();
    }
  }

  String _dateOffset(int days) {
    final d = DateTime.now().add(Duration(days: days));
    return '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
  }

  // ── Persistence ──────────────────────────────────────────────────────────

  Future<void> _saveExpenses() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('et_expenses', jsonEncode(_expenses.map((e) => e.toJson()).toList()));
  }

  Future<void> _saveCategories() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('et_categories', jsonEncode(_categories.map((c) => c.toJson()).toList()));
  }

  Future<void> _saveRecurring() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('et_recurring', jsonEncode(_recurring.map((r) => r.toJson()).toList()));
  }

  Future<void> _saveStreak() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('et_streak', jsonEncode(_streak.toJson()));
  }

  Future<void> _saveDailyNotes() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('et_daily_notes', jsonEncode(_dailyNotes));
  }

  // ── Settings ─────────────────────────────────────────────────────────────

  Future<void> setCurrency(String currency) async {
    _currency = currency;
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('et_currency', currency);
  }

  Future<void> setTotalBudget(double budget) async {
    _totalBudget = budget;
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble('et_budget', budget);
  }

  Future<void> setSoundEnabled(bool v) async {
    _soundEnabled = v;
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('et_sound', v);
  }

  Future<void> setHapticEnabled(bool v) async {
    _hapticEnabled = v;
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('et_haptic', v);
  }

  // ── Expenses ─────────────────────────────────────────────────────────────

  void addExpense(Expense expense) {
    _expenses.insert(0, expense);
    _updateStreak(expense.date);
    if (_hapticEnabled) HapticFeedback.lightImpact();
    notifyListeners();
    _saveExpenses();
    _saveStreak();
  }

  void updateExpense(Expense updated) {
    final idx = _expenses.indexWhere((e) => e.id == updated.id);
    if (idx == -1) return;
    _expenses[idx] = updated;
    notifyListeners();
    _saveExpenses();
  }

  void deleteExpense(int id) {
    _expenses.removeWhere((e) => e.id == id);
    if (_hapticEnabled) HapticFeedback.mediumImpact();
    notifyListeners();
    _saveExpenses();
  }

  void _updateStreak(String date) {
    final today = todayStr();
    if (date != today) return; // only track today's entries for streak

    if (_streak.lastLogDate == today) return; // already logged today

    int newStreak = _streak.currentStreak;
    if (_streak.lastLogDate == _dateOffset(-1)) {
      // consecutive day
      newStreak += 1;
    } else {
      // new streak
      newStreak = 1;
    }
    final newLongest = newStreak > _streak.longestStreak ? newStreak : _streak.longestStreak;
    _streak = _streak.copyWith(
      currentStreak: newStreak,
      longestStreak: newLongest,
      lastLogDate: today,
    );
  }

  void clearAll() {
    _expenses = [];
    notifyListeners();
    _saveExpenses();
  }

  // ── Categories ───────────────────────────────────────────────────────────

  void addCategory(ExpenseCategory category) {
    _categories.add(category);
    notifyListeners();
    _saveCategories();
  }

  // ── Daily Notes ──────────────────────────────────────────────────────────

  Future<void> saveDailyNote(String date, String note) async {
    _dailyNotes[date] = note;
    notifyListeners();
    await _saveDailyNotes();
  }

  String getDailyNote(String date) => _dailyNotes[date] ?? '';

  // ── Recurring ────────────────────────────────────────────────────────────

  void addRecurring(RecurringExpense r) {
    _recurring.add(r);
    notifyListeners();
    _saveRecurring();
  }

  void updateRecurring(RecurringExpense updated) {
    final idx = _recurring.indexWhere((r) => r.id == updated.id);
    if (idx == -1) return;
    _recurring[idx] = updated;
    notifyListeners();
    _saveRecurring();
  }

  void deleteRecurring(int id) {
    _recurring.removeWhere((r) => r.id == id);
    notifyListeners();
    _saveRecurring();
  }

  // ── Navigation ───────────────────────────────────────────────────────────

  void setSelectedTab(int tab) {
    _selectedTab = tab;
    notifyListeners();
  }

  // ── Helpers ──────────────────────────────────────────────────────────────

  String randomColor() => kRandColors[Random().nextInt(kRandColors.length)];

  Expense buildExpense({
    required double amount,
    required String category,
    required String note,
    required String payment,
    String type = 'expense',
    String? date,
  }) {
    final allCats = [..._categories, ...kDefaultIncomeCategories];
    final catObj = allCats.firstWhere(
      (c) => c.name == category,
      orElse: () => _categories.isNotEmpty ? _categories.first : kDefaultCategories.first,
    );
    return Expense(
      id:       DateTime.now().millisecondsSinceEpoch,
      amount:   amount,
      category: category,
      note:     note.isNotEmpty ? note : category,
      date:     date ?? todayStr(),
      emoji:    catObj.emoji,
      payment:  payment,
      type:     type,
    );
  }
}
