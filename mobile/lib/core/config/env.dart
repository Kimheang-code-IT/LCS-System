/// Typed build-time configuration. Never store secrets here — only endpoints.
class Env {
  /// Base URL of the existing LCS FastAPI backend (no trailing slash).
  ///
  /// Android emulator: host loopback is 10.0.2.2. Physical devices need a
  /// reachable LAN address. Production uses the HTTPS backend domain.
  static const apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );
}
