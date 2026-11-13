import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../core/auth/session.dart';
import '../features/auth/presentation/login_screen.dart';
import '../features/dashboard/presentation/dashboard_screen.dart';
import '../features/documents/presentation/document_detail_screen.dart';
import '../features/documents/presentation/document_form_screen.dart';
import '../features/documents/presentation/document_list_screen.dart';
import '../features/documents/presentation/document_preview_screen.dart';
import '../features/journals/presentation/journals_screen.dart';
import '../features/reports/presentation/receivables_screen.dart';
import '../features/reports/presentation/reports_home_screen.dart';
import '../features/service_charges/presentation/service_charges_screen.dart';
import 'landing_screens.dart';

/// Four primary destinations: Dashboard, Finance, Accounting, Reports.
/// Detail routes live on the root navigator so each tab keeps its state.
class _ShellScaffold extends StatelessWidget {
  const _ShellScaffold({required this.shell});

  final StatefulNavigationShell shell;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: shell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: shell.currentIndex,
        onDestinationSelected: (index) =>
            shell.goBranch(index, initialLocation: index == shell.currentIndex),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.dashboard_outlined),
            selectedIcon: Icon(Icons.dashboard),
            label: 'Dashboard',
          ),
          NavigationDestination(
            icon: Icon(Icons.account_balance_wallet_outlined),
            selectedIcon: Icon(Icons.account_balance_wallet),
            label: 'Finance',
          ),
          NavigationDestination(
            icon: Icon(Icons.account_balance_outlined),
            selectedIcon: Icon(Icons.account_balance),
            label: 'Accounting',
          ),
          NavigationDestination(
            icon: Icon(Icons.summarize_outlined),
            selectedIcon: Icon(Icons.summarize),
            label: 'Reports',
          ),
        ],
      ),
    );
  }
}

class SessionRefresh extends ChangeNotifier {
  void notify() => notifyListeners();
}

/// Builds the app router. [sessionState] must read the live session and
/// [refresh] must be notified whenever the session changes so redirects
/// re-evaluate.
GoRouter buildRouter({
  required SessionState Function() sessionState,
  required SessionRefresh refresh,
}) {
  return GoRouter(
    initialLocation: '/dashboard',
    refreshListenable: refresh,
    redirect: (context, state) {
      final status = sessionState().status;
      final loggingIn = state.matchedLocation == '/login';
      if (status == SessionStatus.anonymous && !loggingIn) {
        return '/login';
      }
      if (status == SessionStatus.authenticated && loggingIn) {
        return '/dashboard';
      }
      return null;
    },
    routes: [
      GoRoute(path: '/login', builder: (context, state) => const LoginScreen()),
      StatefulShellRoute.indexedStack(
        builder: (context, state, shell) => _ShellScaffold(shell: shell),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/dashboard',
                builder: (context, state) => const DashboardScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/finance',
                builder: (context, state) => const FinanceHomeScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/accounting',
                builder: (context, state) => const AccountingHomeScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/reports',
                builder: (context, state) => const ReportsHomeScreen(),
              ),
            ],
          ),
        ],
      ),
      GoRoute(
        path: '/receivables',
        builder: (context, state) => const ReceivablesScreen(),
      ),
      GoRoute(
        path: '/payables',
        builder: (context, state) => const PayablesScreen(),
      ),
      GoRoute(
        path: '/doc-list',
        builder: (context, state) {
          final args = state.extra is DocListArgs
              ? state.extra! as DocListArgs
              : const DocListArgs(type: null, title: 'Financial Documents');
          return DocumentListScreen(type: args.type, title: args.title);
        },
      ),
      GoRoute(
        path: '/document',
        builder: (context, state) =>
            DocumentDetailScreen(documentId: state.extra as String? ?? ''),
      ),
      GoRoute(
        path: '/document-form',
        builder: (context, state) => DocumentFormScreen(
          args: state.extra is DocumentFormArgs
              ? state.extra! as DocumentFormArgs
              : const DocumentFormArgs(documentType: 'CUSTOMER_RECEIPT'),
        ),
      ),
      GoRoute(
        path: '/print',
        builder: (context, state) => DocumentPreviewScreen(
          printData: (state.extra as Map?)?.cast<String, dynamic>() ?? const {},
        ),
      ),
      GoRoute(
        path: '/service-charges',
        builder: (context, state) => const ServiceChargesScreen(),
      ),
      GoRoute(
        path: '/service-charge',
        builder: (context, state) =>
            ServiceChargeDetailScreen(chargeId: state.extra as String? ?? ''),
      ),
      GoRoute(
        path: '/journals',
        builder: (context, state) => const JournalsScreen(),
      ),
      GoRoute(
        path: '/journal',
        builder: (context, state) =>
            JournalDetailScreen(entryId: state.extra as String? ?? ''),
      ),
      GoRoute(
        path: '/report-run',
        builder: (context, state) {
          final args = state.extra is ReportRunArgs
              ? state.extra! as ReportRunArgs
              : const ReportRunArgs(
                  key: 'trial-balance',
                  title: 'Trial Balance',
                  fromDate: '',
                  toDate: '',
                );
          return ReportRunScreen(args: args);
        },
      ),
    ],
  );
}
