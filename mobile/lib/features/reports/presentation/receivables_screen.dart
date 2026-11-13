import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/widgets/common.dart';
import '../data/reports_repository.dart';

/// Read-only Accounts Receivable list — posted customer invoices with
/// backend-calculated balances (`/api/v1/reports/receivables`).
class ReceivablesScreen extends ConsumerWidget {
  const ReceivablesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final future = ref.watch(arProvider);
    return _ProjectionScaffold(
      title: 'Accounts Receivable',
      future: future,
      onRefresh: () async => ref.invalidate(arProvider),
      emptyMessage: 'No open receivables',
      buildItem: (context, row) => _AgingCard(
        row: row,
        partyKey: 'customer',
        onTap: () =>
            context.push('/document', extra: row['id']?.toString() ?? ''),
      ),
    );
  }
}

/// Read-only Accounts Payable list (`/api/v1/reports/payables`).
class PayablesScreen extends ConsumerWidget {
  const PayablesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final future = ref.watch(apProvider);
    return _ProjectionScaffold(
      title: 'Accounts Payable',
      future: future,
      onRefresh: () async => ref.invalidate(apProvider),
      emptyMessage: 'No open payables',
      buildItem: (context, row) => _AgingCard(
        row: row,
        partyKey: 'supplier',
        onTap: () =>
            context.push('/document', extra: row['id']?.toString() ?? ''),
      ),
    );
  }
}

final arProvider = FutureProvider.autoDispose<List<Map<String, dynamic>>>(
  (ref) => ref.read(reportsRepositoryProvider).receivables(),
);

final apProvider = FutureProvider.autoDispose<List<Map<String, dynamic>>>(
  (ref) => ref.read(reportsRepositoryProvider).payables(),
);

class _ProjectionScaffold extends StatelessWidget {
  const _ProjectionScaffold({
    required this.title,
    required this.future,
    required this.onRefresh,
    required this.buildItem,
    required this.emptyMessage,
  });

  final AsyncValue<List<Map<String, dynamic>>> future;
  final String title;
  final Future<void> Function() onRefresh;
  final Widget Function(BuildContext, Map<String, dynamic>) buildItem;
  final String emptyMessage;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: future.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => ErrorView(
          error: error,
          onRetry: onRefresh,
          messageFor: messageForError,
        ),
        data: (rows) => rows.isEmpty
            ? EmptyView(message: emptyMessage, onRetry: onRefresh)
            : RefreshIndicator(
                onRefresh: onRefresh,
                child: ListView.builder(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  itemCount: rows.length,
                  itemBuilder: (context, index) =>
                      buildItem(context, rows[index]),
                ),
              ),
      ),
    );
  }
}

class _AgingCard extends StatelessWidget {
  const _AgingCard({
    required this.row,
    required this.partyKey,
    required this.onTap,
  });

  final Map<String, dynamic> row;
  final String partyKey;
  final VoidCallback onTap;

  static num _num(Object? value) =>
      value is num ? value : num.tryParse('${value ?? ''}') ?? 0;

  @override
  Widget build(BuildContext context) {
    final currency = row['currency'] as String? ?? '';
    return RecordCard(
      title: row['invoiceNo'] as String? ?? row['documentNo'] as String? ?? '',
      subtitle:
          '${row[partyKey] ?? ''}${(row['jobNo'] as String?)?.isNotEmpty == true ? ' · ${row['jobNo']}' : ''}',
      amount: _num(row['total']),
      currency: currency,
      status: row['status'] as String?,
      trailing: (row['dueDate'] as String?)?.substring(0, 10) ?? '',
      footer: _num(row['balance']) != 0
          ? 'Outstanding ${_num(row['balance'])}${(row['aging'] as String?)?.isNotEmpty == true ? ' · aging ${row['aging']}' : ''}'
          : null,
      onTap: onTap,
    );
  }
}
