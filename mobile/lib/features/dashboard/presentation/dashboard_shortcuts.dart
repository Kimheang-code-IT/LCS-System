import 'package:flutter/material.dart';

import '../../../app/theme.dart';
import '../../documents/presentation/document_list_screen.dart';
import '../../reports/presentation/reports_home_screen.dart';
import '../../../l10n/app_localizations.dart';

/// One dashboard shortcut: icon, localized label, an existing go_router
/// destination and the page permission that gates it. The label/extra pair is
/// typed so no route path or argument shape is duplicated at call sites.
class DashboardShortcut {
  const DashboardShortcut({
    required this.label,
    required this.icon,
    required this.route,
    required this.permission,
    required this.dotColor,
    this.extra,
    this.tab = false,
  });

  /// Localized label, resolved against the active locale.
  final String Function(AppLocalizations t) label;

  final IconData icon;
  final String route;

  /// Page permission code from `/auth/me`; the shortcut is hidden without it.
  final String permission;

  /// Small status dot, purely decorative (matches the reference design).
  final Color dotColor;

  /// `extra` payload for routes that take one (document lists, on-demand reports).
  final Object? extra;

  /// True for the four bottom-navigation branches, which switch tabs via
  /// `go` instead of pushing a page.
  final bool tab;
}

/// Reusable tile widget for the dashboard shortcut grid.
///
/// Uses the ambient [ColorScheme] so it adapts to dark mode, shows touch
/// feedback through [InkWell], exposes a semantic button label, and renders
/// disabled (or is hidden by its parent) when the permission is missing.
class DashboardShortcutCard extends StatelessWidget {
  const DashboardShortcutCard({
    super.key,
    required this.label,
    required this.icon,
    required this.dotColor,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final Color dotColor;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Semantics(
      button: true,
      label: label,
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Stack(
                clipBehavior: Clip.none,
                children: [
                  Container(
                    width: 52,
                    height: 52,
                    decoration: BoxDecoration(
                      color: scheme.primary.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Icon(icon, size: 24, color: scheme.primary),
                  ),
                  Positioned(
                    top: -2,
                    right: -2,
                    child: Container(
                      width: 9,
                      height: 9,
                      decoration: BoxDecoration(
                        color: dotColor,
                        shape: BoxShape.circle,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                label,
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: 11.5,
                  height: 1.15,
                  color: scheme.onSurface,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The centralized shortcut list. Route names and arguments mirror the real
/// go_router configuration in `app/router.dart` — nothing invented.
List<DashboardShortcut> dashboardShortcuts() {
  final today = DateTime.now();
  final yearStart = DateTime(
    today.year,
    1,
    1,
  ).toIso8601String().substring(0, 10);
  final todayIso = today.toIso8601String().substring(0, 10);
  ReportRunArgs reportArgs(String key, String title) => ReportRunArgs(
    key: key,
    title: title,
    fromDate: yearStart,
    toDate: todayIso,
  );

  return [
    DashboardShortcut(
      label: (t) => t.accountsReceivable,
      icon: Icons.receipt_long_outlined,
      route: '/receivables',
      permission: 'reports.accounts_receivable.view',
      dotColor: AppTheme.shortcutGreen,
    ),
    DashboardShortcut(
      label: (t) => t.accountsPayable,
      icon: Icons.credit_card_off_outlined,
      route: '/payables',
      permission: 'reports.accounts_payable.view',
      dotColor: AppTheme.shortcutOrange,
    ),
    DashboardShortcut(
      label: (t) => t.customerReceipts,
      icon: Icons.payments_outlined,
      route: '/doc-list',
      extra: const DocListArgs(
        type: DocType.customerReceipt,
        title: 'Customer Receipts',
      ),
      permission: 'financial_document.read',
      dotColor: AppTheme.shortcutPink,
    ),
    DashboardShortcut(
      label: (t) => t.supplierPayments,
      icon: Icons.send_to_mobile_outlined,
      route: '/doc-list',
      extra: const DocListArgs(
        type: DocType.supplierPayment,
        title: 'Supplier Payments',
      ),
      permission: 'financial_document.read',
      dotColor: AppTheme.shortcutPurple,
    ),
    DashboardShortcut(
      label: (t) => t.documents,
      icon: Icons.folder_open_outlined,
      route: '/doc-list',
      extra: const DocListArgs(type: null, title: 'Financial Documents'),
      permission: 'financial_document.read',
      dotColor: AppTheme.shortcutBlue,
    ),
    DashboardShortcut(
      label: (t) => t.customerInvoices,
      icon: Icons.description_outlined,
      route: '/doc-list',
      extra: const DocListArgs(
        type: DocType.customerInvoice,
        title: 'Customer Invoices',
      ),
      permission: 'financial_document.read',
      dotColor: AppTheme.shortcutTeal,
    ),
    DashboardShortcut(
      label: (t) => t.supplierBills,
      icon: Icons.request_quote_outlined,
      route: '/doc-list',
      extra: const DocListArgs(
        type: DocType.supplierBill,
        title: 'Supplier Bills',
      ),
      permission: 'financial_document.read',
      dotColor: AppTheme.shortcutIndigo,
    ),
    DashboardShortcut(
      label: (t) => t.creditNotes,
      icon: Icons.library_add_check_outlined,
      route: '/doc-list',
      extra: const DocListArgs(type: DocType.creditNote, title: 'Credit Notes'),
      permission: 'financial_document.read',
      dotColor: AppTheme.shortcutAmber,
    ),
    DashboardShortcut(
      label: (t) => t.serviceCharges,
      icon: Icons.layers_outlined,
      route: '/service-charges',
      permission: 'service_charge.read',
      dotColor: AppTheme.shortcutCyan,
    ),
    DashboardShortcut(
      label: (t) => t.journals,
      icon: Icons.book_outlined,
      route: '/journals',
      permission: 'journal_entry.read',
      dotColor: AppTheme.shortcutDeepPurple,
    ),
    DashboardShortcut(
      label: (t) => t.trialBalance,
      icon: Icons.balance_outlined,
      route: '/report-run',
      extra: reportArgs('trial-balance', 'Trial Balance'),
      permission: 'reports.trial_balance.view',
      dotColor: AppTheme.shortcutRed,
    ),
    DashboardShortcut(
      label: (t) => t.generalLedger,
      icon: Icons.format_list_bulleted_outlined,
      route: '/report-run',
      extra: reportArgs('general-ledger', 'General Ledger'),
      permission: 'reports.general_ledger.view',
      dotColor: AppTheme.shortcutBlue,
    ),
  ];
}
