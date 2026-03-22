class Expense {
  final int id;
  final double amount;
  final String category;
  final String note;
  final String date; // YYYY-MM-DD
  final String emoji;
  final String payment;

  Expense({
    required this.id,
    required this.amount,
    required this.category,
    required this.note,
    required this.date,
    required this.emoji,
    required this.payment,
  });

  Map<String, dynamic> toJson() => {
        'id': id,
        'amount': amount,
        'category': category,
        'note': note,
        'date': date,
        'emoji': emoji,
        'payment': payment,
      };

  factory Expense.fromJson(Map<String, dynamic> json) => Expense(
        id: json['id'] as int,
        amount: (json['amount'] as num).toDouble(),
        category: json['category'] as String,
        note: json['note'] as String,
        date: json['date'] as String,
        emoji: json['emoji'] as String,
        payment: json['payment'] as String,
      );
}
