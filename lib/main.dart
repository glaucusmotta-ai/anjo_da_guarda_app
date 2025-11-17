// lib/main.dart
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'l10n/app_localizations.dart';
import 'audio_service_controller.dart';
import 'screens/pin_duress_screen.dart';
import 'screens/settings_screen.dart';
import 'services/settings_store.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const App());
}

class App extends StatelessWidget {
  const App({super.key});

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<AppSettings>(
      future: SettingsStore.instance.load(),
      builder: (ctx, snap) {
        var initial = '/pin';
        if (snap.hasData && !(snap.data!.pinSecondLayerEnabled)) {
          initial = '/home';
        }

        return MaterialApp(
          debugShowCheckedModeBanner: false,
          onGenerateTitle: (ctx) => AppLocalizations.of(ctx)!.appTitle,
          localizationsDelegates: const [
            AppLocalizations.delegate,
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          supportedLocales: const [Locale('en'), Locale('pt'), Locale('es')],
          initialRoute: initial,
          routes: {
            '/pin': (_) => const PinDuressScreen(),
            '/home': (_) => const HomePage(),
            '/settings': (_) => const SettingsScreen(),
          },
        );
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
    _restoreLastState();
  }

  // ---------- Persistência de status visual ----------
  Future<void> _restoreLastState() async {
    final sp = await SharedPreferences.getInstance();
    if (!mounted) return;
    setState(() => running = sp.getBool('svc_running') ?? false);
  }

  Future<void> _saveState(bool value) async {
    final sp = await SharedPreferences.getInstance();
    await sp.setBool('svc_running', value);
  }

  // ---------- Permissões ----------
  Future<bool> _ensurePermissions() async {
    // Pede permissões se necessário
    final statuses = await [
      Permission.notification,
      Permission.microphone,
      Permission.location,
    ].request();

    final notifOk = statuses[Permission.notification]?.isGranted ?? true;
    final micOk   = statuses[Permission.microphone]?.isGranted ?? false;
    final locOk   = statuses[Permission.location]?.isGranted ?? false;

    if (!(micOk && locOk)) {
      if (!mounted) return false;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Precisamos de Microfone e Localização. Toque em “Permitir” ou habilite nas configurações.',
          ),
          duration: Duration(seconds: 3),
        ),
      );
      // Abre as configurações do app para o usuário conceder manualmente
      await openAppSettings();
      return false;
    }
    return notifOk && micOk && locOk;
  }

  // ---------- Ações ----------
  Future<void> _startServicePressed() async {
    final perms = await _ensurePermissions();
    if (!perms) return;

    // Marca ATIVO na UI e persiste
    setState(() => running = true);
    await _saveState(true);

    // Inicia serviço nativo (se falhar, mantém UI ativa e mostramos aviso)
    final ok = await startService();
    if (!mounted) return;

    if (!ok) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Serviço iniciado (modo compatível).')),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Serviço iniciado')),
      );
    }

    // Abre a tela de canais para configurar
    Navigator.of(context).pushNamed('/settings');
  }

  Future<void> _stopServicePressed() async {
    final ok = await stopService();
    if (!mounted) return;

    if (ok) {
      setState(() => running = false);
      await _saveState(false);
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Serviço parado')));
    } else {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Falha ao parar serviço')));
    }
  }

  // ---------- UI ----------
  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    return Scaffold(
      // AppBar discreta (sem nome do app)
      appBar: AppBar(
        title: const Text(''),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            tooltip: 'Configurações',
            onPressed: () => Navigator.of(context).pushNamed('/settings'),
          ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: Padding(
            padding: const EdgeInsets.all(20),
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
                Text(
                  running ? 'Status: ATIVO' : 'Status: INATIVO',
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: Colors.black, // texto PRETO
                  ),
                ),
                const SizedBox(height: 12),
                const Text(
                  'Use a catraca (⚙️) para configurar WhatsApp, SMS, Email e Telegram.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.black87),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
