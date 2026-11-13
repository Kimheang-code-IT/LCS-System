import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/auth/session.dart';
import '../l10n/app_localizations.dart';
import 'router.dart';
import 'theme.dart';

class LcsMobileApp extends ConsumerStatefulWidget {
  const LcsMobileApp({super.key});

  @override
  ConsumerState<LcsMobileApp> createState() => _LcsMobileAppState();
}

class _LcsMobileAppState extends ConsumerState<LcsMobileApp> {
  late final SessionRefresh _refresh;
  late final GoRouter _router;

  @override
  void initState() {
    super.initState();
    _refresh = SessionRefresh();
    _router = buildRouter(
      sessionState: () => ref.read(sessionProvider),
      refresh: _refresh,
    );
    // Restore the persisted session once at startup; a platform-channel
    // failure must not crash the app before the first frame.
    Future<void>.microtask(() async {
      try {
        await ref.read(sessionProvider.notifier).restore();
      } catch (_) {
        ref.read(sessionProvider.notifier).logoutLocal();
      }
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    ref.listenManual(sessionProvider, (previous, next) => _refresh.notify());
  }

  @override
  void dispose() {
    _refresh.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'LCS Finance',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      routerConfig: _router,
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      // Follow the device language; English is the fallback when the device
      // locale has no arb translation (e.g. anything but en/km).
      localeListResolutionCallback: (locales, supported) {
        for (final locale in locales ?? const <Locale>[]) {
          if (supported.contains(locale)) return locale;
          final languageOnly = Locale(locale.languageCode);
          if (supported.contains(languageOnly)) return languageOnly;
        }
        return const Locale('en');
      },
    );
  }
}
