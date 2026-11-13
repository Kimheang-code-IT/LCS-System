/// A server pagination envelope: `{"items": [...], "meta": {"page", "page_size", "total"}}`.
class ApiPage<T> {
  ApiPage({required this.items, required this.total});

  final List<T> items;
  final int total;

  bool get hasMore => items.length < total;

  factory ApiPage.of(List<T> items, int total) =>
      ApiPage(items: items, total: total);
}

/// Reusable paged-list state for list screens (search, filters, infinite scroll).
class PagedState<T> {
  const PagedState({
    this.items = const [],
    this.total = 0,
    this.page = 0,
    this.loadingMore = false,
    this.search = '',
    this.status,
    this.fromDate,
    this.toDate,
    this.error,
  });

  final List<T> items;
  final int total;
  final int page;
  final bool loadingMore;
  final String search;
  final String? status;
  final String? fromDate;
  final String? toDate;
  final String? error;

  bool get hasMore => items.length < total;

  PagedState<T> copyWith({
    List<T>? items,
    int? total,
    int? page,
    bool? loadingMore,
    String? search,
    Object? status = _unset,
    Object? fromDate = _unset,
    Object? toDate = _unset,
    Object? error = _unset,
  }) => PagedState<T>(
    items: items ?? this.items,
    total: total ?? this.total,
    page: page ?? this.page,
    loadingMore: loadingMore ?? this.loadingMore,
    search: search ?? this.search,
    status: status == _unset ? this.status : status as String?,
    fromDate: fromDate == _unset ? this.fromDate : fromDate as String?,
    toDate: toDate == _unset ? this.toDate : toDate as String?,
    error: error == _unset ? this.error : error as String?,
  );

  static const _unset = Object();
}

/// A financial document line as the API payload reports it.
class DocLine {
  const DocLine({
    required this.description,
    required this.quantity,
    required this.unitPrice,
    required this.discount,
    required this.tax,
    required this.amount,
    this.feeType,
  });

  final String description;
  final num quantity;
  final num unitPrice;
  final num discount;
  final num tax;
  final num amount;
  final String? feeType;

  factory DocLine.fromJson(Map<String, dynamic> json) => DocLine(
    description: json['description'] as String? ?? '',
    quantity: _num(json['quantity']),
    unitPrice: _num(json['unitPrice']),
    discount: _num(json['discount']),
    tax: _num(json['taxAmount'] ?? json['tax']),
    amount: _num(json['amount']),
    feeType: json['feeType'] as String?,
  );
}

num _num(Object? value) =>
    value is num ? value : num.tryParse('${value ?? ''}') ?? 0;
