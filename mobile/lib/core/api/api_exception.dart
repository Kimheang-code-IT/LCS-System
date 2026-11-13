import 'dart:convert';

/// Errors raised by the LCS API client, mapped to stable codes the UI can act
/// on. Never leaks stack traces or server internals to the user.
class ApiException implements Exception {
  ApiException({
    required this.code,
    required this.message,
    this.statusCode,
    this.fieldErrors = const {},
  });

  static const network = 'NETWORK';
  static const unauthorized = 'UNAUTHORIZED';
  static const forbidden = 'FORBIDDEN';
  static const notFound = 'NOT_FOUND';
  static const validation = 'VALIDATION';
  static const conflict = 'CONFLICT';
  static const server = 'SERVER';
  static const invalidResponse = 'INVALID_RESPONSE';

  final String code;
  final String message;
  final int? statusCode;
  final Map<String, String> fieldErrors;

  /// The backend answers errors as `{code, message, request_id, field_errors}`;
  /// transport failures and proxies do not, so every branch produces a usable
  /// code and a user-safe message.
  factory ApiException.fromResponse({
    int? statusCode,
    String? body,
    required String fallback,
  }) {
    Map<String, dynamic>? json;
    if (body != null && body.isNotEmpty) {
      try {
        final decoded = jsonDecode(body);
        if (decoded is Map<String, dynamic>) json = decoded;
      } catch (_) {
        json = null;
      }
    }
    // Non-JSON plain-text errors (e.g. middleware responses such as
    // "Invalid host header") still deserve their real message on screen.
    final plainMessage =
        json == null &&
            body != null &&
            body.trim().isNotEmpty &&
            body.trim().length <= 200
        ? body.trim()
        : null;
    return ApiException(
      code: _codeFor(statusCode, json?['code'] as String?),
      message: (json?['message'] as String?) ?? plainMessage ?? fallback,
      statusCode: statusCode,
      fieldErrors: _stringMap(json?['field_errors']),
    );
  }

  static String _codeFor(int? statusCode, String? serverCode) {
    switch (statusCode) {
      case 400:
        return validation;
      case 401:
        return unauthorized;
      case 403:
        return forbidden;
      case 404:
        return notFound;
      case 409:
        return conflict;
      case null:
        return network;
      default:
        return statusCode < 500 ? validation : server;
    }
  }

  static Map<String, String> _stringMap(Object? raw) {
    if (raw is Map) {
      return raw.map((k, v) => MapEntry(k.toString(), v?.toString() ?? ''));
    }
    return {};
  }

  @override
  String toString() => 'ApiException($code): $message';
}
