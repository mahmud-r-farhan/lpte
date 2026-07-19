"""
LPTE Flutter Plugin — Dart wrapper for the Python core engine.

For production use, this plugin communicates with a Python subprocess
or a compiled native extension via method channels.

Usage:
    final result = await LpteFlutter.analyze('some text', languageCode: 'bn');
    if (result.isToxic) {
        print('Toxic content detected: ${result.severity}');
    }
"""

import 'dart:async';
import 'package:flutter/services.dart';

/// Result of a toxicity analysis.
class LpteResult {
  final bool isToxic;
  final String severity;
  final double confidence;
  final List<String> matchedTerms;

  const LpteResult({
    required this.isToxic,
    required this.severity,
    required this.confidence,
    required this.matchedTerms,
  });

  factory LpteResult.fromMap(Map<dynamic, dynamic> map) {
    return LpteResult(
      isToxic: map['isToxic'] ?? false,
      severity: map['severity'] ?? 'NONE',
      confidence: (map['confidence'] ?? 0.0).toDouble(),
      matchedTerms: List<String>.from(map['matchedTerms'] ?? []),
    );
  }

  @override
  String toString() =>
      'LpteResult(isToxic: $isToxic, severity: $severity, '
      'confidence: $confidence, matchedTerms: $matchedTerms)';
}

/// Flutter plugin for the LPTE toxicity engine.
class LpteFlutter {
  static const MethodChannel _channel = MethodChannel('dev.lpte/flutter');

  static String? _lastError;

  /// Analyze text for toxic content.
  static Future<LpteResult> analyze(
    String text, {
    String languageCode = 'en',
    double threshold = 0.6,
  }) async {
    try {
      final result = await _channel.invokeMethod('analyze', {
        'text': text,
        'languageCode': languageCode,
        'threshold': threshold,
      });
      return LpteResult.fromMap(result);
    } on PlatformException catch (e) {
      _lastError = e.message;
      return const LpteResult(
        isToxic: false,
        severity: 'ERROR',
        confidence: 0.0,
        matchedTerms: [],
      );
    }
  }

  /// Quick check: is the text toxic?
  static Future<bool> isToxic(
    String text, {
    String languageCode = 'en',
    double threshold = 0.6,
  }) async {
    try {
      final result = await _channel.invokeMethod('isToxic', {
        'text': text,
        'languageCode': languageCode,
        'threshold': threshold,
      });
      return result ?? false;
    } on PlatformException catch (e) {
      _lastError = e.message;
      return false;
    }
  }

  /// Sanitize text by replacing toxic parts with a mask character.
  static Future<String> sanitize(
    String text, {
    String languageCode = 'en',
    String mask = '*',
  }) async {
    try {
      final result = await _channel.invokeMethod('sanitize', {
        'text': text,
        'languageCode': languageCode,
        'mask': mask,
      });
      return result ?? text;
    } on PlatformException catch (e) {
      _lastError = e.message;
      return text;
    }
  }

  /// Load a custom language profile from a JSON asset.
  static Future<void> loadCustomProfile({
    required String assetPath,
    required String languageCode,
  }) async {
    try {
      await _channel.invokeMethod('loadCustomProfile', {
        'assetPath': assetPath,
        'languageCode': languageCode,
      });
    } on PlatformException catch (e) {
      _lastError = e.message;
    }
  }

  /// Get the last error message, if any.
  static String? get lastError => _lastError;
}
