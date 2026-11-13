import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/paged.dart';
import '../models/paged_notifier.dart';

import '../../app/theme.dart';
import '../../core/widgets/common.dart';

/// Generic server-paginated list screen: app bar, debounced search, filter
/// sheet, pull-to-refresh, skeleton while loading, infinite scroll.
class PagedListView<T, N extends FamilyNotifier<PagedState<T>, String>>
    extends ConsumerStatefulWidget {
  const PagedListView({
    super.key,
    required this.provider,
    required this.arg,
    required this.title,
    required this.buildItem,
    this.trailingActions = const [],
    this.emptyMessage = 'No records found',
    this.hero,
  });

  final NotifierProviderFamily<N, PagedState<T>, String> provider;
  final String arg;
  final String title;
  final Widget Function(BuildContext context, T item) buildItem;
  final List<Widget> trailingActions;
  final String emptyMessage;
  final Widget? hero;

  @override
  ConsumerState<PagedListView<T, N>> createState() =>
      _PagedListViewState<T, N>();
}

class _PagedListViewState<T, N extends FamilyNotifier<PagedState<T>, String>>
    extends ConsumerState<PagedListView<T, N>> {
  final _searchController = TextEditingController();

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final arg = widget.arg;
    final state = ref.watch(widget.provider(arg));

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title),
        actions: [
          ...widget.trailingActions,
          IconButton(
            icon: const Icon(Icons.filter_list),
            onPressed: () => _openFilters(context, arg),
          ),
        ],
      ),
      body: Column(
        children: [
          if (widget.hero != null) widget.hero!,
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
            child: TextField(
              controller: _searchController,
              textInputAction: TextInputAction.search,
              decoration: InputDecoration(
                hintText: 'Search',
                prefixIcon: const Icon(Icons.search),
                isDense: true,
                suffixIcon: _searchController.text.isEmpty
                    ? null
                    : IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _searchController.clear();
                          ref.read(widget.provider(arg).notifier).search('');
                        },
                      ),
              ),
              onChanged: (value) =>
                  ref.read(widget.provider(arg).notifier).search(value),
            ),
          ),
          Expanded(child: _body(context, state, arg)),
        ],
      ),
    );
  }

  Widget _body(BuildContext context, PagedState<T> state, String arg) {
    final controller = ref.read(widget.provider(arg).notifier);
    final error = state.error;
    final columns = MediaQuery.of(context).size.width;
    if (error != null && state.items.isEmpty) {
      return ErrorView(
        error: error,
        onRetry: controller.refresh,
        messageFor: messageForError,
      );
    }
    // First page still loading.
    if (state.items.isEmpty && state.page == 0) {
      return const Center(child: CircularProgressIndicator());
    }
    if (state.items.isEmpty) {
      return EmptyView(
        message: widget.emptyMessage,
        onRetry: controller.refresh,
      );
    }
    return RefreshIndicator(
      onRefresh: controller.refresh,
      child: _list(context, state, columns, arg),
    );
  }

  Widget _list(
    BuildContext context,
    PagedState<T> state,
    double columns,
    String arg,
  ) {
    return ListView.builder(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.symmetric(vertical: 8),
      itemCount: state.items.length + (state.hasMore ? 1 : 0),
      itemBuilder: (context, index) {
        if (index >= state.items.length) {
          // Load more when the sentinel scrolls into view.
          Future<void>.microtask(
            () => ref.read(widget.provider(arg).notifier).loadMore(),
          );
          return const Padding(
            padding: EdgeInsets.all(16),
            child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
          );
        }
        return Padding(
          padding: EdgeInsets.symmetric(horizontal: columns > 600 ? 24 : 0),
          child: widget.buildItem(context, state.items[index]),
        );
      },
    );
  }

  Future<void> _openFilters(BuildContext context, String arg) async {
    final state = ref.read(widget.provider(arg));
    final result = await showModalBottomSheet<Object>(
      context: context,
      showDragHandle: true,
      builder: (_) => FilterSheet(
        status: state.status,
        fromDate: state.fromDate,
        toDate: state.toDate,
      ),
    );
    if (result != null && context.mounted) {
      ref
          .read(widget.provider(arg).notifier)
          .setFilters(
            status: (result as dynamic).status as String?,
            fromDate: (result as dynamic).fromDate as String?,
            toDate: (result as dynamic).toDate as String?,
          );
    }
  }
}

/// Entry tile used on the Finance/Accounting/Reports landing screens.
class EntryTile extends StatelessWidget {
  const EntryTile({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.enabled = true,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        enabled: enabled,
        onTap: enabled ? onTap : null,
        leading: CircleAvatar(
          backgroundColor: AppTheme.seed.withValues(alpha: 0.08),
          foregroundColor: AppTheme.seed,
          child: Icon(icon, size: 22),
        ),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(
          subtitle,
          style: TextStyle(fontSize: 12.5, color: Colors.grey.shade600),
        ),
        trailing: const Icon(Icons.chevron_right),
      ),
    );
  }
}
