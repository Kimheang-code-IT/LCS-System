import 'dart:async';

// The paging extension manipulates Notifier state on behalf of list
// controllers that own this state; Riverpod's @protected marker cannot see
// through extensions.
// ignore_for_file: invalid_use_of_protected_member, invalid_use_of_visible_for_testing_member
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'paged.dart';

final _debounces = Expando<Timer>();

/// Paging/search/filter behaviour shared by every family list controller.
///
/// Controllers extend [FamilyNotifier] and expose `fetch(page, state)`; the
/// extension drives them via that contract (fetched through `dynamic` to keep
/// one implementation for every list screen).
extension PagedListOps<T, Arg> on FamilyNotifier<PagedState<T>, Arg> {
  /// Fetch one page. Concrete controllers implement this.
  Future<ApiPage<T>> fetch(int page, PagedState<T> state) =>
      throw UnimplementedError();

  Future<void> refresh() async {
    final loader = _fetch;
    try {
      final result = await loader(1, state);
      state = PagedState<T>(
        items: result.items,
        total: result.total,
        page: 1,
        search: state.search,
        status: state.status,
        fromDate: state.fromDate,
        toDate: state.toDate,
      );
    } catch (error) {
      state = state.copyWith(loadingMore: false, error: error);
    }
  }

  Future<ApiPage<T>> Function(int, PagedState<T>) get _fetch =>
      (int page, PagedState<T> s) async {
        final result = await (this as dynamic).fetch(page, s);
        return result as ApiPage<T>;
      };

  Future<void> loadMore() async {
    final current = state;
    if (current.loadingMore || !current.hasMore) return;
    state = current.copyWith(loadingMore: true);
    try {
      final result = await _fetch(current.page + 1, current);
      state = state.copyWith(
        items: [...state.items, ...result.items],
        total: result.total,
        page: current.page + 1,
        loadingMore: false,
        error: null,
      );
    } catch (error) {
      state = state.copyWith(loadingMore: false, error: error);
    }
  }

  /// Debounced search: 350 ms so typing never floods the backend.
  void search(String value) {
    _debounces[this]?.cancel();
    _debounces[this] = Timer(const Duration(milliseconds: 350), () {
      state = state.copyWith(search: value);
      refresh();
    });
  }

  void setFilters({String? status, String? fromDate, String? toDate}) {
    state = state.copyWith(status: status, fromDate: fromDate, toDate: toDate);
    refresh();
  }
}
