import 'package:intl/intl.dart';

/// Formats a money value for display.
///
/// shortcut: amounts are already backend-rounded (Numeric(19,4)); the mobile
/// app performs no authoritative arithmetic, so `double` display is safe.
/// Revisit only if the app starts aggregating amounts itself.
String formatMoney(num? amount, {required String currency, int decimals = 2}) {
  final value = amount ?? 0;
  final formatter = NumberFormat.decimalPattern()
    ..minimumFractionDigits = decimals;
  final digits = formatter.format(value);
  return '$currency $digits';
}

String formatDate(String? iso) {
  if (iso == null || iso.isEmpty) return '';
  final date = DateTime.tryParse(iso);
  if (date == null) return iso;
  return DateFormat('dd MMM yyyy').format(date);
}

String formatDateTime(String? iso) {
  if (iso == null || iso.isEmpty) return '';
  final date = DateTime.tryParse(iso);
  if (date == null) return iso;
  return DateFormat('dd MMM yyyy, HH:mm').format(date);
}

/// Document statuses as the API reports them (capitalised or uppercase).
String normalizeStatus(String? raw) => (raw ?? '').toUpperCase();

enum StatusKind { neutral, positive, warning, danger, info }

StatusKind statusKind(String? raw) {
  switch (normalizeStatus(raw)) {
    case 'POSTED':
    case 'PAID':
    case 'ACTIVE':
      return StatusKind.positive;
    case 'PARTIAL':
    case 'OPEN':
      return StatusKind.info;
    case 'DRAFT':
      return StatusKind.neutral;
    case 'REVERSED':
    case 'CANCELLED':
    case 'CLOSED':
      return StatusKind.danger;
    default:
      return StatusKind.neutral;
  }
}

/// Human label for a status; uppercase vocabulary from the backend.
String statusLabel(String? raw, {required String Function(String) t}) {
  switch (normalizeStatus(raw)) {
    case 'DRAFT':
      return t('draft');
    case 'POSTED':
      return t('posted');
    case 'PARTIAL':
      return t('partial');
    case 'OPEN':
      return t('open');
    case 'PAID':
      return t('paidStatus');
    case 'REVERSED':
      return t('reversed');
    default:
      return raw ?? '';
  }
}
