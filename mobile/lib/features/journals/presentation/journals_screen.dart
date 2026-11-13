import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_client.dart';
import '../../../core/auth/session.dart';
import '../../../core/utils/format.dart';
import '../../../core/widgets/common.dart';

/// Journal voucher (`/api/v1/journal-entries`) — the backend's double-entry
/// voucher document. Mobile is read-only: posting a journal with balanced
/// lines is a desktop workflow; the list and posted entry remain available.
class JournalEntry {
  const JournalEntry({
    required this.id,
    required this.entryNo,
    required this.status,
    required this.currency,
    required this.debitTotal,
    required this.creditTotal,
    this.entryType,
    this.entryDate,
    this.description,
    this.lines = const [],
  });

  final String id;
  final String entryNo;
  final String status;
  final String currency;
  final num debitTotal;
  final num creditTotal;
  final String? entryType;
  final String? entryDate;
  final String? description;
  final List<JournalLine> lines;

  factory JournalEntry.fromJson(Map<String, dynamic> json) {
    final linesRaw = json['lines'] ?? json['entries'];
    return JournalEntry(
      id: json['id']?.toString() ?? '',
      entryNo: json['entryNo'] as String? ?? '',
      status: json['status'] as String? ?? '',
      currency: json['currency'] as String? ?? '',
      debitTotal: _num(json['debitTotal']),
      creditTotal: _num(json['creditTotal']),
      entryType: json['entryType'] as String?,
      entryDate: json['entryDate'] as String?,
      description: json['description'] as String?,
      lines: linesRaw is List
          ? linesRaw
                .whereType<Map>()
                .map((e) => JournalLine.fromJson(e.cast<String, dynamic>()))
                .toList()
          : const [],
    );
  }
}

class JournalLine {
  const JournalLine({
    required this.account,
    required this.debit,
    required this.credit,
  });

  final String account;
  final num debit;
  final num credit;

  factory JournalLine.fromJson(Map<String, dynamic> json) => JournalLine(
    account: json['account'] as String? ?? '',
    debit: _num(json['debitAmount'] ?? json['debit']),
    credit: _num(json['creditAmount'] ?? json['credit']),
  );
}

final journalsProvider = FutureProvider.autoDispose.family<JournalPage, String>(
  (ref, _) async {
    final api = ref.read(apiClientProvider);
    final response = await apiCall(
      () => api.dio.get<dynamic>(
        '/api/v1/journal-entries',
        queryParameters: {'page': 1, 'page_size': 50},
      ),
    );
    final (:items, :total) = unwrapPage(response);
    return JournalPage(
      items: items.map(JournalEntry.fromJson).toList(),
      total: total,
    );
  },
);

class JournalPage {
  const JournalPage({required this.items, required this.total});

  final List<JournalEntry> items;
  final int total;
}

class JournalsScreen extends ConsumerWidget {
  const JournalsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final future = ref.watch(journalsProvider(''));
    return Scaffold(
      appBar: AppBar(title: const Text('Journal Vouchers')),
      body: future.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => ErrorView(
          error: error,
          onRetry: () => ref.invalidate(journalsProvider('')),
          messageFor: messageForError,
        ),
        data: (page) => RefreshIndicator(
          onRefresh: () async => ref.invalidate(journalsProvider('')),
          child: page.items.isEmpty
              ? EmptyView(
                  message: 'No journal entries',
                  onRetry: () => ref.invalidate(journalsProvider('')),
                )
              : ListView.builder(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  itemCount: page.items.length,
                  itemBuilder: (context, index) {
                    final entry = page.items[index];
                    return RecordCard(
                      title: entry.entryNo,
                      subtitle:
                          '${entry.entryType ?? ''}${entry.description != null && entry.description!.isNotEmpty ? ' — ${entry.description}' : ''}',
                      amount: entry.debitTotal,
                      currency: entry.currency,
                      status: entry.status,
                      trailing: (entry.entryDate ?? '').substring(0, 10),
                      footer:
                          'Dr ${formatMoney(entry.debitTotal, currency: entry.currency)} / '
                          'Cr ${formatMoney(entry.creditTotal, currency: entry.currency)}',
                      onTap: () => context.push('/journal', extra: entry.id),
                    );
                  },
                ),
        ),
      ),
    );
  }
}

final journalDetailProvider = FutureProvider.autoDispose
    .family<JournalEntry, String>((ref, id) async {
      final api = ref.read(apiClientProvider);
      final response = await apiCall(
        () => api.dio.get<dynamic>('/api/v1/journal-entries/$id'),
      );
      final data = unwrapData(response);
      return JournalEntry.fromJson((data as Map).cast<String, dynamic>());
    });

class JournalDetailScreen extends ConsumerWidget {
  const JournalDetailScreen({super.key, required this.entryId});

  final String entryId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final future = ref.watch(journalDetailProvider(entryId));
    return Scaffold(
      appBar: AppBar(title: const Text('Journal Voucher')),
      body: future.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => ErrorView(
          error: error,
          onRetry: () => ref.invalidate(journalDetailProvider(entryId)),
          messageFor: messageForError,
        ),
        data: (entry) => ListView(
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
                          entry.entryNo,
                          style: const TextStyle(
                            fontSize: 17,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                      StatusChip(raw: entry.status),
                    ],
                  ),
                  const SizedBox(height: 10),
                  InfoRow(label: 'Type', value: entry.entryType ?? ''),
                  InfoRow(label: 'Date', value: formatDate(entry.entryDate)),
                  InfoRow(label: 'Currency', value: entry.currency),
                  InfoRow(label: 'Description', value: entry.description ?? ''),
                  InfoRow(
                    label: 'Totals',
                    value:
                        'Dr ${formatMoney(entry.debitTotal, currency: entry.currency)} / Cr ${formatMoney(entry.creditTotal, currency: entry.currency)}',
                  ),
                ],
              ),
            ),
            SectionHeader(title: 'Debit / credit lines'),
            ...entry.lines.map(
              (line) => Card(
                child: ListTile(
                  title: Text(line.account.isEmpty ? '—' : line.account),
                  trailing: SizedBox(
                    width: 170,
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        Text(
                          'Dr ${line.debit}',
                          style: const TextStyle(fontSize: 12.5),
                        ),
                        const SizedBox(width: 12),
                        Text(
                          'Cr ${line.credit}',
                          style: const TextStyle(fontSize: 12.5),
                        ),
                      ],
                    ),
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
