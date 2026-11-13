import 'package:flutter_test/flutter_test.dart';
import 'package:lcs_mobile/core/utils/format.dart';

void main() {
  group('formatMoney', () {
    test('formats with currency prefix and two decimals', () {
      expect(formatMoney(1234.5, currency: 'USD'), 'USD 1,234.50');
    });

    test('handles zero and negative amounts', () {
      expect(formatMoney(0, currency: 'KHR'), 'KHR 0.00');
      expect(formatMoney(-10, currency: 'USD'), 'USD -10.00');
    });

    test('supports a different decimal count', () {
      expect(
        formatMoney(1.23456, currency: 'USD', decimals: 4),
        contains('1.2346'),
      );
    });

    test('null amount renders as zero', () {
      expect(formatMoney(null, currency: 'USD'), 'USD 0.00');
    });
  });

  group('dates', () {
    test('formatDate renders ISO dates', () {
      expect(formatDate('2026-02-03'), '03 Feb 2026');
    });

    test('formatDate passes through empty and invalid values', () {
      expect(formatDate(null), '');
      expect(formatDate(''), '');
      expect(formatDate('not-a-date'), 'not-a-date');
    });

    test('formatDateTime includes time', () {
      expect(formatDateTime('2026-02-03T14:30:00'), contains('14:30'));
    });
  });

  group('status mapping', () {
    test('kind maps to colors semantically', () {
      expect(statusKind('POSTED'), StatusKind.positive);
      expect(statusKind('DRAFT'), StatusKind.neutral);
      expect(statusKind('REVERSED'), StatusKind.danger);
      expect(statusKind('PARTIAL'), StatusKind.info);
      expect(statusKind('OPEN'), StatusKind.info);
      expect(statusKind('PAID'), StatusKind.positive);
      expect(statusKind('WHATEVER'), StatusKind.neutral);
      expect(statusKind(null), StatusKind.neutral);
    });

    test('labels map through the localization keys', () {
      expect(statusLabel('DRAFT', t: (key) => key), 'draft');
      expect(statusLabel('POSTED', t: (key) => key), 'posted');
      expect(statusLabel('draft', t: (key) => key), 'draft');
      expect(statusLabel('UNKNOWN', t: (key) => key), 'UNKNOWN');
    });
  });
}
