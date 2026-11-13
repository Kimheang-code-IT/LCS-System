import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';

/// The authenticated identity as `/api/v1/auth/me` reports it.
class AuthUser {
  AuthUser({
    required this.id,
    required this.name,
    required this.email,
    required this.role,
    this.permissions = const [],
    this.mustChangePassword = false,
  });

  final String id;
  final String name;
  final String email;
  final String role;
  final List<String> permissions;
  final bool mustChangePassword;

  /// Super administrators receive the `ALL_PAGES` wildcard; every specific
  /// page code must also pass, exactly like the web app's guard.
  bool can(String pageCode) =>
      permissions.contains('ALL_PAGES') || permissions.contains(pageCode);

  factory AuthUser.fromJson(Map<String, dynamic> json) => AuthUser(
    id: json['id']?.toString() ?? '',
    name: (json['name'] ?? json['displayName'] ?? '') as String,
    email: json['email'] as String? ?? '',
    role: json['role'] as String? ?? '',
    permissions: (json['permissions'] as List? ?? [])
        .map((e) => e.toString())
        .toList(growable: false),
    mustChangePassword: json['mustChangePassword'] == true,
  );
}

enum SessionStatus { unknown, anonymous, authenticated }

class SessionState {
  const SessionState({required this.status, this.user, this.busy = false});

  final SessionStatus status;
  final AuthUser? user;
  final bool busy;

  SessionState copyWith({SessionStatus? status, AuthUser? user, bool? busy}) =>
      SessionState(
        status: status ?? this.status,
        user: user ?? this.user,
        busy: busy ?? this.busy,
      );
}

/// Owns the LCS session lifecycle: login → me → refresh-on-401 → logout.
class SessionController extends Notifier<SessionState> {
  ApiClient get _api => ref.read(apiClientProvider);

  @override
  SessionState build() => const SessionState(status: SessionStatus.unknown);

  /// Called once at startup: restore token, then verify the session server-side.
  /// A start-up network failure must never crash the app: fall back to the
  /// login screen, where the user retries.
  Future<void> restore() async {
    await _api.restoreTokens();
    try {
      final me = await _me();
      state = me == null
          ? const SessionState(status: SessionStatus.anonymous)
          : SessionState(status: SessionStatus.authenticated, user: me);
    } on DioException {
      state = const SessionState(status: SessionStatus.anonymous);
    }
  }

  /// Local-only fallback used when session restore itself fails.
  Future<void> logoutLocal() async {
    await _api.clearSession();
    state = const SessionState(status: SessionStatus.anonymous);
  }

  Future<void> login({
    required String loginValue,
    required String password,
    required bool rememberMe,
  }) async {
    state = state.copyWith(busy: true);
    try {
      final response = await _api.dio.post<Map<String, dynamic>>(
        '/api/v1/auth/login',
        data: {
          'email': loginValue.contains('@') ? loginValue : null,
          'username': loginValue.contains('@') ? null : loginValue,
          'password': password,
          'remember_me': rememberMe,
        },
        options: Options(extra: {'lcsSkipRefresh': true}),
      );
      await _api.adoptLoginResponse(response);
      final data = response.data?['data'];
      final user = data is Map && data['user'] is Map
          ? AuthUser.fromJson((data['user'] as Map).cast<String, dynamic>())
          : await _me();
      if (user == null) {
        throw ApiException(
          code: ApiException.invalidResponse,
          message: 'Login response was invalid.',
        );
      }
      state = SessionState(status: SessionStatus.authenticated, user: user);
    } on DioException catch (error) {
      final e = mapDioError(error);
      final message = e.code == ApiException.unauthorized
          ? 'Incorrect email/username or password.'
          : e.message;
      throw ApiException(
        code: e.code,
        message: message,
        fieldErrors: e.fieldErrors,
      );
    } finally {
      state = state.copyWith(busy: false);
    }
  }

  Future<AuthUser?> _me() async {
    try {
      final response = await _api.dio.get<Map<String, dynamic>>(
        '/api/v1/auth/me',
        options: Options(extra: {'lcsSkipRefresh': true}),
      );
      final data = response.data?['data'];
      if (data is! Map) return null;
      return AuthUser.fromJson(data.cast<String, dynamic>());
    } on DioException catch (error) {
      final status = error.response?.statusCode;
      if (status == 401 || status == 403) return null;
      rethrow;
    }
  }

  Future<void> logout() async {
    try {
      await _api.dio.post<dynamic>(
        '/api/v1/auth/logout',
        data: <String, dynamic>{},
        options: Options(extra: {'lcsSkipRefresh': true}),
      );
    } on DioException {
      // Logout clears local state even when the backend is unreachable.
    }
    await _api.clearSession();
    state = const SessionState(status: SessionStatus.anonymous);
  }
}

final sessionProvider = NotifierProvider<SessionController, SessionState>(
  SessionController.new,
);

/// Unwraps a paginated `{items, meta}` envelope; throws a typed error on any
/// other shape so callers never operate on half-parsed data.
({List<Map<String, dynamic>> items, int total}) unwrapPage(
  Response<dynamic> response,
) {
  final data = response.data;
  if (data is Map && data['data'] is Map) {
    final payload = data['data'] as Map;
    final items = payload['items'];
    if (items is List) {
      final meta = payload['meta'];
      final total = meta is Map
          ? (meta['total'] as num?) ?? items.length
          : items.length;
      return (
        items: items
            .whereType<Map>()
            .map((e) => e.cast<String, dynamic>())
            .toList(),
        total: total.toInt(),
      );
    }
  }
  throw ApiException(
    code: ApiException.invalidResponse,
    message: 'Unexpected page shape.',
  );
}

/// Unwraps a `{"data": ...}` envelope.
dynamic unwrapData(Response<dynamic> response) {
  final data = response.data;
  if (data is Map && data.containsKey('data')) return data['data'];
  throw ApiException(
    code: ApiException.invalidResponse,
    message: 'Unexpected response shape.',
  );
}

/// Wraps Dio failures into [ApiException] for repository code.
Future<T> apiCall<T>(Future<T> Function() run) async {
  try {
    return await run();
  } on DioException catch (error) {
    throw mapDioError(error);
  }
}
