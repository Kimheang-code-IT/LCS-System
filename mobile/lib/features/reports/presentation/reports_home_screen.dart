import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:share_plus/share_plus.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/auth/session.dart';
import '../../../core/widgets/common.dart';
import '../../../core/widgets/list_scaffold.dart';
import '../../reports/data/reports_repository.dart';

/// Reports landing: only the financial reports the backend implements.
class ReportsHomeScreen extends ConsumerWidget {
  const ReportsHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(sessionProvider).user;
    return Scaffold(
      appBar: AppBar(title: const Text('Reports')),
      body: ListView(
        padding: const EdgeInsets.all(8),
        children: [
          EntryTile(
            icon: Icons.receipt_long,
            title: 'Receivables Report',
            subtitle: 'Aging and balances of posted customer invoices',
            enabled: user?.can('reports.accounts_receivable.view') ?? true,
            onTap: () => context.push('/receivables'),
          ),
          EntryTile(
            icon: Icons.credit_card_off_outlined,
            title: 'Payables Report',
            subtitle: 'Aging and balances of posted supplier bills',
            enabled: user?.can('reports.accounts_payable.view') ?? true,
            onTap: () => context.push('/payables'),
          ),
          EntryTile(
            icon: Icons.balance_outlined,
            title: 'Trial Balance',
            subtitle: 'Debit/credit movement per account (on-demand)',
            enabled: user?.can('reports.trial_balance.view') ?? true,
            onTap: () => _open(context, 'trial-balance', 'Trial Balance'),
          ),
          EntryTile(
            icon: Icons.format_list_bulleted,
            title: 'General Ledger',
            subtitle: 'Posted ledger lines with running balances (on-demand)',
            enabled: user?.can('reports.general_ledger.view') ?? true,
            onTap: () => _open(context, 'general-ledger', 'General Ledger'),
          ),
        ],
      ),
    );
  }

  void _open(BuildContext context, String key, String title) {
    final today = DateTime.now();
    final args = ReportRunArgs(
      key: key,
      title: title,
      // Default window: this calendar year, like the web report pages.
      fromDate: DateTime(today.year, 1, 1).toIso8601String().substring(0, 10),
      toDate: today.toIso8601String().substring(0, 10),
    );
    context.push('/report-run', extra: args);
  }
}

class ReportRunArgs {
  const ReportRunArgs({
    required this.key,
    required this.title,
    required this.fromDate,
    required this.toDate,
  });

  final String key;
  final String title;
  final String fromDate;
  final String toDate;

  @override
  bool operator ==(Object other) =>
      other is ReportRunArgs &&
      other.key == key &&
      other.fromDate == fromDate &&
      other.toDate == toDate;

  @override
  int get hashCode => Object.hash(key, fromDate, toDate);
}

final reportRunProvider = FutureProvider.autoDispose
    .family<Map<String, dynamic>, ReportRunArgs>((ref, args) async {
      final repo = ref.read(reportsRepositoryProvider);
      return repo.generate(args.key, {
        'fromDate': args.fromDate,
        'toDate': args.toDate,
      });
    });

/// On-demand report runner for trial-balance / general-ledger: date range,
/// backend aggregation (never computed on-device), CSV export passthrough.
class ReportRunScreen extends ConsumerWidget {
  const ReportRunScreen({super.key, required this.args});

  final ReportRunArgs args;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final future = ref.watch(reportRunProvider(args));
    return Scaffold(
      appBar: AppBar(
        title: Text(args.title),
        actions: [
          IconButton(
            icon: const Icon(Icons.ios_share),
            tooltip: 'Export CSV',
            onPressed: () => _export(context, ref, args),
          ),
          IconButton(
            icon: const Icon(Icons.date_range),
            tooltip: 'Date range',
            onPressed: () => _changeRange(context, args),
          ),
        ],
      ),
      body: future.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => ErrorView(
          error: error,
          onRetry: () => ref.invalidate(reportRunProvider(args)),
          messageFor: messageForError,
        ),
        data: (report) => _ReportBody(args: args, report: report),
      ),
    );
  }

  Future<void> _changeRange(BuildContext context, ReportRunArgs args) async {
    final from = await showDatePicker(
      context: context,
      initialDate: DateTime.tryParse(args.fromDate) ?? DateTime.now(),
      firstDate: DateTime(2000),
      lastDate: DateTime(2100),
      helpText: 'From date',
    );
    if (from == null || !context.mounted) return;
    final to = await showDatePicker(
      context: context,
      initialDate: DateTime.tryParse(args.toDate) ?? DateTime.now(),
      firstDate: from,
      lastDate: DateTime(2100),
      helpText: 'To date',
    );
    if (to == null || !context.mounted) return;
    final updated = ReportRunArgs(
      key: args.key,
      title: args.title,
      fromDate: from.toIso8601String().substring(0, 10),
      toDate: to.toIso8601String().substring(0, 10),
    );
    // ignore: unawaited_futures
    context.pushReplacement('/report-run', extra: updated);
  }

  Future<void> _export(
    BuildContext context,
    WidgetRef ref,
    ReportRunArgs args,
  ) async {
    try {
      final repo = ref.read(reportsRepositoryProvider);
      final bytes = await repo.exportCsv(args.key, {
        'fromDate': args.fromDate,
        'toDate': args.toDate,
      });
      final file = File('${Directory.systemTemp.path}/${args.key}-report.csv');
      await file.writeAsBytes(bytes, flush: true);
      if (!context.mounted) return;
      await SharePlus.instance.share(
        ShareParams(files: [XFile(file.path)], text: '${args.title} export'),
      );
    } on ApiException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(messageForError(error))));
      }
    }
  }
}

class _ReportBody extends StatelessWidget {
  const _ReportBody({required this.args, required this.report});

  final ReportRunArgs args;
  final Map<String, dynamic> report;

  @override
  Widget build(BuildContext context) {
    // The report engine answers `items` (+ meta.total); `rows` kept as a
    // defensive fallback.
    final rowsRaw = report['items'] ?? report['rows'];
    final list = rowsRaw is List
        ? rowsRaw.whereType<Map>().toList()
        : const <Map>[];
    if (list.isEmpty) {
      return EmptyView(message: 'No rows for the selected period');
    }
    final isTrialBalance = args.key == 'trial-balance';
    return ListView(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: Text(
            '${args.fromDate} → ${args.toDate}',
            style: TextStyle(fontSize: 12.5, color: Colors.grey.shade600),
          ),
        ),
        if (isTrialBalance)
          ...list.map(
            (row) => Card(
              child: ListTile(
                title: Text(
                  '${row['accountCode'] ?? ''} — ${row['accountName'] ?? ''}',
                  style: const TextStyle(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                subtitle: Text(
                  'Period Dr ${_num(row['periodDebit'])} / Cr ${_num(row['periodCredit'])}'
                  ' · Closing Dr ${_num(row['closingDebit'])} / Cr ${_num(row['closingCredit'])}',
                ),
              ),
            ),
          )
        else
          ...list.map(
            (row) => Card(
              child: ListTile(
                title: Text(
                  '${row['postingDate'] ?? ''} — ${row['account'] ?? ''}',
                  style: const TextStyle(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                subtitle: Text(
                  '${row['voucherNo'] ?? ''} · ${row['description'] ?? ''}',
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                ),
                isThreeLine: true,
                trailing: SizedBox(
                  width: 110,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        'Dr ${_num(row['debit'])}',
                        style: const TextStyle(fontSize: 12),
                      ),
                      Text(
                        'Cr ${_num(row['credit'])}',
                        style: const TextStyle(fontSize: 12),
                      ),
                      Text(
                        'bal ${_num(row['runningBalance'])}',
                        style: TextStyle(
                          fontSize: 11,
                          color: Colors.grey.shade600,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}

num _num(Object? value) =>
    value is num ? value : num.tryParse('${value ?? ''}') ?? 0;
