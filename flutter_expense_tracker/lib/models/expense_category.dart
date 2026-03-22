class ExpenseCategory {
  final String name;
  final String emoji;
  final String color; // hex e.g. "#E07A5F"
  final double budget;

  ExpenseCategory({
    required this.name,
    required this.emoji,
    required this.color,
    required this.budget,
  });

  Map<String, dynamic> toJson() => {
        'name': name,
        'emoji': emoji,
        'color': color,
        'budget': budget,
      };

  factory ExpenseCategory.fromJson(Map<String, dynamic> json) =>
      ExpenseCategory(
        name: json['name'] as String,
        emoji: json['emoji'] as String,
        color: json['color'] as String,
        budget: (json['budget'] as num).toDouble(),
      );
}
