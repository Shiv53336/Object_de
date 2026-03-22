class StreakModel {
  final int currentStreak;
  final int longestStreak;
  final String lastLogDate; // YYYY-MM-DD or ''

  const StreakModel({
    this.currentStreak = 0,
    this.longestStreak = 0,
    this.lastLogDate = '',
  });

  Map<String, dynamic> toJson() => {
        'currentStreak': currentStreak,
        'longestStreak': longestStreak,
        'lastLogDate': lastLogDate,
      };

  factory StreakModel.fromJson(Map<String, dynamic> json) => StreakModel(
        currentStreak: json['currentStreak'] as int? ?? 0,
        longestStreak: json['longestStreak'] as int? ?? 0,
        lastLogDate: json['lastLogDate'] as String? ?? '',
      );

  StreakModel copyWith({int? currentStreak, int? longestStreak, String? lastLogDate}) =>
      StreakModel(
        currentStreak: currentStreak ?? this.currentStreak,
        longestStreak: longestStreak ?? this.longestStreak,
        lastLogDate: lastLogDate ?? this.lastLogDate,
      );
}
