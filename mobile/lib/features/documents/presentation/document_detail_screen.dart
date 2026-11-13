import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/auth/session.dart';
import '../../../core/utils/format.dart';
import '../../../core/widgets/common.dart';
import '../../../l10n/app_localizations.dart';
import '../../../core/models/paged.dart';
import '../data/document_models.dart';
import '../data/document_repository.dart';
import 'document_form_screen.dart';

class DocumentDetailController
    extends AutoDisposeFamilyNotifier<AsyncValue<FinancialDocument>, String> {
  @override
  AsyncValue<FinancialDocument> build(String arg) {
    Future<void>.microtask(refresh);
    return const AsyncLoading();
  }

  DocumentRepository get _repo => ref.read(documentRepositoryProvider);

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() => _repo.get(arg));
  }

  Future<void> post() async {
    await _repo.post(arg);
    await refresh();
  }

  Future<void> reverse(String reason) async {
    await _repo.reverse(arg, reason);
    await refresh();
  }
}

final documentDetailProvider = NotifierProvider.autoDispose
    .family<DocumentDetailController, AsyncValue<FinancialDocument>, String>(
      DocumentDetailController.new,
    );

/// Detail screen for any financial document: header, lines, allocations,
/// journal, with backend-supported actions only (post draft, reverse posted,
/// print preview for customer invoices).
class DocumentDetailScreen extends ConsumerWidget {
  const DocumentDetailScreen({super.key, required this.documentId});

  final String documentId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = AppLocalizations.of(context)!;
    final state = ref.watch(documentDetailProvider(documentId));
    final controller = ref.read(documentDetailProvider(documentId).notifier);
    final user = ref.watch(sessionProvider).user;

    final canPost = user?.can('financial_document.submit') ?? false;
    final canReverse = user?.can('financial_document.reverse') ?? false;
    final canEdit = user?.can('financial_document.update') ?? false;

    return Scaffold(
      appBar: AppBar(title: Text(t.documentNo)),
      body: state.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => ErrorView(
          error: error,
          onRetry: controller.refresh,
          messageFor: messageForError,
        ),
        data: (doc) => _Body(
          doc: doc,
          canPost: canPost,
          canReverse: canReverse,
          canEdit: canEdit,
        ),
      ),
    );
  }
}

class _Body extends ConsumerWidget {
  const _Body({
    required this.doc,
    required this.canPost,
    required this.canReverse,
    required this.canEdit,
  });

  final FinancialDocument doc;
  final bool canPost;
  final bool canReverse;
  final bool canEdit;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = AppLocalizations.of(context)!;
    final busy = ref.watch(_busyProvider(doc.id));

    return Stack(
      children: [
        ListView(
          padding: const EdgeInsets.only(bottom: 100),
          children: [
            _Header(doc: doc),
            if (doc.lines.isNotEmpty) ...[
              SectionHeader(title: t.lines),
              ...doc.lines.map(
                (line) => _LineTile(
                  line: line,
                  currency: doc.currency,
                  precision: doc.currencyPrecision,
                ),
              ),
            ],
            if (doc.allocations.isNotEmpty) ...[
              SectionHeader(title: t.allocations),
              ...doc.allocations.map((a) => _AllocationTile(a: a)),
            ],
            if (doc.journalEntries.isNotEmpty) ...[
              SectionHeader(title: t.journal),
              ...doc.journalEntries.map((row) => _JournalTile(row: row)),
            ],
          ],
        ),
        if (busy)
          const Positioned.fill(
            child: ColoredBox(
              color: Colors.black26,
              child: Center(child: CircularProgressIndicator()),
            ),
          ),
        Align(
          alignment: Alignment.bottomCenter,
          child: SafeArea(
            child: _ActionBar(
              doc: doc,
              canPost: canPost,
              canReverse: canReverse,
              canEdit: canEdit,
            ),
          ),
        ),
      ],
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.doc});

  final FinancialDocument doc;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  doc.documentNo,
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              StatusChip(raw: doc.status),
            ],
          ),
          const SizedBox(height: 10),
          MoneyText(
            doc.total,
            currency: doc.currency,
            strong: true,
            decimals: 2,
          ),
          const Divider(height: 24),
          InfoRow(label: t.customer, value: doc.customer ?? ''),
          if (doc.dueDate != null)
            InfoRow(label: t.dueDate, value: formatDate(doc.dueDate)),
          InfoRow(label: t.date, value: formatDate(doc.documentDate)),
          if (doc.referenceNumber != null)
            InfoRow(label: t.reference, value: doc.referenceNumber!),
          if (doc.paymentMethod != null)
            InfoRow(label: t.paymentMethod, value: doc.paymentMethod!),
          if (doc.financialAccount != null)
            InfoRow(label: t.financialAccount, value: doc.financialAccount!),
          InfoRow(
            label: t.paidAmount,
            value: formatMoney(doc.paidAmount, currency: doc.currency),
          ),
          InfoRow(
            label: t.outstanding,
            value: formatMoney(doc.balance, currency: doc.currency),
          ),
          if (doc.jobNo != null) InfoRow(label: 'Job', value: doc.jobNo!),
          if (doc.journalNo != null)
            InfoRow(label: t.journal, value: doc.journalNo!),
          if (doc.remark != null) InfoRow(label: t.remark, value: doc.remark!),
          if (doc.createdBy != null)
            InfoRow(label: t.createdBy, value: doc.createdBy!),
          if (doc.createdAt != null)
            InfoRow(label: t.createdAt, value: formatDateTime(doc.createdAt)),
        ],
      ),
    );
  }
}

class _LineTile extends StatelessWidget {
  const _LineTile({
    required this.line,
    required this.currency,
    this.precision = 2,
  });

  final DocLine line;
  final String currency;
  final int precision;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        title: Text(
          line.description.isEmpty ? (line.feeType ?? '—') : line.description,
        ),
        subtitle: Text(
          '${line.quantity} × ${formatMoney(line.unitPrice, currency: currency, decimals: precision)}'
          '${line.discount > 0 ? ' · -${formatMoney(line.discount, currency: currency, decimals: precision)}' : ''}'
          '${line.tax > 0 ? ' · tax ${formatMoney(line.tax, currency: currency, decimals: precision)}' : ''}',
          style: TextStyle(fontSize: 12.5, color: Colors.grey.shade600),
        ),
        trailing: MoneyText(
          line.amount,
          currency: currency,
          strong: true,
          decimals: 2,
        ),
      ),
    );
  }
}

class _AllocationTile extends StatelessWidget {
  const _AllocationTile({required this.a});

  final Allocation a;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        title: Text(a.targetDocumentNo ?? a.targetDocumentId ?? '—'),
        subtitle: Text(
          '${formatDate(a.allocatedAt)} · applied ${formatMoney(a.appliedAmount, currency: a.appliedCurrency.isEmpty ? 'USD' : a.appliedCurrency)}',
          style: TextStyle(fontSize: 12.5, color: Colors.grey.shade600),
        ),
        trailing: MoneyText(
          a.amount,
          currency: a.appliedCurrency,
          strong: true,
        ),
      ),
    );
  }
}

class _JournalTile extends StatelessWidget {
  const _JournalTile({required this.row});

  final JournalRow row;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        title: Text('${row.account} — ${row.description}'),
        subtitle: Text('Debit ${row.debit} · Credit ${row.credit}'),
      ),
    );
  }
}

class _ActionBar extends ConsumerWidget {
  const _ActionBar({
    required this.doc,
    required this.canPost,
    required this.canReverse,
    required this.canEdit,
  });

  final FinancialDocument doc;
  final bool canPost;
  final bool canReverse;
  final bool canEdit;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = AppLocalizations.of(context)!;
    final controller = ref.read(documentDetailProvider(doc.id).notifier);
    final isInvoice = doc.documentType == 'CUSTOMER_INVOICE';

    return Container(
      color: Colors.white,
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      child: Row(
        children: [
          if (isInvoice)
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => _print(context, ref),
                icon: const Icon(Icons.print_outlined, size: 18),
                label: Text(t.print),
              ),
            ),
          if (canEdit && doc.isDraft) ...[
            const SizedBox(width: 8),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => _edit(context),
                icon: const Icon(Icons.edit_outlined, size: 18),
                label: Text(t.edit),
              ),
            ),
          ],
          if (canPost && doc.isDraft) ...[
            const SizedBox(width: 8),
            Expanded(
              child: FilledButton.icon(
                onPressed: () => _post(context, ref, controller),
                icon: const Icon(Icons.check_circle_outline, size: 18),
                label: Text(t.post),
              ),
            ),
          ],
          if (canReverse && doc.isPosted) ...[
            const SizedBox(width: 8),
            Expanded(
              child: FilledButton.tonalIcon(
                onPressed: () => _reverse(context, controller, t),
                icon: const Icon(Icons.undo, size: 18),
                label: Text(t.reverse),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Future<void> _post(
    BuildContext context,
    WidgetRef ref,
    DocumentDetailController controller,
  ) async {
    final t = AppLocalizations.of(context)!;
    final confirmed = await confirmAction(
      context,
      title: t.post,
      message: '${t.confirmPost} ${t.postHint}',
      confirmLabel: t.post,
    );
    if (!confirmed || !context.mounted) return;
    ref.read(_busyProvider(doc.id).notifier).state = true;
    try {
      await controller.post();
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(t.posted)));
      }
    } on ApiException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('${t.postingFailed}: ${messageForError(error)}'),
          ),
        );
      }
    } finally {
      ref.read(_busyProvider(doc.id).notifier).state = false;
    }
  }

  Future<void> _reverse(
    BuildContext context,
    DocumentDetailController controller,
    AppLocalizations t,
  ) async {
    final confirmed = await confirmAction(
      context,
      title: t.reverse,
      message: t.confirmReverse,
      confirmLabel: t.reverse,
    );
    if (!confirmed || !context.mounted) return;
    final reason = await _askReason(context, t);
    if (reason == null || !context.mounted) return;
    try {
      await controller.reverse(reason);
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(t.reversed)));
      }
    } on ApiException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(messageForError(error))));
      }
    }
  }

  Future<String?> _askReason(BuildContext context, AppLocalizations t) {
    final controller = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(t.reason),
        content: TextField(
          controller: controller,
          autofocus: true,
          maxLines: 2,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(t.cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text.trim()),
            child: Text(t.reverse),
          ),
        ],
      ),
    );
  }

  Future<void> _print(BuildContext context, WidgetRef ref) async {
    try {
      final repo = ref.read(documentRepositoryProvider);
      final data = await repo.printData(doc.id);
      if (context.mounted) {
        await context.push('/print', extra: data);
      }
    } on ApiException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(messageForError(error))));
      }
    }
  }

  void _edit(BuildContext context) {
    context.push(
      '/document-form',
      extra: DocumentFormArgs(existing: doc, documentType: doc.documentType),
    );
  }
}

final _busyProvider = StateProvider.autoDispose.family<bool, String>(
  (ref, id) => false,
);

void openDocumentForm(
  BuildContext context, {
  FinancialDocument? existing,
  required String documentType,
}) {
  Navigator.of(context).pushNamed(
    '/document-form',
    arguments: DocumentFormArgs(existing: existing, documentType: documentType),
  );
}
