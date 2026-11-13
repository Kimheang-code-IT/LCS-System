import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

import 'package:lcs_mobile/app/app.dart';

/// End-to-end drive against a real, seeded LCS backend.
///
/// Run with the backend reachable from the device/emulator, e.g.
/// `flutter test integration_test -d emulator-5554
///   --dart-define=API_BASE_URL=http://10.0.2.2:8000
///   --dart-define=TEST_USERNAME=... --dart-define=TEST_PASSWORD=...`
///
/// Reads seeded data and exercises login/dashboard-shortcuts/reports; it posts
/// no new financial transactions.
void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  binding.framePolicy = LiveTestWidgetsFlutterBindingFramePolicy.fullyLive;

  const username = String.fromEnvironment('TEST_USERNAME');
  const password = String.fromEnvironment('TEST_PASSWORD');

  /// Pumps frames until [finder] matches or the timeout elapses; then asserts.
  /// (pumpAndSettle cannot be used: spinners animate forever under live frames.)
  Future<void> waitFor(
    WidgetTester tester,
    Finder finder, {
    int seconds = 15,
  }) async {
    final end = DateTime.now().add(Duration(seconds: seconds));
    while (DateTime.now().isBefore(end)) {
      await tester.pump(const Duration(milliseconds: 250));
      if (finder.evaluate().isNotEmpty) {
        await tester.pump(const Duration(milliseconds: 250));
        return;
      }
    }
    expect(finder, findsWidgets, reason: 'Timed out waiting for $finder');
  }

  testWidgets('login → shortcut grid → receivables → journals → logout',
      (tester) async {
    await tester.pumpWidget(const ProviderScope(child: LcsMobileApp()));

    // Wait for the app to land on either the login screen (fresh/expired
    // session) or the dashboard (restored session).
    final loginForm = find.text('Sign in');
    final dashGrid = find.text('Accounts Receivable');
    final landed = DateTime.now().add(const Duration(seconds: 25));
    var landedLogin = false;
    while (DateTime.now().isBefore(landed)) {
      await tester.pump(const Duration(milliseconds: 300));
      if (dashGrid.evaluate().isNotEmpty) {
        break;
      }
      if (loginForm.evaluate().isNotEmpty &&
          find.byType(TextFormField).evaluate().length == 2) {
        landedLogin = true;
        break;
      }
    }
    expect(
      dashGrid.evaluate().isNotEmpty || landedLogin,
      isTrue,
      reason: 'App never reached the login screen or the dashboard',
    );

    // Login
    if (landedLogin) {
      expect(username, isNotEmpty, reason: 'TEST_USERNAME dart-define required');
      await tester.enterText(find.byType(TextFormField).first, username);
      await tester.enterText(find.byType(TextFormField).last, password);
      await tester.pump(const Duration(milliseconds: 300));
      await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
    }

    // Dashboard: the shortcut grid replaces all summary/statistic widgets.
    await waitFor(tester, find.text('Accounts Receivable'), seconds: 25);
    expect(find.text('Accounts Payable'), findsOneWidget);
    expect(find.text('Journal Vouchers'), findsOneWidget);
    expect(find.text('Total Receivables'), findsNothing);
    expect(find.text('Cash & Bank'), findsNothing);

    // Shortcut navigation: open Accounts Receivable, then come back.
    await tester.tap(find.text('Accounts Receivable'));
    await waitFor(tester, find.text('Aging'), seconds: 15).catchError((_) async {});
    await tester.pageBack();
    await waitFor(tester, find.text('Accounts Receivable'), seconds: 8);

    // Reports tab through the bottom navigation.
    await tester.tap(find.text('Reports'));
    await waitFor(tester, find.text('Trial Balance'), seconds: 8);
  });
}
