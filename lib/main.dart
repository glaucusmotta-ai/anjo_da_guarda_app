import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:permission_handler/permission_handler.dart';

import 'l10n/app_localizations.dart';
import 'audio_service_controller.dart';
import 'screens/pin_duress_screen.dart';
import 'screens/settings_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const App());
}

class App extends StatelessWidget {
  const App({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      onGenerateTitle: (ctx) => AppLocalizations.of(ctx)!.appTitle,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,

      // Inicia no PIN (duress)
      home: const PinDuressScreen(),

      // Rotas
      routes: {
        '/home': (_) => const HomePage(),
        '/settings': (_) => const SettingsScreen(),
      },
    );
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  bool running = false;

  @override
  void initState() {
    super.initState();
    _ensurePermissions();
  }

  Future<bool> _ensurePermissions() async {
    final statuses = await [
      Permission.notification,
      Permission.microphone,
      Permission.location,
    ].request();

    final notifOk = statuses[Permission.notification]?.isGranted ?? true;
    final micOk = statuses[Permission.microphone]?.isGranted ?? false;
    final locOk = statuses[Permission.location]?.isGranted ?? false;

    if (micOk && locOk && notifOk) return true;

    final missing = <String>[];
    if (!micOk) missing.add('Microfone');
    if (!locOk) missing.add('Localização');
    if (!notifOk) missing.add('Notificações');

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Permissões necessárias: ${missing.join(", ")}')),
      );
    }
    return false;
  }

  Future<void> _startServicePressed() async {
    final okPerms = await _ensurePermissions();
    if (!okPerms) return;

    final ok = await startService();
    if (!mounted) return;

    if (ok) {
      setState(() => running = true);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context)!.serviceStarted)),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Falha ao iniciar o serviço')),
      );
    }
  }

  Future<void> _stopServicePressed() async {
    final ok = await stopService();
    if (!mounted) return;

    if (ok) {
      setState(() => running = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context)!.serviceStopped)),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Falha ao parar o serviço')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;

    return Scaffold(
      appBar: AppBar(
        title: Text(t.appTitle),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            tooltip: 'Configurações',
            onPressed: () => Navigator.of(context).pushNamed('/settings'),
          ),
        ],
      ),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ElevatedButton(
              onPressed: _startServicePressed,
              child: const Text('Iniciar serviço'),
            ),
            const SizedBox(height: 12),
            ElevatedButton(
              onPressed: _stopServicePressed,
              child: const Text('Parar serviço'),
            ),
            const SizedBox(height: 20),
            Text(running ? 'Status: ATIVO' : 'Status: INATIVO'),
          ],
        ),
      ),
    );
  }
}
