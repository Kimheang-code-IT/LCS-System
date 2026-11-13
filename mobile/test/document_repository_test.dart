import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lcs_mobile/core/api/api_exception.dart';
import 'package:lcs_mobile/features/documents/data/document_repository.dart';

/// Serves canned responses so repository contracts are tested without a
/// backend: success, auth failures, pagination, and error envelopes.
class FakeAdapter implements HttpClientAdapter {
  FakeAdapter(this.handler);

  final Future<ResponseBody> Function(RequestOptions options) handler;

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) => handler(options);
}

ResponseBody jsonBody(dynamic data, {int statusCode = 200}) => ResponseBody(
  Stream.value(utf8.encode(jsonEncode(data))),
  statusCode,
  headers: {
    Headers.contentTypeHeader: [Headers.jsonContentType],
  },
);

void main() {
  late Dio dio;

  setUp(() {
    dio = Dio(BaseOptions(baseUrl: 'http://localhost:8000'));
  });

  group('DocumentRepository.list', () {
    test(
      'requests the unified financial-documents endpoint with filters',
      () async {
        final paths = <String>[];
        dio.httpClientAdapter = FakeAdapter((options) async {
          paths.add('${options.uri}');
          return jsonBody({
            'data': {
              'items': [
                {
                  'id': 1,
                  'documentNo': 'RCT-1',
                  'documentType': 'CUSTOMER_RECEIPT',
                },
              ],
              'meta': {'total': 1},
            },
          });
        });
        final repo = DocumentRepository(dio);
        final page = await repo.list(
          page: 2,
          documentType: 'CUSTOMER_RECEIPT',
          search: 'acme',
          status: 'POSTED',
          fromDate: '2026-01-01',
          toDate: '2026-01-31',
        );
        expect(page.items.single.documentNo, 'RCT-1');
        expect(page.total, 1);
        expect(paths.single, contains('/api/v1/financial-documents'));
        expect(paths.single, contains('document_type=CUSTOMER_RECEIPT'));
        expect(paths.single, contains('page=2'));
        expect(paths.single, contains('q=acme'));
        expect(paths.single, contains('status=POSTED'));
        expect(paths.single, contains('from_date=2026-01-01'));
      },
    );

    test('propagates server validation errors as typed exceptions', () async {
      dio.httpClientAdapter = FakeAdapter((options) async {
        return jsonBody({
          'code': 'VALIDATION',
          'message': 'Choose an active business party.',
        }, statusCode: 400);
      });
      final repo = DocumentRepository(dio);
      await expectLater(
        repo.list(),
        throwsA(
          predicate(
            (e) => e is ApiException && e.code == ApiException.validation,
          ),
        ),
      );
    });
  });

  group('DocumentRepository.post', () {
    test('posts with an Idempotency-Key header', () async {
      String? idempotencyKey;
      dio.httpClientAdapter = FakeAdapter((options) async {
        idempotencyKey = options.headers['Idempotency-Key'] as String?;
        return jsonBody({
          'data': {'id': 9, 'status': 'POSTED'},
        });
      });
      final repo = DocumentRepository(dio);
      final doc = await repo.post('9');
      expect(idempotencyKey, isNotNull);
      expect(idempotencyKey, isNotEmpty);
      expect(doc.status, 'POSTED');
    });

    test('duplicate posting surfaces a conflict', () async {
      dio.httpClientAdapter = FakeAdapter((options) async {
        return jsonBody({
          'code': 'DUPLICATE_POSTING',
          'message': 'Already posted.',
        }, statusCode: 409);
      });
      final repo = DocumentRepository(dio);
      await expectLater(
        repo.post('9'),
        throwsA(
          predicate(
            (e) => e is ApiException && e.code == ApiException.conflict,
          ),
        ),
      );
    });
  });

  group('DocumentRepository.save', () {
    test('creates with POST and updates with PUT', () async {
      final methods = <String>[];
      dio.httpClientAdapter = FakeAdapter((options) async {
        methods.add(options.method);
        return jsonBody({
          'data': {'id': 5, 'status': 'DRAFT'},
        });
      });
      final repo = DocumentRepository(dio);
      await repo.save({'documentType': 'CUSTOMER_RECEIPT'});
      await repo.save({'documentType': 'CUSTOMER_RECEIPT'}, id: '5');
      expect(methods, ['POST', 'PUT']);
    });
  });

  group('permission failures', () {
    test('403 responses map to FORBIDDEN', () async {
      dio.httpClientAdapter = FakeAdapter((options) async {
        return jsonBody({
          'code': 'ACCESS_DENIED',
          'message': 'You do not have permission.',
        }, statusCode: 403);
      });
      final repo = DocumentRepository(dio);
      await expectLater(
        repo.get('1'),
        throwsA(
          predicate(
            (e) => e is ApiException && e.code == ApiException.forbidden,
          ),
        ),
      );
    });
  });
}
