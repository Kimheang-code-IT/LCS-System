import 'dart:convert';

import 'package:cookie_jar/cookie_jar.dart';
import 'package:dio/dio.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../config/env.dart';
import 'api_exception.dart';

/// One Dio client for the whole app, wired to the existing LCS backend:
///
/// * HttpOnly cookie session (`access_token`, `refresh_token`, `XSRF-TOKEN`),
///   exactly like the web SPA — persisted through a secure-storage cookie jar;
/// * Bearer fallback with the access token returned by the login response
///   (bearer requests skip the backend's CSRF double-submit check);
/// * `X-CSRF-Token` header derived from the `XSRF-TOKEN` cookie for cookie-mode
///   mutations, matching what the web app sends;
/// * one transparent token refresh on 401, then a single retry — a non-idempotent
///   financial write is never silently replayed more than once.
class ApiClient {
  ApiClient({FlutterSecureStorage? storage})
    : _secure = storage ?? const FlutterSecureStorage() {
    dio = Dio(
      BaseOptions(
        baseUrl: Env.apiBaseUrl,
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 30),
        headers: {'Accept': 'application/json'},
        // Default validateStatus: 4xx (including 401) must reach the error
        // interceptor so the session can be refreshed and the request replayed.
        responseType: ResponseType.json,
      ),
    );
    final jar = PersistCookieJar(
      persistSession: true,
      storage: SecureCookieStorage(_secure),
    );
    dio.interceptors.add(CookieManager(jar));
    dio.interceptors.add(
      InterceptorsWrapper(onRequest: _onRequest, onError: _onError),
    );
    _jar = jar;
  }

  final FlutterSecureStorage _secure;
  late final PersistCookieJar _jar;
  late final Dio dio;

  static const _accessTokenKey = 'lcs.access_token';
  String? _accessToken;

  String? get accessToken => _accessToken;

  Future<void> storeTokens({required String accessToken}) async {
    _accessToken = accessToken;
    await _secure.write(key: _accessTokenKey, value: accessToken);
  }

  Future<void> restoreTokens() async {
    _accessToken = await _secure.read(key: _accessTokenKey);
  }

  Future<void> clearSession() async {
    _accessToken = null;
    await _secure.delete(key: _accessTokenKey);
    await _jar.deleteAll();
  }

  /// The login response also carries `access_token` when the backend returns
  /// tokens; persist it so a cold start can authenticate before the first
  /// cookie refresh.
  Future<void> adoptLoginResponse(Response<dynamic> response) async {
    final data = (response.data as Map?)?['data'];
    final token = data is Map ? data['access_token'] as String? : null;
    if (token != null && token.isNotEmpty) {
      await storeTokens(accessToken: token);
    }
  }

  Future<void> _onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    if (_accessToken != null) {
      options.headers['Authorization'] = 'Bearer $_accessToken';
    }
    final csrf = await _csrfFromJar();
    if (csrf != null) options.headers['X-CSRF-Token'] = csrf;
    handler.next(options);
  }

  Future<String?> _csrfFromJar() async {
    final cookies = await _jar.loadForRequest(Uri.parse(Env.apiBaseUrl));
    for (final cookie in cookies) {
      final value = cookie.value;
      if (cookie.name == 'XSRF-TOKEN' && value.isNotEmpty) {
        return value;
      }
    }
    return null;
  }

  Future<void> _onError(
    DioException error,
    ErrorInterceptorHandler handler,
  ) async {
    final path = error.requestOptions.uri.toString();
    final isAuthCall =
        path.contains('/auth/refresh') || path.contains('/auth/login');
    if (error.response?.statusCode == 401 && !isAuthCall) {
      final retry = await _refreshAndRetry(error.requestOptions);
      if (retry != null) {
        handler.resolve(retry);
        return;
      }
    }
    handler.next(error);
  }

  /// POST /api/v1/auth/refresh rotates the refresh cookie and returns a new
  /// access token; the original request is replayed exactly once.
  Future<Response<dynamic>?> _refreshAndRetry(RequestOptions original) async {
    try {
      final response = await dio.post<dynamic>(
        '/api/v1/auth/refresh',
        data: <String, dynamic>{},
        options: Options(extra: {'lcsSkipRefresh': true}),
      );
      final data = (response.data as Map?)?['data'];
      final token = data is Map ? data['access_token'] as String? : null;
      if (token == null || token.isEmpty) return null;
      await storeTokens(accessToken: token);
      original.headers['Authorization'] = 'Bearer $token';
      return await dio.fetch<dynamic>(original);
    } on DioException {
      return null;
    }
  }
}

/// cookie_jar Storage backed by the device-encrypted secure store, so the
/// HttpOnly session survives an app restart without plaintext prefs.
class SecureCookieStorage extends Storage {
  SecureCookieStorage(this._secure);

  final FlutterSecureStorage _secure;

  @override
  Future<void> init(bool persistSession, bool ignoreExpires) async {}

  @override
  Future<String?> read(String key) => _secure.read(key: key);

  @override
  Future<void> write(String key, String value) =>
      _secure.write(key: key, value: value);

  @override
  Future<void> delete(String key) => _secure.delete(key: key);

  @override
  Future<void> deleteAll(List<String> keys) async {
    for (final key in keys) {
      await _secure.delete(key: key);
    }
  }
}

/// Maps any transport-level failure into a user-safe [ApiException].
ApiException mapDioError(Object error) {
  if (error is ApiException) return error;
  if (error is DioException) {
    final response = error.response;
    final data = response?.data;
    final body = data is String
        ? data
        : data is Map
        ? jsonEncode(data)
        : null;
    const fallback = 'No connection. Check your network and try again.';
    return ApiException.fromResponse(
      statusCode: response?.statusCode,
      body: body,
      fallback: fallback,
    );
  }
  return ApiException(
    code: ApiException.network,
    message: fallbackNetworkMessage,
  );
}

const fallbackNetworkMessage =
    'No connection. Check your network and try again.';

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());
