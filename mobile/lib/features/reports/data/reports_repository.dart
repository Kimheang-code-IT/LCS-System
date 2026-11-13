import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/auth/session.dart';

/// Dashboard summary straight from `/api/v1/reports/dashboard` — the four
/// card values come from the backend, which also powers the web dashboard.
class DashboardSummary {
  const DashboardSummary({
    required this.receivables,
    required this.payables,
    required this.totalReceived,
    required this.totalPaid,
    required this.cashBankBalance,
    required this.generatedAt,
    this.receivablesByCurrency = const {},
    this.payablesByCurrency = const {},
    this.totalReceivedByCurrency = const {},
    this.totalPaidByCurrency = const {},
  });

  final num receivables;
  final num payables;
  final num totalReceived;
  final num totalPaid;
  final num cashBankBalance;
  final String generatedAt;

  /// Per-currency composition of the four totals. The headline values sum
  /// document-currency amounts (the web app's convention), so a multi-currency
  /// deployment reads the split instead of adding mixed units.
  final Map<String, num> receivablesByCurrency;
  final Map<String, num> payablesByCurrency;
  final Map<String, num> totalReceivedByCurrency;
  final Map<String, num> totalPaidByCurrency;

  /// True when any card total mixes more than one currency.
  bool get mixedCurrencies => {
    'receivables': receivablesByCurrency,
    'payables': payablesByCurrency,
    'received': totalReceivedByCurrency,
    'paid': totalPaidByCurrency,
  }.values.any(_hasMultipleNonZero);

  static bool _hasMultipleNonZero(Map<String, num> breakdown) {
    final nonZero = breakdown.values.where((v) => v != 0).length;
    return nonZero > 1 || (nonZero == 1 && breakdown.length > 1);
  }

  static num _num(Object? value) =>
      value is num ? value : num.tryParse('${value ?? ''}') ?? 0;

  static Map<String, num> _currencyMap(Object? raw) {
    if (raw is Map) {
      return raw.map((k, v) => MapEntry(k.toString(), _num(v)));
    }
    return {};
  }

  factory DashboardSummary.fromJson(Map<String, dynamic> json) {
    final summary =
        (json['summary'] as Map?)?.cast<String, dynamic>() ?? const {};
    return DashboardSummary(
      receivables: _num(summary['receivables']),
      payables: _num(summary['payables']),
      totalReceived: _num(summary['totalReceived']),
      totalPaid: _num(summary['totalPaid']),
      cashBankBalance: _num(summary['cashBankBalance']),
      generatedAt: json['generatedAt'] as String? ?? '',
      receivablesByCurrency: _currencyMap(summary['receivablesByCurrency']),
      payablesByCurrency: _currencyMap(summary['payablesByCurrency']),
      totalReceivedByCurrency: _currencyMap(summary['totalReceivedByCurrency']),
      totalPaidByCurrency: _currencyMap(summary['totalPaidByCurrency']),
    );
  }
}

class ReportsRepository {
  ReportsRepository(this._dio);

  final Dio _dio;

  Future<DashboardSummary> dashboard() => apiCall(() async {
    final response = await _dio.get<dynamic>(
      '/api/v1/reports/dashboard',
      queryParameters: {'granularity': 'month'},
    );
    final data = unwrapData(response);
    return DashboardSummary.fromJson((data as Map).cast<String, dynamic>());
  });

  /// Read-only AR projection: posted customer invoices with backend balances.
  Future<List<Map<String, dynamic>>> receivables() =>
      _projection('/api/v1/reports/receivables');

  Future<List<Map<String, dynamic>>> payables() =>
      _projection('/api/v1/reports/payables');

  Future<List<Map<String, dynamic>>> _projection(String path) =>
      apiCall(() async {
        final response = await _dio.get<dynamic>(path);
        final data = unwrapData(response);
        if (data is List) {
          return data
              .whereType<Map>()
              .map((e) => e.cast<String, dynamic>())
              .toList();
        }
        throw ApiException(
          code: ApiException.invalidResponse,
          message: 'Unexpected report shape.',
        );
      });

  /// On-demand report generation (POST generate endpoints).
  Future<Map<String, dynamic>> generate(
    String key,
    Map<String, dynamic> filters,
  ) => apiCall(() async {
    final response = await _dio.post<dynamic>(
      '/api/v1/reports/$key/generate',
      data: filters,
    );
    return (unwrapData(response) as Map).cast<String, dynamic>();
  });

  /// CSV export stream for trial-balance / general-ledger.
  Future<List<int>> exportCsv(String key, Map<String, dynamic> filters) =>
      apiCall(() async {
        final response = await _dio.post<List<int>>(
          '/api/v1/reports/$key/export',
          data: filters,
          options: Options(responseType: ResponseType.bytes),
        );
        return response.data ?? const [];
      });
}

final reportsRepositoryProvider = Provider<ReportsRepository>(
  (ref) => ReportsRepository(ref.read(apiClientProvider).dio),
);
