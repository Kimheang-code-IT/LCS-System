import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/models/paged.dart';
import '../../../core/models/paged_notifier.dart';
import '../../../core/widgets/common.dart';
import '../../../core/widgets/list_scaffold.dart';
import '../data/document_models.dart';
import '../data/document_repository.dart';

/// Document types the mobile app exposes, in web terminology order.
enum DocType {
  customerInvoice('CUSTOMER_INVOICE'),
  customerReceipt('CUSTOMER_RECEIPT'),
  supplierBill('SUPPLIER_BILL'),
  supplierPayment('SUPPLIER_PAYMENT'),
  creditNote('CREDIT_NOTE'),
  supplierCreditNote('SUPPLIER_CREDIT_NOTE'),
  otherIncome('OTHER_INCOME'),
  otherExpense('OTHER_EXPENSE'),
  transfer('TRANSFER'),
  adjustment('ADJUSTMENT');

  const DocType(this.code);
  final String code;
}

class _DocListController
    extends FamilyNotifier<PagedState<FinancialDocument>, String> {
  DocumentRepository get _repo => ref.read(documentRepositoryProvider);

  @override
  PagedState<FinancialDocument> build(String arg) {
    Future<void>.microtask(refresh);
    return const PagedState<FinancialDocument>();
  }

  Future<ApiPage<FinancialDocument>> fetch(
    int page,
    PagedState<FinancialDocument> state,
  ) => _repo.list(
    page: page,
    documentType: arg == 'ALL' ? null : arg,
    search: state.search,
    status: state.status,
    fromDate: state.fromDate,
    toDate: state.toDate,
  );
}

final documentListProvider =
    NotifierProvider.family<
      _DocListController,
      PagedState<FinancialDocument>,
      String
    >(_DocListController.new);

/// Generic financial-document list for one type (or ALL for the browser).
class DocumentListScreen extends ConsumerWidget {
  const DocumentListScreen({
    super.key,
    required this.type,
    required this.title,
    this.hero,
    this.trailingActions = const [],
  });

  final DocType? type;
  final String title;
  final Widget? hero;
  final List<Widget> trailingActions;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final arg = type?.code ?? 'ALL';
    return PagedListView<FinancialDocument, _DocListController>(
      provider: documentListProvider,
      arg: arg,
      title: title,
      hero: hero,
      trailingActions: trailingActions,
      buildItem: (context, doc) => _DocumentCard(doc: doc),
    );
  }
}

class _DocumentCard extends StatelessWidget {
  const _DocumentCard({required this.doc});

  final FinancialDocument doc;

  @override
  Widget build(BuildContext context) {
    return RecordCard(
      title: doc.documentNo,
      subtitle: doc.customer ?? doc.remark ?? '',
      amount: doc.total,
      currency: doc.currency,
      status: doc.status,
      trailing: doc.documentDate?.substring(0, 10) ?? '',
      footer: doc.balance != 0 && doc.total != doc.paidAmount
          ? 'Outstanding ${doc.currency} ${doc.balance}'
          : null,
      onTap: () => context.push('/document', extra: doc.id),
    );
  }
}

/// Route argument shared by the /doc-list route (type filter + title).
class DocListArgs {
  const DocListArgs({required this.type, required this.title});

  final DocType? type;
  final String title;
}
