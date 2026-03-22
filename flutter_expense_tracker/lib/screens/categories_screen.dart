import 'package:flutter/material.dart';
import '../widgets/category_breakdown_widget.dart';

class CategoriesScreen extends StatelessWidget {
  const CategoriesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const SingleChildScrollView(
      child: Column(
        children: [
          CategoryBreakdownWidget(),
          SizedBox(height: 16),
        ],
      ),
    );
  }
}
