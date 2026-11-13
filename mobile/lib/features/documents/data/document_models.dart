import '../../../core/models/paged.dart';

/// A financial document from `/api/v1/financial-documents`, matching the
/// backend `document_payload` keys. Amounts are display-only (backend Decimal).
class FinancialDocument {
  const FinancialDocument({
    required this.id,
    required this.documentNo,
    required this.documentType,
    required this.documentDate,
    required this.status,
    required this.currency,
    required this.total,
    required this.paidAmount,
    required this.balance,
    this.currencyPrecision = 2,
    this.dueDate,
    this.postingDate,
    this.referenceNumber,
    this.remark,
    this.paymentMethod,
    this.financialAccount,
    this.financialAccountId,
    this.customer,
    this.jobNo,
    this.exchangeRate,
    this.baseCurrency,
    this.lines = const [],
    this.allocations = const [],
    this.journalNo,
    this.journalEntries = const [],
    this.createdBy,
    this.createdAt,
    this.raw = const {},
  });

  final String id;
  final String documentNo;
  final String documentType;
  final String? documentDate;
  final String status;
  final String currency;
  final num total;
  final num paidAmount;
  final num balance;

  /// Decimal places of the document currency, reported by the list/detail
  /// payload (`currencyPrecision`, resolved from the Currency master data).
  final int currencyPrecision;
  final String? dueDate;
  final String? postingDate;
  final String? referenceNumber;
  final String? remark;
  final String? paymentMethod;
  final String? financialAccount;
  final String? financialAccountId;
  final String? customer;
  final String? jobNo;
  final num? exchangeRate;
  final String? baseCurrency;
  final List<DocLine> lines;
  final List<Allocation> allocations;
  final String? journalNo;
  final List<JournalRow> journalEntries;
  final String? createdBy;
  final String? createdAt;
  final Map<String, dynamic> raw;

  bool get isDraft => status.toUpperCase() == 'DRAFT';
  bool get isPosted => status.toUpperCase() == 'POSTED';

  static final _no = RegExp(r'^[0-9]+$');

  /// Party name: detail/list payload puts it in `customer` (or the raw record's
  /// typed name); fall back to the stored data blob.
  static String? _partyName(Map<String, dynamic> json) =>
      (json['customer'] ?? json['supplier'] ?? json['partyName']) as String?;

  static FinancialDocument fromJson(Map<String, dynamic> json) {
    final rawLines = json['lines'];
    final rawAllocations = json['allocations'];
    final rawJournal = json['journalEntries'];
    final financialAccountId = json['financialAccountId'];
    return FinancialDocument(
      id: json['id']?.toString() ?? '',
      documentNo: json['documentNo'] as String? ?? '',
      documentType: json['documentType'] as String? ?? '',
      documentDate: (json['documentDate'] ?? json['date']) as String?,
      status: json['status'] as String? ?? '',
      currency: json['currency'] as String? ?? '',
      currencyPrecision: json['currencyPrecision'] is num
          ? (json['currencyPrecision'] as num).toInt()
          : 2,
      total: _num(json['total'] ?? json['amount']),
      paidAmount: _num(json['paidAmount'] ?? json['paid']),
      balance: _num(json['balance'] ?? json['outstanding']),
      dueDate: json['dueDate'] as String?,
      postingDate: json['postingDate'] as String?,
      referenceNumber: json['referenceNumber'] as String?,
      remark: (json['remark'] ?? json['description']) as String?,
      paymentMethod: json['paymentMethod'] as String?,
      financialAccount: json['financialAccount'] as String?,
      financialAccountId:
          financialAccountId is String && _no.hasMatch(financialAccountId)
          ? financialAccountId
          : financialAccountId?.toString(),
      customer: _partyName(json),
      jobNo: (json['jobNo'] as String?)?.isNotEmpty == true
          ? json['jobNo'] as String?
          : null,
      exchangeRate: _numOrNull(json['exchangeRate']),
      baseCurrency: json['baseCurrency'] as String?,
      lines: rawLines is List
          ? rawLines
                .whereType<Map>()
                .map((e) => DocLine.fromJson(e.cast<String, dynamic>()))
                .toList()
          : const [],
      allocations: rawAllocations is List
          ? rawAllocations
                .whereType<Map>()
                .map((e) => Allocation.fromJson(e.cast<String, dynamic>()))
                .toList()
          : const [],
      journalNo: json['journalNo'] as String?,
      journalEntries: rawJournal is List
          ? rawJournal
                .whereType<Map>()
                .map((e) => JournalRow.fromJson(e.cast<String, dynamic>()))
                .toList()
          : const [],
      createdBy: json['createdBy'] as String?,
      createdAt: json['createdAt'] as String?,
      raw: json,
    );
  }

  Map<String, dynamic> toFormPayload() => {
    'documentType': documentType,
    'documentDate': (documentDate ?? '').substring(0, 10),
    'currency': currency,
    'remark': remark,
  };
}

/// A payment allocation between a payment and its target invoice/bill.
class Allocation {
  const Allocation({
    required this.amount,
    required this.appliedAmount,
    required this.appliedCurrency,
    required this.allocatedAt,
    this.targetDocumentId,
    this.targetDocumentNo,
    this.targetOutstanding,
  });

  final num amount;
  final num appliedAmount;
  final String appliedCurrency;
  final String? allocatedAt;
  final String? targetDocumentId;
  final String? targetDocumentNo;
  final num? targetOutstanding;

  factory Allocation.fromJson(Map<String, dynamic> json) {
    final targetId = json['targetDocumentId'];
    return Allocation(
      amount: _num(json['amount']),
      appliedAmount: _num(json['appliedAmount']),
      appliedCurrency: json['appliedCurrency'] as String? ?? '',
      allocatedAt: json['allocatedAt'] as String?,
      targetDocumentId: targetId?.toString(),
      targetDocumentNo: json['targetDocumentNo'] as String?,
      targetOutstanding: _numOrNull(json['targetOutstanding']),
    );
  }
}

/// One debit/credit row of the journal a posted document created.
class JournalRow {
  const JournalRow({
    required this.account,
    required this.description,
    required this.debit,
    required this.credit,
  });

  final String account;
  final String description;
  final num debit;
  final num credit;

  factory JournalRow.fromJson(Map<String, dynamic> json) => JournalRow(
    account: json['account'] as String? ?? '',
    description: json['description'] as String? ?? '',
    debit: _num(json['debit']),
    credit: _num(json['credit']),
  );
}

/// A business party option for selects (`/api/v1/businessParties`).
class PartyOption {
  const PartyOption({required this.id, required this.name});

  final String id;
  final String name;

  factory PartyOption.fromJson(Map<String, dynamic> json) => PartyOption(
    id: json['id']?.toString() ?? '',
    name:
        (json['legalName'] ?? json['displayName'] ?? json['name'] ?? '')
            as String,
  );
}

/// A financial account option for payment forms (`/api/v1/financial-accounts`).
class FinancialAccountOption {
  const FinancialAccountOption({
    required this.id,
    required this.name,
    required this.currency,
  });

  final String id;
  final String name;
  final String currency;

  factory FinancialAccountOption.fromJson(Map<String, dynamic> json) =>
      FinancialAccountOption(
        id: json['id']?.toString() ?? '',
        name: json['accountName'] as String? ?? '',
        currency: json['currency'] as String? ?? '',
      );
}

num _num(Object? value) =>
    value is num ? value : num.tryParse('${value ?? ''}') ?? 0;

num? _numOrNull(Object? value) {
  if (value is num) return value;
  if (value is String && value.isNotEmpty) return num.tryParse(value);
  return null;
}
