// lib/main.dart
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:permission_handler/permission_handler.dart';

import 'l10n/app_localizations.dart';
import 'audio_service_controller.dart';
import 'screens/pin_duress_screen.dart';
import 'screens/settings_screen.dart'; // <-- CORRETO: tela de Configurações

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

      // PIN como primeira tela
      initialRoute: '/pin',
      routes: {
        '/pin': (_) => const PinDuressScreen(),
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
    return notifOk && micOk && locOk;
  }

  Future<void> _startServicePressed() async {
    if (!await _ensurePermissions()) return;
    final ok = await startService();
    if (!mounted) return;
    setState(() => running = ok);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(ok ? AppLocalizations.of(context)!.serviceStarted : 'Falha ao iniciar o serviço')),
    );
  }

  Future<void> _stopServicePressed() async {
    final ok = await stopService();
    if (!mounted) return;
    setState(() => running = !ok);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(ok ? AppLocalizations.of(context)!.serviceStopped : 'Falha ao parar o serviço')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    return Scaffold(
      appBar: AppBar(title: Text(t.appTitle)),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ElevatedButton(onPressed: _startServicePressed, child: const Text('Iniciar serviço')),
            const SizedBox(height: 12),
            ElevatedButton(onPressed: _stopServicePressed, child: const Text('Parar serviço')),
            const SizedBox(height: 20),
            Text(running ? 'Status: ATIVO' : 'Status: INATIVO'),
          ],
        ),
      ),
    );
  }
}
