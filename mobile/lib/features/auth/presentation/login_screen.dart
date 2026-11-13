import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/auth/session.dart';
import '../../../core/widgets/common.dart';

/// Login against the existing LCS `/api/v1/auth/login` contract: username or
/// email + password, with the same error surfaces as the web app.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _loginController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _rememberMe = false;
  bool _obscure = true;
  String? _error;

  @override
  void dispose() {
    _loginController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _error = null);
    try {
      await ref
          .read(sessionProvider.notifier)
          .login(
            loginValue: _loginController.text.trim(),
            password: _passwordController.text,
            rememberMe: _rememberMe,
          );
      // Router listens to the session and lands on the dashboard.
    } on ApiException catch (error) {
      // Inline, persistent error: a snack bar disappears before the user
      // finishes reading why the sign-in failed.
      if (mounted) setState(() => _error = error.message);
    } catch (error) {
      // Unexpected failure type — surface it in the same inline slot in debug
      // builds so a wrong base URL or proxy is diagnosable on-device.
      if (mounted) {
        setState(() => _error = messageForError(error));
      }
      if (kDebugMode) {
        // ignore: avoid_print
        print('LOGIN FAILED: ${error.runtimeType} $error');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final busy = ref.watch(sessionProvider.select((s) => s.busy));
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Icon(Icons.local_shipping_outlined, size: 44),
                    const SizedBox(height: 8),
                    const Text(
                      'LCS Finance',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const Text(
                      'Finance & Accounting mobile client',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 13, color: Colors.grey),
                    ),
                    const SizedBox(height: 28),
                    TextFormField(
                      controller: _loginController,
                      autofillHints: const [
                        AutofillHints.username,
                        AutofillHints.email,
                      ],
                      decoration: const InputDecoration(
                        labelText: 'Email or username',
                      ),
                      textInputAction: TextInputAction.next,
                      validator: (value) =>
                          (value == null || value.trim().isEmpty)
                          ? 'Enter your email or username'
                          : null,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _passwordController,
                      obscureText: _obscure,
                      autofillHints: const [AutofillHints.password],
                      decoration: InputDecoration(
                        labelText: 'Password',
                        suffixIcon: IconButton(
                          icon: Icon(
                            _obscure ? Icons.visibility_off : Icons.visibility,
                          ),
                          onPressed: () => setState(() => _obscure = !_obscure),
                        ),
                      ),
                      textInputAction: TextInputAction.done,
                      onFieldSubmitted: (_) => _submit(),
                      validator: (value) => (value == null || value.isEmpty)
                          ? 'Enter your password'
                          : null,
                    ),
                    const SizedBox(height: 8),
                    CheckboxListTile(
                      value: _rememberMe,
                      onChanged: (value) =>
                          setState(() => _rememberMe = value ?? false),
                      title: const Text('Remember me'),
                      controlAffinity: ListTileControlAffinity.leading,
                      contentPadding: EdgeInsets.zero,
                    ),
                    const SizedBox(height: 8),
                    if (_error != null) ...[
                      Text(
                        _error!,
                        style: TextStyle(
                          color: Colors.red.shade700,
                          fontSize: 13,
                        ),
                      ),
                      const SizedBox(height: 8),
                    ],
                    FilledButton(
                      onPressed: busy ? null : _submit,
                      child: busy
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Text('Sign in'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
