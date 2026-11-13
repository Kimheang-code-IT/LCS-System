import 'package:flutter/material.dart';

import '../models/paged.dart';
import '../utils/format.dart';

/// Status badge with LCS status colors.
class StatusChip extends StatelessWidget {
  const StatusChip({super.key, required this.raw});

  final String? raw;

  @override
  Widget build(BuildContext context) {
    final kind = statusKind(raw);
    final colors = switch (kind) {
      StatusKind.positive => (Colors.green.shade50, Colors.green.shade800),
      StatusKind.info => (Colors.blue.shade50, Colors.blue.shade800),
      StatusKind.warning => (Colors.amber.shade50, Colors.amber.shade900),
      StatusKind.danger => (Colors.red.shade50, Colors.red.shade800),
      StatusKind.neutral => (Colors.grey.shade200, Colors.grey.shade800),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: colors.$1,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        (raw ?? '').toUpperCase(),
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: colors.$2,
        ),
      ),
    );
  }
}

/// Money text with tabular figures so amounts line up.
class MoneyText extends StatelessWidget {
  const MoneyText(
    this.amount, {
    super.key,
    required this.currency,
    this.decimals = 2,
    this.strong = false,
  });

  final num? amount;
  final String currency;
  final int decimals;
  final bool strong;

  @override
  Widget build(BuildContext context) {
    return Text(
      formatMoney(amount, currency: currency, decimals: decimals),
      style: TextStyle(
        fontFeatures: const [FontFeature.tabularFigures()],
        fontWeight: strong ? FontWeight.w700 : FontWeight.w500,
        fontSize: strong ? 15 : 13.5,
      ),
    );
  }
}

/// One labelled row on a detail screen.
class InfoRow extends StatelessWidget {
  const InfoRow({super.key, required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 116,
            child: Text(
              label,
              style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
            ),
          ),
          Expanded(
            child: Text(
              value.isEmpty ? '—' : value,
              style: const TextStyle(fontSize: 14),
            ),
          ),
        ],
      ),
    );
  }
}

/// Section header on a detail screen.
class SectionHeader extends StatelessWidget {
  const SectionHeader({super.key, required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 4),
      child: Text(
        title.toUpperCase(),
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.8,
          color: Colors.grey.shade600,
        ),
      ),
    );
  }
}

/// Empty state with optional retry.
class EmptyView extends StatelessWidget {
  const EmptyView({super.key, required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.inbox_outlined, size: 44, color: Colors.grey.shade400),
          const SizedBox(height: 12),
          Text(message, style: TextStyle(color: Colors.grey.shade600)),
          if (onRetry != null) ...[
            const SizedBox(height: 12),
            TextButton(onPressed: onRetry, child: const Text('Retry')),
          ],
        ],
      ),
    );
  }
}

/// Error state with a user-safe message and a retry action.
class ErrorView extends StatelessWidget {
  const ErrorView({
    super.key,
    required this.error,
    required this.onRetry,
    required this.messageFor,
  });

  final Object error;
  final VoidCallback onRetry;
  final String Function(Object) messageFor;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.cloud_off_outlined,
              size: 44,
              color: Colors.grey.shade400,
            ),
            const SizedBox(height: 12),
            Text(
              messageFor(error),
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey.shade700),
            ),
            const SizedBox(height: 16),
            FilledButton.tonal(onPressed: onRetry, child: const Text('Retry')),
          ],
        ),
      ),
    );
  }
}

/// Loading skeleton: shimmer-like pulse blocks.
class ListSkeleton extends StatelessWidget {
  const ListSkeleton({super.key, this.rows = 6});

  final int rows;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: List.generate(rows, (index) {
        return const Card(child: SizedBox(height: 72, width: double.infinity));
      }),
    );
  }
}

/// Confirmation dialog for sensitive actions; returns true when confirmed.
Future<bool> confirmAction(
  BuildContext context, {
  required String title,
  required String message,
  required String confirmLabel,
}) async {
  final result = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(title),
      content: Text(message),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, false),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, true),
          child: Text(confirmLabel),
        ),
      ],
    ),
  );
  return result == true;
}

/// Snack-bar error message mapping, user-safe (no stack traces).
String messageForError(Object error) {
  final type = error.runtimeType.toString();
  if (type.contains('ApiException')) {
    final dynamic e = error;
    final code = e.code as String?;
    return switch (code) {
      'NETWORK' => 'No connection. Check your network and try again.',
      'UNAUTHORIZED' => 'Your session has expired. Please sign in again.',
      'FORBIDDEN' => 'You do not have permission for this action.',
      'NOT_FOUND' => 'Record not found.',
      'VALIDATION' => (e.message as String?) ?? 'The request was not accepted.',
      'CONFLICT' =>
        (e.message as String?) ??
            'The request conflicts with the current state.',
      'SERVER' => 'The server could not process the request.',
      _ => (e.message as String?) ?? 'The request could not be completed.',
    };
  }
  return 'Something went wrong. Please try again.';
}

/// Compact card row used by all document/transaction lists.
class RecordCard extends StatelessWidget {
  const RecordCard({
    super.key,
    required this.title,
    required this.subtitle,
    required this.amount,
    required this.currency,
    this.trailing,
    this.status,
    this.footer,
    this.onTap,
  });

  final String title;
  final String subtitle;
  final num? amount;
  final String currency;
  final String? trailing;
  final String? status;
  final String? footer;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      title,
                      style: const TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 14,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  if (status != null) StatusChip(raw: status),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                subtitle,
                style: TextStyle(fontSize: 13, color: Colors.grey.shade700),
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  MoneyText(amount, currency: currency, strong: true),
                  const Spacer(),
                  if (trailing != null)
                    Text(
                      trailing!,
                      style: TextStyle(
                        fontSize: 12.5,
                        color: Colors.grey.shade600,
                      ),
                    ),
                ],
              ),
              if (footer != null) ...[
                const SizedBox(height: 4),
                Text(
                  footer!,
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade500),
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Reusable filter bottom sheet: status + date range.
class FilterSheet extends StatefulWidget {
  const FilterSheet({
    super.key,
    required this.status,
    required this.fromDate,
    required this.toDate,
    this.statuses = const ['DRAFT', 'POSTED', 'PARTIAL', 'PAID', 'REVERSED'],
  });

  final String? status;
  final String? fromDate;
  final String? toDate;
  final List<String> statuses;

  @override
  State<FilterSheet> createState() => _FilterSheetState();
}

class _FilterSheetState extends State<FilterSheet> {
  late String? _status = widget.status;
  late String? _from = widget.fromDate;
  late String? _to = widget.toDate;

  Future<void> _pickDate({required bool isFrom}) async {
    final initial =
        DateTime.tryParse((isFrom ? _from : _to) ?? '') ?? DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(2000),
      lastDate: DateTime(2100),
    );
    if (picked != null) {
      setState(() {
        final iso = picked.toIso8601String().substring(0, 10);
        if (isFrom) {
          _from = iso;
        } else {
          _to = iso;
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        top: 16,
        bottom: MediaQuery.of(context).viewInsets.bottom + 24,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Filters', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            children: [
              ChoiceChip(
                label: const Text('All'),
                selected: _status == null,
                onSelected: (_) => setState(() => _status = null),
              ),
              for (final status in widget.statuses)
                ChoiceChip(
                  label: Text(status),
                  selected: _status == status,
                  onSelected: (_) => setState(() => _status = status),
                ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: () => _pickDate(isFrom: true),
                  child: Text(_from == null ? 'From date' : _from!),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton(
                  onPressed: () => _pickDate(isFrom: false),
                  child: Text(_to == null ? 'To date' : _to!),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: () => Navigator.pop(context, (
                    status: null,
                    from: null,
                    to: null,
                  )),
                  child: const Text('Clear'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: FilledButton(
                  onPressed: () => Navigator.pop(context, (
                    status: _status,
                    from: _from,
                    to: _to,
                  )),
                  child: const Text('Apply'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// Pagination parsing shared by every repository test and screen.
ApiPage<T> pageFromEnvelope<T>(
  Map<String, dynamic>? envelope,
  T Function(Map<String, dynamic>) fromJson,
) {
  final payload = envelope?['data'];
  if (payload is Map && payload['items'] is List) {
    final items = (payload['items'] as List)
        .whereType<Map>()
        .map((e) => fromJson(e.cast<String, dynamic>()))
        .toList();
    final meta = payload['meta'];
    final total = meta is Map
        ? (meta['total'] as num?) ?? items.length
        : items.length;
    return ApiPage.of(items, total.toInt());
  }
  throw StateError('Unexpected page envelope');
}
