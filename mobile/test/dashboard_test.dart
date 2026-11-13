import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:lcs_mobile/core/auth/session.dart';
import 'package:lcs_mobile/features/dashboard/presentation/dashboard_screen.dart';
import 'package:lcs_mobile/features/dashboard/presentation/dashboard_shortcuts.dart';
import 'package:lcs_mobile/l10n/app_localizations.dart';

class _FakeSession extends SessionController {
  _FakeSession(this._permissions);

  final List<String> _permissions;

  @override
  SessionState build() => SessionState(
    status: SessionStatus.authenticated,
    user: AuthUser(
      id: '1',
      name: 'Admin',
      email: 'a@b.c',
      role: 'Tester',
      permissions: _permissions,
    ),
  );
}

Widget _dashboard({
  Locale locale = const Locale('en'),
  List<String> permissions = const ['ALL_PAGES'],
}) {
  return ProviderScope(
    overrides: [
      sessionProvider.overrideWith(() => _FakeSession(permissions)),
    ],
    child: MaterialApp(
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      locale: locale,
      home: const DashboardScreen(),
    ),
  );
}

/// Pumps the dashboard through a real go_router so shortcut navigation can be
/// asserted: tapping "Accounts Receivable" must open its screen.
Widget _dashboardWithRouter({List<String> permissions = const ['ALL_PAGES']}) {
  final router = GoRouter(
    initialLocation: '/dashboard',
    routes: [
      GoRoute(
        path: '/dashboard',
        builder: (context, state) => const DashboardScreen(),
      ),
      GoRoute(
        path: '/receivables',
        builder: (context, state) => const Scaffold(
          key: ValueKey('receivables-target'),
          body: Text('AR SCREEN'),
        ),
      ),
    ],
  );
  return ProviderScope(
    overrides: [
      sessionProvider.overrideWith(() => _FakeSession(permissions)),
    ],
    child: MaterialApp.router(
      routerConfig: router,
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
    ),
  );
}

void main() {
  testWidgets('dashboard has no financial summary cards, cash/bank or stats', (
    tester,
  ) async {
    await tester.pumpWidget(_dashboard());
    await tester.pumpAndSettle();
    expect(find.text('Total Receivables'), findsNothing);
    expect(find.text('Total Payables'), findsNothing);
    expect(find.text('Total Received'), findsNothing);
    expect(find.text('Total Paid'), findsNothing);
    expect(find.text('Cash & Bank'), findsNothing);
    expect(find.textContaining('Backend generated'), findsNothing);
    expect(find.textContaining('per-currency'), findsNothing);
  });

  testWidgets('shortcut grid renders all twelve routes in three columns', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 3.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(_dashboard());
    await tester.pumpAndSettle();

    const labels = [
      'Accounts Receivable',
      'Accounts Payable',
      'Customer Receipts',
      'Supplier Payments',
      'Documents',      'Customer Invoices',
      'Supplier Bills',
      'Credit Notes',
      'Service Charges',
      'Journal Vouchers',
      'Trial Balance',
      'General Ledger',
    ];
    for (final label in labels) {
      expect(
        find.text(label),
        findsOneWidget,
        reason: 'missing shortcut: $label',
      );
    }
    // 12 cards at width/3 on a normal phone width — exactly three columns.
    final card = find.byType(DashboardShortcutCard).first;
    final size = tester.getSize(card);
    final gridWidth = tester.getSize(find.byType(GridView).first).width;
    expect((gridWidth / size.width).round(), 3);
    expect(find.byType(DashboardShortcutCard), findsNWidgets(12));

    tester.view.reset();
  });

  testWidgets('tapping a shortcut navigates to its route', (tester) async {
    await tester.pumpWidget(_dashboardWithRouter());
    await tester.pumpAndSettle();
    await tester.tap(find.text('Accounts Receivable'));
    await tester.pumpAndSettle();
    expect(find.text('AR SCREEN'), findsOneWidget);
  });

  testWidgets('permission-restricted shortcuts are hidden', (tester) async {
    await tester.pumpWidget(
      _dashboard(
        permissions: [
          'reports.accounts_receivable.view',
          'financial_document.read',
        ],
      ),
    );
    await tester.pumpAndSettle();
    // Visible: receivable + the six document lists + receipts/payments.
    expect(find.text('Accounts Receivable'), findsOneWidget);
    expect(find.text('Customer Receipts'), findsOneWidget);
    // Hidden: everything else.
    expect(find.text('Accounts Payable'), findsNothing);
    expect(find.text('Service Charges'), findsNothing);
    expect(find.text('Journal Vouchers'), findsNothing);
    expect(find.text('Trial Balance'), findsNothing);
    expect(find.text('General Ledger'), findsNothing);
    expect(find.byType(DashboardShortcutCard), findsNWidgets(7));
  });

  testWidgets('Khmer labels render without clipping', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 3.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(_dashboard(locale: const Locale('km')));
    await tester.pumpAndSettle();
    expect(find.text('ប្រាក់ត្រូវទទួល'), findsOneWidget);
    expect(find.text('ប្រាក់ត្រូវបង់'), findsOneWidget);
    expect(find.textContaining('តួសាស្ត្រ'), findsOneWidget);
    // No overflow exceptions were thrown during the pump (they would fail
    // the test framework) — labels wrap to two lines instead.
  });

  testWidgets('header exposes the logout action', (tester) async {
    await tester.pumpWidget(_dashboard());
    await tester.pumpAndSettle();
    expect(find.byIcon(Icons.logout_outlined), findsOneWidget);
    await tester.tap(find.byIcon(Icons.logout_outlined));
    await tester.pumpAndSettle();
    // Confirmation dialog appears; cancelling keeps the session.
    expect(find.text('Log out'), findsWidgets);
    await tester.tap(find.text('Cancel').last);
    await tester.pumpAndSettle();
  });
}
