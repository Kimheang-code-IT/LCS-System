import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/auth/session.dart';
import '../../../core/widgets/common.dart';
import '../../../l10n/app_localizations.dart';
import 'dashboard_shortcuts.dart';

/// Navigation-only dashboard: a responsive three-column grid of shortcuts to
/// the existing Finance/Accounting/Reports routes. All financial summaries,
/// statistics and API loading were removed — the four summary cards and the
/// cash/bank figure live in the web app; the mobile shortcut screens each
/// fetch their own real data.
class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = AppLocalizations.of(context)!;
    final user = ref.watch(sessionProvider.select((s) => s.user));

    // Shortcuts the current role cannot open are hidden, per spec.
    final visible = dashboardShortcuts()
        .where((shortcut) => user?.can(shortcut.permission) ?? false)
        .toList();

    return Scaffold(
      appBar: AppBar(
        title: Text(t.appTitle),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout_outlined),
            tooltip: t.logout,
            onPressed: () => _logout(context, ref),
          ),
        ],
      ),
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            // Three columns on normal phone widths; extra width can host a
            // fourth column so large screens/tablets stay uncluttered.
            final columns = constraints.maxWidth > 640 ? 4 : 3;
            return SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(12),
              child: GridView.count(
                crossAxisCount: columns,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 4,
                crossAxisSpacing: 4,
                childAspectRatio: 0.92,
                padding: EdgeInsets.zero,
                children: [
                  for (final shortcut in visible)
                    DashboardShortcutCard(
                      label: shortcut.label(t),
                      icon: shortcut.icon,
                      dotColor: shortcut.dotColor,
                      onTap: () => _open(context, shortcut),
                    ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }

  void _open(BuildContext context, DashboardShortcut shortcut) {
    // The four bottom-nav branches switch tabs; everything else pushes a page
    // on the root navigator (duplicate taps are ignored by go_router while a
    // push is already in flight).
    if (shortcut.tab) {
      context.go(shortcut.route);
      return;
    }
    context.push(shortcut.route, extra: shortcut.extra);
  }

  Future<void> _logout(BuildContext context, WidgetRef ref) async {
    final t = AppLocalizations.of(context)!;
    final confirmed = await confirmAction(
      context,
      title: t.logout,
      message: '${t.logout} — ${t.appTitle}?',
      confirmLabel: t.logout,
    );
    if (!confirmed) return;
    await ref.read(sessionProvider.notifier).logout();
  }
}
