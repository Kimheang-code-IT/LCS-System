import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/auth/session.dart';
import '../../../core/widgets/list_scaffold.dart';
import '../features/documents/presentation/document_list_screen.dart';
import '../features/reports/presentation/reports_home_screen.dart';

/// The Finance landing screen: the LCS finance submodules the backend supports.
class FinanceHomeScreen extends ConsumerWidget {
  const FinanceHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(sessionProvider).user;
    return Scaffold(
      appBar: AppBar(title: const Text('Finance')),
      body: ListView(
        padding: const EdgeInsets.all(8),
        children: [
          EntryTile(
            icon: Icons.attach_money,
            title: 'Accounts Receivable',
            subtitle: 'Posted customer invoices and outstanding balances',
            enabled: user?.can('reports.accounts_receivable.view') ?? true,
            onTap: () => context.push('/receivables'),
          ),
          EntryTile(
            icon: Icons.credit_card_off_outlined,
            title: 'Accounts Payable',
            subtitle: 'Posted supplier bills and outstanding balances',
            enabled: user?.can('reports.accounts_payable.view') ?? true,
            onTap: () => context.push('/payables'),
          ),
          EntryTile(
            icon: Icons.receipt_outlined,
            title: 'Customer Receipts',
            subtitle: 'Payments received from customers',
            onTap: () => context.push(
              '/doc-list',
              extra: const DocListArgs(
                type: DocType.customerReceipt,
                title: 'Customer Receipts',
              ),
            ),
          ),
          EntryTile(
            icon: Icons.send_to_mobile_outlined,
            title: 'Supplier Payments',
            subtitle: 'Payments made to suppliers',
            onTap: () => context.push(
              '/doc-list',
              extra: const DocListArgs(
                type: DocType.supplierPayment,
                title: 'Supplier Payments',
              ),
            ),
          ),
          EntryTile(
            icon: Icons.swap_horiz,
            title: 'Financial Documents',
            subtitle: 'All types: income, expenses, transfers, adjustments',
            onTap: () => context.push(
              '/doc-list',
              extra: const DocListArgs(
                type: null,
                title: 'Financial Documents',
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Accounting landing: unified document browser + service charges + journals.
class AccountingHomeScreen extends StatelessWidget {
  const AccountingHomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Accounting')),
      body: ListView(
        padding: const EdgeInsets.all(8),
        children: [
          EntryTile(
            icon: Icons.folder_open,
            title: 'All Documents',
            subtitle: 'Unified financial document browser',
            onTap: () => context.push(
              '/doc-list',
              extra: const DocListArgs(
                type: null,
                title: 'Financial Documents',
              ),
            ),
          ),
          EntryTile(
            icon: Icons.description_outlined,
            title: 'Customer Invoices',
            subtitle: 'Invoices issued to customers',
            onTap: () => context.push(
              '/doc-list',
              extra: const DocListArgs(
                type: DocType.customerInvoice,
                title: 'Customer Invoices',
              ),
            ),
          ),
          EntryTile(
            icon: Icons.request_quote_outlined,
            title: 'Supplier Bills',
            subtitle: 'Bills received from suppliers',
            onTap: () => context.push(
              '/doc-list',
              extra: const DocListArgs(
                type: DocType.supplierBill,
                title: 'Supplier Bills',
              ),
            ),
          ),
          EntryTile(
            icon: Icons.library_add_check_outlined,
            title: 'Credit Notes',
            subtitle: 'Customer and supplier credit notes',
            onTap: () => context.push(
              '/doc-list',
              extra: const DocListArgs(
                type: DocType.creditNote,
                title: 'Credit Notes',
              ),
            ),
          ),
          EntryTile(
            icon: Icons.layers_outlined,
            title: 'Service Charges',
            subtitle: 'One charge with multiple fee lines',
            onTap: () => context.push('/service-charges'),
          ),
          EntryTile(
            icon: Icons.book_outlined,
            title: 'Journal Vouchers',
            subtitle: 'Journal entries (double-entry lines)',
            onTap: () => context.push('/journals'),
          ),
        ],
      ),
    );
  }
}

/// Reports landing: backend-supported financial reports only.
class ReportsHomeEntry extends StatelessWidget {
  const ReportsHomeEntry({super.key});

  @override
  Widget build(BuildContext context) {
    return const ReportsHomeScreen();
  }
}
