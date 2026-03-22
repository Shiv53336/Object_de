import 'dart:convert';
import 'dart:math';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/expense.dart';
import '../models/expense_category.dart';
import '../utils/constants.dart';

class AppProvider extends ChangeNotifier {
  String _currency = '₹';
  double _totalBudget = kDefaultBudget;
  List<Expense> _expenses = [];
  List<ExpenseCategory> _categories = [];
  int _selectedTab = 0;
  bool _loaded = false;

  String get currency => _currency;
  double get totalBudget => _totalBudget;
  List<Expense> get expenses => List.unmodifiable(_expenses);
  List<ExpenseCategory> get categories => List.unmodifiable(_categories);
  int get selectedTab => _selectedTab;
  bool get loaded => _loaded;
  double get totalSpent => _expenses.fold(0.0, (sum, e) => sum + e.amount);

  AppProvider() {
    _loadFromPrefs();
  }

  Future<void> _loadFromPrefs() async {
    final prefs = await SharedPreferences.getInstance();

    _currency    = prefs.getString('et_currency') ?? '₹';
    _totalBudget = prefs.getDouble('et_budget') ?? kDefaultBudget;

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
      _categories = List.from(kDefaultCategories);
    }

    _loaded = true;
    notifyListeners();
  }

  Future<void> _saveExpenses() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('et_expenses', jsonEncode(_expenses.map((e) => e.toJson()).toList()));
  }

  Future<void> _saveCategories() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('et_categories', jsonEncode(_categories.map((c) => c.toJson()).toList()));
  }

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

  void addExpense(Expense expense) {
    _expenses.insert(0, expense);
    notifyListeners();
    _saveExpenses();
  }

  void deleteExpense(int id) {
    _expenses.removeWhere((e) => e.id == id);
    notifyListeners();
    _saveExpenses();
  }

  void addCategory(ExpenseCategory category) {
    _categories.add(category);
    notifyListeners();
    _saveCategories();
  }

  void clearAll() {
    _expenses = [];
    notifyListeners();
    _saveExpenses();
  }

  void setSelectedTab(int tab) {
    _selectedTab = tab;
    notifyListeners();
  }

  String randomColor() {
    return kRandColors[Random().nextInt(kRandColors.length)];
  }

  Expense buildExpense({
    required double amount,
    required String category,
    required String note,
    required String payment,
  }) {
    final catObj = _categories.firstWhere(
      (c) => c.name == category,
      orElse: () => _categories.isNotEmpty ? _categories.first : kDefaultCategories.first,
    );
    return Expense(
      id:       DateTime.now().millisecondsSinceEpoch,
      amount:   amount,
      category: category,
      note:     note.isNotEmpty ? note : category,
      date:     todayStr(),
      emoji:    catObj.emoji,
      payment:  payment,
    );
  }
}
