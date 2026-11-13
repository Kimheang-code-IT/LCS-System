import 'package:flutter/material.dart';

/// Professional light accounting theme: white surfaces, neutral background,
/// blue primary, rounded cards, subtle borders, minimal shadows.
class AppTheme {
  static const seed = Color(0xFF2563EB);

  /// Decorative status-dot palette for dashboard shortcut tiles.
  static const shortcutGreen = Color(0xFF22C55E);
  static const shortcutOrange = Color(0xFFF97316);
  static const shortcutPink = Color(0xFFEC4899);
  static const shortcutPurple = Color(0xFFA855F7);
  static const shortcutBlue = Color(0xFF3B82F6);
  static const shortcutTeal = Color(0xFF14B8A6);
  static const shortcutIndigo = Color(0xFF6366F1);
  static const shortcutAmber = Color(0xFFF59E0B);
  static const shortcutCyan = Color(0xFF06B6D4);
  static const shortcutDeepPurple = Color(0xFF7C3AED);
  static const shortcutRed = Color(0xFFEF4444);

  static ThemeData light() {
    final scheme = ColorScheme.fromSeed(
      seedColor: seed,
      brightness: Brightness.light,
    );
    final base = ThemeData(useMaterial3: true, colorScheme: scheme);
    return base.copyWith(
      scaffoldBackgroundColor: const Color(0xFFF5F6F8),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.white,
        foregroundColor: Color(0xFF111827),
        elevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: Color(0xFF111827),
          fontSize: 18,
          fontWeight: FontWeight.w600,
        ),
      ),
      cardTheme: CardThemeData(
        color: Colors.white,
        elevation: 0,
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: Color(0xFFE5E7EB)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 12,
          vertical: 12,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: Color(0xFFD1D5DB)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: Color(0xFFD1D5DB)),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(64, 44),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
        ),
      ),
      chipTheme: base.chipTheme.copyWith(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: Colors.white,
        indicatorColor: scheme.primaryContainer,
        labelTextStyle: const WidgetStatePropertyAll(TextStyle(fontSize: 11)),
      ),
    );
  }
}
