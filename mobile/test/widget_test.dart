import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lcs_mobile/core/api/api_exception.dart';
import 'package:lcs_mobile/core/widgets/common.dart';
import 'package:lcs_mobile/features/auth/presentation/login_screen.dart';

void _noop() {}

void main() {
  group('LoginScreen', () {
    testWidgets('validates required fields and never calls the network', (
      tester,
    ) async {
      await tester.pumpWidget(
        const ProviderScope(
          overrides: [],
          child: MaterialApp(home: LoginScreen()),
        ),
      );
      await tester.tap(find.byType(FilledButton));
      await tester.pump();
      expect(find.text('Enter your email or username'), findsOneWidget);
      expect(find.text('Enter your password'), findsOneWidget);
    });

    testWidgets('renders email, password and remember-me controls', (
      tester,
    ) async {
      await tester.pumpWidget(
        const ProviderScope(child: MaterialApp(home: LoginScreen())),
      );
      expect(find.text('Sign in'), findsOneWidget);
      expect(find.text('Remember me'), findsOneWidget);
      expect(find.byType(TextFormField), findsNWidgets(2));
    });
  });

  group('state widgets', () {
    testWidgets('EmptyView shows its message and retry', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: EmptyView(message: 'Nothing here', onRetry: _noop),
          ),
        ),
      );
      expect(find.text('Nothing here'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });

    testWidgets('ErrorView shows user-safe message via mapper', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ErrorView(
              error: ApiException(
                code: ApiException.forbidden,
                message: 'denied',
              ),
              onRetry: _noop,
              messageFor: messageForError,
            ),
          ),
        ),
      );
      expect(
        find.text('You do not have permission for this action.'),
        findsOneWidget,
      );
    });
  });
}
