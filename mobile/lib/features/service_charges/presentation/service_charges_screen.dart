import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_client.dart';
import '../../../core/auth/session.dart';
import '../../../core/models/paged.dart';
import '../../../core/models/paged_notifier.dart';
import '../../../core/utils/format.dart';
import '../../../core/widgets/common.dart';
import '../../../core/widgets/list_scaffold.dart';

/// A service charge: one charge → many fee lines, from `/api/v1/service-charges`.
/// List columns follow the existing LCS design: Charge No., description, grand
/// total, created by, created at (party/order/invoice details stay in detail).
class ServiceCharge {
  const ServiceCharge({
    required this.id,
    required this.chargeNo,
    required this.status,
    required this.currency,
    required this.total,
    this.description,
    this.createdBy,
    this.createdAt,
    this.lines = const [],
  });

  final String id;
  final String chargeNo;
  final String status;
  final String currency;
  final num total;
  final String? description;
  final String? createdBy;
  final String? createdAt;
  final List<DocLine> lines;

  factory ServiceCharge.fromJson(Map<String, dynamic> json) => ServiceCharge(
    id: json['id']?.toString() ?? '',
    chargeNo: (json['chargeNo'] ?? json['documentNo']) as String? ?? '',
    status: json['status'] as String? ?? '',
    currency: json['currency'] as String? ?? '',
    total: _num(json['total'] ?? json['amount']),
    description: json['description'] as String?,
    createdBy: json['createdBy'] as String?,
    createdAt: json['createdAt'] as String?,
    lines: json['feeLines'] is List
        ? (json['feeLines'] as List)
              .whereType<Map>()
              .map((e) => DocLine.fromJson(e.cast<String, dynamic>()))
              .toList()
        : const [],
  );
}

class ServiceChargeListController
    extends FamilyNotifier<PagedState<ServiceCharge>, String> {
  @override
  PagedState<ServiceCharge> build(String arg) {
    Future<void>.microtask(refresh);
    return const PagedState<ServiceCharge>();
  }

  Future<ApiPage<ServiceCharge>> fetch(
    int page,
    PagedState<ServiceCharge> state,
  ) => apiCall(() async {
    final api = ref.read(apiClientProvider);
    final response = await api.dio.get<dynamic>(
      '/api/v1/service-charges',
      queryParameters: {
        'page': page,
        'page_size': 20,
        if (state.search.isNotEmpty) 'q': state.search,
        if (state.status != null && state.status!.isNotEmpty)
          'status': state.status,
      },
    );
    final (:items, :total) = unwrapPage(response);
    return ApiPage.of(items.map(ServiceCharge.fromJson).toList(), total);
  });
}

final serviceChargeListProvider =
    NotifierProvider.family<
      ServiceChargeListController,
      PagedState<ServiceCharge>,
      String
    >(ServiceChargeListController.new);

class ServiceChargesScreen extends ConsumerWidget {
  const ServiceChargesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return PagedListView<ServiceCharge, ServiceChargeListController>(
      provider: serviceChargeListProvider,
      arg: 'all',
      title: 'Service Charges',
      buildItem: (context, charge) => RecordCard(
        title: charge.chargeNo,
        subtitle: charge.description ?? '',
        amount: charge.total,
        currency: charge.currency,
        status: charge.status,
        trailing: charge.createdAt?.substring(0, 10) ?? '',
        footer: charge.createdBy != null ? 'By ${charge.createdBy}' : null,
        onTap: () => context.push('/service-charge', extra: charge.id),
      ),
    );
  }
}

final serviceChargeDetailProvider = FutureProvider.autoDispose
    .family<ServiceCharge, String>((ref, id) async {
      final api = ref.read(apiClientProvider);
      final response = await apiCall(
        () => api.dio.get<dynamic>('/api/v1/service-charges/$id'),
      );
      final data = unwrapData(response);
      return ServiceCharge.fromJson((data as Map).cast<String, dynamic>());
    });

/// Detail: charge number, description, fee lines with backend-calculated totals.
class ServiceChargeDetailScreen extends ConsumerWidget {
  const ServiceChargeDetailScreen({super.key, required this.chargeId});

  final String chargeId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final future = ref.watch(serviceChargeDetailProvider(chargeId));
    return Scaffold(
      appBar: AppBar(title: const Text('Service Charge')),
      body: future.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => ErrorView(
          error: error,
          onRetry: () => ref.invalidate(serviceChargeDetailProvider(chargeId)),
          messageFor: messageForError,
        ),
        data: (charge) => ListView(
          children: [
            Container(
              color: Colors.white,
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          charge.chargeNo,
                          style: const TextStyle(
                            fontSize: 17,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                      StatusChip(raw: charge.status),
                    ],
                  ),
                  const SizedBox(height: 10),
                  MoneyText(
                    charge.total,
                    currency: charge.currency,
                    strong: true,
                  ),
                  if (charge.description != null) ...[
                    const SizedBox(height: 10),
                    Text(
                      charge.description!,
                      style: const TextStyle(fontSize: 14),
                    ),
                  ],
                  if (charge.createdBy != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Text(
                        'Created by ${charge.createdBy} · ${formatDateTime(charge.createdAt)}',
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey.shade600,
                        ),
                      ),
                    ),
                ],
              ),
            ),
            SectionHeader(title: 'Fee lines'),
            ...charge.lines.map(
              (line) => Card(
                child: ListTile(
                  title: Text(
                    line.description.isEmpty
                        ? (line.feeType ?? '—')
                        : line.description,
                  ),
                  subtitle: Text(
                    '${line.quantity} × ${formatMoney(line.unitPrice, currency: charge.currency)}'
                    '${line.discount > 0 ? ' · -${formatMoney(line.discount, currency: charge.currency)}' : ''}'
                    '${line.tax > 0 ? ' · tax ${formatMoney(line.tax, currency: charge.currency)}' : ''}',
                    style: TextStyle(
                      fontSize: 12.5,
                      color: Colors.grey.shade600,
                    ),
                  ),
                  trailing: MoneyText(
                    line.amount,
                    currency: charge.currency,
                    strong: true,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

num _num(Object? value) =>
    value is num ? value : num.tryParse('${value ?? ''}') ?? 0;
