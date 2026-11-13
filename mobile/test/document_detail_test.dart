import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lcs_mobile/core/auth/session.dart';
import 'package:lcs_mobile/features/documents/data/document_models.dart';
import 'package:lcs_mobile/features/documents/presentation/document_detail_screen.dart';
import 'package:lcs_mobile/l10n/app_localizations.dart';

class _FakeSession extends SessionController {
  @override
  SessionState build() => SessionState(
    status: SessionStatus.authenticated,
    user: AuthUser(
      id: '1',
      name: 'Admin',
      email: 'a@b.c',
      role: 'SuperAdmin',
      permissions: ['ALL_PAGES'],
    ),
  );
}

class _FakeDetail extends DocumentDetailController {
  _FakeDetail(this._doc);

  final FinancialDocument _doc;

  @override
  AsyncValue<FinancialDocument> build(String arg) => AsyncData(_doc);

  @override
  Future<void> refresh() async {}

  @override
  Future<void> post() async {}

  @override
  Future<void> reverse(String reason) async {}
}

FinancialDocument _postedInvoice() => FinancialDocument.fromJson({
  'id': '1',
  'documentNo': 'INV2026-000001',
  'documentType': 'CUSTOMER_INVOICE',
  'documentDate': '2026-11-13',
  'status': 'POSTED',
  'currency': 'USD',
  'currencyPrecision': 2,
  'total': 1200,
  'paidAmount': 0,
  'balance': 1200,
  'customer': 'Mobile Test Customer',
  'journalNo': 'JE2026-000001',
  'journalEntries': [
    {'account': '1100', 'description': 'AR', 'debit': 1200, 'credit': 0},
    {'account': '4010', 'description': 'Revenue', 'debit': 0, 'credit': 1200},
  ],
  'lines': [
    {
      'description': 'Freight charge',
      'quantity': 1,
      'unitPrice': 1200,
      'discount': 0,
      'taxAmount': 0,
      'amount': 1200,
    },
  ],
});

void main() {
  Widget detail(FinancialDocument doc, {Locale locale = const Locale('en')}) =>
      ProviderScope(
        // Distinct key: consecutive pumpWidget calls with the same widget type
        // would otherwise reuse the previous provider container/state.
        key: ValueKey('detail-${doc.status}-$locale'),
        overrides: [
          sessionProvider.overrideWith(_FakeSession.new),
          documentDetailProvider.overrideWith(() => _FakeDetail(doc)),
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
          home: DocumentDetailScreen(documentId: '1'),
        ),
      );

  testWidgets('English detail shows document, lines and balanced journal', (
    tester,
  ) async {
    await tester.pumpWidget(detail(_postedInvoice()));
    await tester.pumpAndSettle();
    expect(find.text('INV2026-000001'), findsOneWidget);
    expect(find.text('POSTED'), findsOneWidget);
    expect(find.text('JE2026-000001'), findsOneWidget);
    expect(find.text('Freight charge'), findsOneWidget);
    expect(find.text('1100 — AR'), findsOneWidget);
    expect(find.text('4010 — Revenue'), findsOneWidget);
    // USD 1,200.00 formatting with the backend precision (header total, paid,
    // outstanding rows).
    expect(find.text('USD 1,200.00'), findsNWidgets(3));
  });

  testWidgets('Khmer labels render on the detail screen without overflow', (
    tester,
  ) async {
    await tester.pumpWidget(
      detail(_postedInvoice(), locale: const Locale('km')),
    );
    await tester.pumpAndSettle();
    // Khmer ARB labels for the info rows the detail screen renders (label +
    // section header both use the term).
    expect(find.text('អតិថិជន'), findsOneWidget);
    expect(find.text('បញ្ជីទូទៅ'), findsNWidgets(2));
    // The status chip stays machine-readable.
    expect(find.text('POSTED'), findsOneWidget);
    // No layout exceptions (overflow errors would fail the test framework).
    await tester.pumpAndSettle();
  });

  testWidgets('Posted documents offer no post action; drafts do', (
    tester,
  ) async {
    await tester.pumpWidget(detail(_postedInvoice()));
    await tester.pumpAndSettle();
    expect(find.text('Post'), findsNothing);
    expect(find.text('Reverse'), findsOneWidget);

    final draft = _postedInvoice().raw;
    final draftDoc = FinancialDocument.fromJson({...draft, 'status': 'DRAFT'});
    await tester.pumpWidget(detail(draftDoc));
    await tester.pumpAndSettle();
    debugPrint(
      'DEBUG draft texts: '
      '${tester.widgetList<Text>(find.byType(Text)).map((w) => w.data).take(30).toList()}',
    );
    expect(find.text('Post'), findsOneWidget);
    expect(find.text('Reverse'), findsNothing);
  });
}
