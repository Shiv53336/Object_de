import 'package:flutter/material.dart';
import '../widgets/quick_add_widget.dart';
import '../widgets/budget_card_widget.dart';
import '../widgets/category_breakdown_widget.dart';
import '../widgets/weekly_trend_widget.dart';
import '../widgets/expense_list_widget.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          QuickAddWidget(),
          BudgetCardWidget(),
          CategoryBreakdownWidget(),
          WeeklyTrendWidget(),
          ExpenseListWidget(),
          SizedBox(height: 16),
        ],
      ),
    );
  }
}
