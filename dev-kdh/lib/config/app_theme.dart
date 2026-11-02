import 'package:flutter/material.dart';

class AppTheme {
  // Primary Clinical Crimson Colors
  static const Color primaryRed = Color(0xFF8B1515);
  static const Color darkRed = Color(0xFF6B1111);
  static const Color crimson = Color(0xFF991B1B);
  static const Color deepCrimson = Color(0xFF7F1D1D);
  static const Color accentRed = Color(0xFFDC2626);
  static const Color softRedBg = Color(0xFFFEE2E2);
  static const Color borderRed = Color(0xFFFECACA);

  // Background and Surfaces
  static const Color background = Color(0xFFF3F4F6);
  static const Color surface = Colors.white;
  static const Color cardBorder = Color(0xFFE5E7EB);
  static const Color divider = Color(0xFFE5E7EB);

  // Status & Telemetry Colors
  static const Color green = Color(0xFF059669);
  static const Color lightGreen = Color(0xFFD1FAE5);
  static const Color emerald = Color(0xFF10B981);
  static const Color cyan = Color(0xFF0284C7);
  static const Color lightCyan = Color(0xFFE0F2FE);
  static const Color amber = Color(0xFFD97706);
  static const Color lightAmber = Color(0xFFFEF3C7);

  // Text Colors
  static const Color textPrimary = Color(0xFF111827);
  static const Color textSecondary = Color(0xFF4B5563);
  static const Color textMuted = Color(0xFF6B7280);
  static const Color textLight = Color(0xFF9CA3AF);

  // ECG Colors
  static const Color ecgRed = Color(0xFF8B1515);
  static const Color ecgGrid = Color(0xFFF3D2D2);

  static ThemeData get theme {
    return ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: background,
      primaryColor: primaryRed,
      colorScheme: ColorScheme.fromSeed(
        seedColor: primaryRed,
        primary: primaryRed,
        secondary: cyan,
        surface: surface,
      ),
      fontFamily: 'Pretendard',
      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: cardBorder, width: 1),
        ),
      ),
      textTheme: const TextTheme(
        headlineLarge: TextStyle(
          fontSize: 24,
          fontWeight: FontWeight.w800,
          color: textPrimary,
          letterSpacing: -0.5,
        ),
        headlineMedium: TextStyle(
          fontSize: 20,
          fontWeight: FontWeight.w700,
          color: textPrimary,
          letterSpacing: -0.3,
        ),
        titleLarge: TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.w700,
          color: textPrimary,
        ),
        titleMedium: TextStyle(
          fontSize: 15,
          fontWeight: FontWeight.w600,
          color: textPrimary,
        ),
        bodyLarge: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w500,
          color: textPrimary,
        ),
        bodyMedium: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w400,
          color: textSecondary,
        ),
        bodySmall: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w400,
          color: textMuted,
        ),
      ),
    );
  }
}
