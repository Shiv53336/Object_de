class RecurringExpense {
  final int id;
  final double amount;
  final String category;
  final String note;
  final String emoji;
  final String payment;
  final String type; // "expense" | "income"
  final String frequency; // "daily" | "weekly" | "monthly" | "yearly"
  final int dayOfMonth; // 1-28 for monthly
  final String lastAdded; // YYYY-MM-DD or ''
  final bool active;

  const RecurringExpense({
    required this.id,
    required this.amount,
    required this.category,
    required this.note,
    required this.emoji,
    required this.payment,
    this.type = 'expense',
    this.frequency = 'monthly',
    this.dayOfMonth = 1,
    this.lastAdded = '',
    this.active = true,
  });

  Map<String, dynamic> toJson() => {
        'id': id,
        'amount': amount,
        'category': category,
        'note': note,
        'emoji': emoji,
        'payment': payment,
        'type': type,
        'frequency': frequency,
        'dayOfMonth': dayOfMonth,
        'lastAdded': lastAdded,
        'active': active,
      };

  factory RecurringExpense.fromJson(Map<String, dynamic> json) => RecurringExpense(
        id: json['id'] as int,
        amount: (json['amount'] as num).toDouble(),
        category: json['category'] as String,
        note: json['note'] as String,
        emoji: json['emoji'] as String? ?? '🔄',
        payment: json['payment'] as String,
        type: json['type'] as String? ?? 'expense',
        frequency: json['frequency'] as String? ?? 'monthly',
        dayOfMonth: json['dayOfMonth'] as int? ?? 1,
        lastAdded: json['lastAdded'] as String? ?? '',
        active: json['active'] as bool? ?? true,
      );

  RecurringExpense copyWith({
    bool? active,
    String? lastAdded,
    double? amount,
    String? category,
    String? note,
    String? emoji,
    String? payment,
    String? type,
    String? frequency,
    int? dayOfMonth,
  }) =>
      RecurringExpense(
        id: id,
        amount: amount ?? this.amount,
        category: category ?? this.category,
        note: note ?? this.note,
        emoji: emoji ?? this.emoji,
        payment: payment ?? this.payment,
        type: type ?? this.type,
        frequency: frequency ?? this.frequency,
        dayOfMonth: dayOfMonth ?? this.dayOfMonth,
        lastAdded: lastAdded ?? this.lastAdded,
        active: active ?? this.active,
      );
}
