import 'package:flutter/material.dart';
import '../widgets/budget_card_widget.dart';
import '../widgets/weekly_trend_widget.dart';
import '../widgets/category_breakdown_widget.dart';

class StatsScreen extends StatelessWidget {
  const StatsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const SingleChildScrollView(
      child: Column(
        children: [
          BudgetCardWidget(),
          WeeklyTrendWidget(),
          CategoryBreakdownWidget(),
          SizedBox(height: 16),
        ],
      ),
    );
  }
}
