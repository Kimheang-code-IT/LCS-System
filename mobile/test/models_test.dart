import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lcs_mobile/core/api/api_client.dart';
import 'package:lcs_mobile/core/api/api_exception.dart';
import 'package:lcs_mobile/core/auth/session.dart';
import 'package:lcs_mobile/core/models/paged.dart';
import 'package:lcs_mobile/features/documents/data/document_models.dart';

FinancialDocument _doc(Map<String, dynamic> extra) =>
    FinancialDocument.fromJson({
      'id': 7,
      'documentNo': 'INV-000007',
      'documentType': 'CUSTOMER_INVOICE',
      'documentDate': '2026-01-15',
      'status': 'POSTED',
      'currency': 'USD',
      'total': 150.5,
      'paidAmount': 50,
      'balance': 100.5,
      'lines': [
        {
          'description': 'Freight',
          'quantity': 2,
          'unitPrice': 75,
          'discount': 0,
          'taxAmount': 0.5,
          'amount': 150.5,
        },
      ],
      'allocations': [
        {
          'amount': 50,
          'appliedAmount': 50,
          'appliedCurrency': 'USD',
          'allocatedAt': '2026-01-20T08:00:00',
          'targetDocumentNo': 'RCT-000003',
        },
      ],
      'journalEntries': [
        {'account': '1100', 'description': 'AR', 'debit': 150.5, 'credit': 0},
      ],
      ...extra,
    });

void main() {
  group('FinancialDocument parsing', () {
    test('parses the document_payload envelope keys', () {
      final doc = _doc({'customer': 'ACME', 'jobNo': 'SO-0001'});
      expect(doc.id, '7');
      expect(doc.documentNo, 'INV-000007');
      expect(doc.total, 150.5);
      expect(doc.balance, 100.5);
      expect(doc.isPosted, isTrue);
      expect(doc.customer, 'ACME');
      expect(doc.lines.single.amount, 150.5);
      expect(doc.allocations.single.targetDocumentNo, 'RCT-000003');
      expect(doc.journalEntries.single.account, '1100');
    });

    test('amounts fall back to zero on junk', () {
      final doc = _doc({'total': 'not-a-number'});
      expect(doc.total, 0);
    });

    test('draft detection', () {
      expect(_doc({'status': 'DRAFT'}).isDraft, isTrue);
      expect(_doc({'status': 'Draft'}).isDraft, isTrue);
    });
  });

  group('pagination envelope', () {
    Response<dynamic> response(dynamic data) => Response<dynamic>(
      requestOptions: RequestOptions(path: '/x'),
      data: data,
    );

    test('unwrapPage reads items and meta.total', () {
      final (:items, :total) = unwrapPage(
        response({
          'data': {
            'items': [
              {'id': 1},
              {'id': 2},
            ],
            'meta': {'page': 1, 'page_size': 50, 'total': 99},
          },
        }),
      );
      expect(items.length, 2);
      expect(total, 99);
    });

    test('unwrapPage throws on unexpected shapes', () {
      expect(
        () => unwrapPage(response({'data': 'scalar'})),
        throwsA(isA<ApiException>()),
      );
      expect(
        () => unwrapPage(response('plain body')),
        throwsA(isA<ApiException>()),
      );
    });

    test('unwrapData unwraps the data envelope', () {
      expect(
        unwrapData(
          response({
            'data': {'id': 1},
          }),
        ),
        {'id': 1},
      );
    });

    test('ApiPage.hasMore reflects the total', () {
      expect(ApiPage.of([1, 2], 2).hasMore, isFalse);
      expect(ApiPage.of([1], 2).hasMore, isTrue);
    });
  });

  group('error mapping', () {
    test('network failures map to NETWORK with a user-safe message', () {
      final error = mapDioError(
        DioException(
          requestOptions: RequestOptions(path: '/x'),
          type: DioExceptionType.connectionError,
        ),
      );
      expect(error.code, ApiException.network);
      expect(error.message, isNot(contains('DioException')));
    });

    test('backend error bodies map to codes and field errors', () {
      final error = mapDioError(
        DioException(
          requestOptions: RequestOptions(path: '/x'),
          type: DioExceptionType.badResponse,
          response: Response(
            requestOptions: RequestOptions(path: '/x'),
            statusCode: 409,
            data: {
              'code': 'PERIOD_CLOSED',
              'message': 'The accounting period is not open.',
              'field_errors': {'documentDate': 'Bad date'},
            },
          ),
        ),
      );
      expect(error.code, ApiException.conflict);
      expect(error.message, contains('accounting period'));
      expect(error.fieldErrors['documentDate'], 'Bad date');
    });

    test('403 maps to permission denied, 401 to session', () {
      final forbidden = mapDioError(
        DioException(
          requestOptions: RequestOptions(path: '/x'),
          type: DioExceptionType.badResponse,
          response: Response(
            requestOptions: RequestOptions(path: '/x'),
            statusCode: 403,
          ),
        ),
      );
      expect(forbidden.code, ApiException.forbidden);

      final unauthorized = mapDioError(
        DioException(
          requestOptions: RequestOptions(path: '/x'),
          type: DioExceptionType.badResponse,
          response: Response(
            requestOptions: RequestOptions(path: '/x'),
            statusCode: 401,
          ),
        ),
      );
      expect(unauthorized.code, ApiException.unauthorized);
    });
  });

  group('auth user', () {
    test('parses /auth/me payload and permission checks', () {
      final user = AuthUser.fromJson({
        'id': 3,
        'name': 'Moeng',
        'email': 'a@b.c',
        'role': 'Accountant',
        'permissions': [
          'financial_document.read',
          'reports.accounts_receivable.view',
        ],
      });
      expect(user.can('financial_document.read'), isTrue);
      expect(user.can('financial_document.submit'), isFalse);
    });
  });
}
