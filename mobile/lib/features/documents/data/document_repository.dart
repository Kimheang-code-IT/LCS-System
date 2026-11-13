import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import '../../../core/api/api_client.dart';
import '../../../core/auth/session.dart';
import '../../../core/models/paged.dart';
import 'document_models.dart';

/// Repositories for the unified `/api/v1/financial-documents` resource plus the
/// master-data options the create/edit forms need. Endpoint contracts mirror
/// the web app's `freight-remote.ts` mapping — no invented routes.
class DocumentRepository {
  DocumentRepository(this._dio);

  final Dio _dio;

  static const _documents = '/api/v1/financial-documents';

  Future<ApiPage<FinancialDocument>> list({
    int page = 1,
    int pageSize = 20,
    String? documentType,
    String? search,
    String? status,
    String? fromDate,
    String? toDate,
    String sortBy = 'documentDate',
  }) => apiCall(() async {
    final response = await _dio.get<dynamic>(
      _documents,
      queryParameters: {
        'page': page,
        'page_size': pageSize,
        if (documentType != null && documentType.isNotEmpty)
          'document_type': documentType,
        if (search != null && search.isNotEmpty) 'q': search,
        if (status != null && status.isNotEmpty) 'status': status,
        if (fromDate != null && fromDate.isNotEmpty) 'from_date': fromDate,
        if (toDate != null && toDate.isNotEmpty) 'to_date': toDate,
        'sort_by': sortBy,
        'sort_order': 'desc',
      },
    );
    final (:items, :total) = unwrapPage(response);
    return ApiPage.of(items.map(FinancialDocument.fromJson).toList(), total);
  });

  Future<FinancialDocument> get(String id) => apiCall(() async {
    final response = await _dio.get<dynamic>('$_documents/$id');
    final data = unwrapData(response);
    return FinancialDocument.fromJson((data as Map).cast<String, dynamic>());
  });

  /// Creates or updates a draft. The payload matches `DOCUMENT_WRITE_SCHEMA`
  /// plus lines, as the web form posts it.
  Future<FinancialDocument> save(Map<String, dynamic> payload, {String? id}) =>
      apiCall(() async {
        final response = id == null
            ? await _dio.post<dynamic>(_documents, data: payload)
            : await _dio.put<dynamic>('$_documents/$id', data: payload);
        final data = unwrapData(response);
        return FinancialDocument.fromJson(
          (data as Map).cast<String, dynamic>(),
        );
      });

  /// Posts the document with an Idempotency-Key so a retry after a dropped
  /// response can never double-post the journal.
  Future<FinancialDocument> post(String id) => apiCall(() async {
    final response = await _dio.post<dynamic>(
      '$_documents/$id/post',
      data: <String, dynamic>{},
      options: Options(headers: {'Idempotency-Key': const Uuid().v4()}),
    );
    final data = unwrapData(response);
    return FinancialDocument.fromJson((data as Map).cast<String, dynamic>());
  });

  Future<FinancialDocument> reverse(String id, String reason) => apiCall(
    () async {
      final response = await _dio.post<dynamic>(
        '$_documents/$id/reverse',
        data: {'reason': reason},
        options: Options(headers: {'Idempotency-Key': const Uuid().v4()}),
      );
      final data = unwrapData(response);
      return FinancialDocument.fromJson((data as Map).cast<String, dynamic>());
    },
  );

  /// Reconciled print model for CUSTOMER_INVOICE documents.
  Future<Map<String, dynamic>> printData(
    String id, {
    String template = 'tax-invoice',
  }) => apiCall(() async {
    final response = await _dio.get<dynamic>(
      '$_documents/$id/print-data',
      queryParameters: {'template': template},
    );
    return (unwrapData(response) as Map).cast<String, dynamic>();
  });

  /// Party options for selects. Single flat page; the form needs at most a
  /// few hundred active parties — no N+1 list loading.
  Future<List<PartyOption>> parties({String search = ''}) => apiCall(() async {
    final response = await _dio.get<dynamic>(
      '/api/v1/businessParties',
      queryParameters: {
        'page': 1,
        'page_size': 200,
        'status': 'ACTIVE',
        if (search.isNotEmpty) 'q': search,
      },
    );
    return unwrapPage(response).items.map(PartyOption.fromJson).toList();
  });

  Future<List<FinancialAccountOption>> financialAccounts() => apiCall(() async {
    final response = await _dio.get<dynamic>(
      '/api/v1/financial-accounts',
      queryParameters: {'page': 1, 'page_size': 200, 'status': 'ACTIVE'},
    );
    return unwrapPage(
      response,
    ).items.map(FinancialAccountOption.fromJson).toList();
  });
}

final documentRepositoryProvider = Provider<DocumentRepository>(
  (ref) => DocumentRepository(ref.read(apiClientProvider).dio),
);
