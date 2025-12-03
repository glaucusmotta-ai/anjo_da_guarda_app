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
import 'theme/anjo_theme.dart';

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
          supportedLocales: const [
            Locale('en'),
            Locale('pt'),
            Locale('es'),
          ],
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

  // Hibernação manual (botão principal)
  bool hibernationOn = false;

  // Agenda automática de hibernação
  bool _hibAgendaEnabled = false;
  List<bool> _hibDays = List<bool>.filled(7, false); // 0=Seg ... 6=Dom
  int _hibStartMinutes = 8 * 60 + 30; // 08:30
  int _hibEndMinutes = 18 * 60; // 18:00

  static const _svcRunningKey = 'svc_running';
  static const _hibernationKey = 'hibernation_on';

  static const _hibAgendaEnabledKey = 'hib_agenda_enabled';
  static const _hibStartKey = 'hib_start_min';
  static const _hibEndKey = 'hib_end_min';
  static const _hibDayKeyPrefix = 'hib_day_';

  @override
  void initState() {
    super.initState();
    _restoreLastState();
  }

  // ---------- Persistência de status visual ----------
  Future<void> _restoreLastState() async {
    final sp = await SharedPreferences.getInstance();
    if (!mounted) return;

    setState(() {
      running = sp.getBool(_svcRunningKey) ?? false;
      hibernationOn = sp.getBool(_hibernationKey) ?? false;

      _hibAgendaEnabled = sp.getBool(_hibAgendaEnabledKey) ?? false;
      _hibStartMinutes = sp.getInt(_hibStartKey) ?? _hibStartMinutes;
      _hibEndMinutes = sp.getInt(_hibEndKey) ?? _hibEndMinutes;
      _hibDays = List<bool>.generate(7, (i) {
        return sp.getBool('$_hibDayKeyPrefix$i') ?? false;
      });
    });
  }

  Future<void> _saveRunning(bool value) async {
    final sp = await SharedPreferences.getInstance();
    await sp.setBool(_svcRunningKey, value);
  }

  Future<void> _saveHibernation(bool value) async {
    final sp = await SharedPreferences.getInstance();
    await sp.setBool(_hibernationKey, value);
  }

  Future<void> _saveHibAgenda() async {
    final sp = await SharedPreferences.getInstance();
    await sp.setBool(_hibAgendaEnabledKey, _hibAgendaEnabled);
    await sp.setInt(_hibStartKey, _hibStartMinutes);
    await sp.setInt(_hibEndKey, _hibEndMinutes);
    for (var i = 0; i < 7; i++) {
      await sp.setBool('$_hibDayKeyPrefix$i', _hibDays[i]);
    }
  }

  // ---------- Permissões ----------
  Future<bool> _ensurePermissions() async {
    final statuses = await [
      Permission.notification,
      Permission.microphone,
      Permission.location,
    ].request();

    final notifOk = statuses[Permission.notification]?.isGranted ?? true;
    final micOk = statuses[Permission.microphone]?.isGranted ?? false;
    final locOk = statuses[Permission.location]?.isGranted ?? false;

    if (!(micOk && locOk)) {
      if (!mounted) return false;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Precisamos de Microfone e Localização. '
            'Toque em "Permitir" ou habilite nas configurações.',
          ),
          duration: Duration(seconds: 3),
        ),
      );
      await openAppSettings();
      return false;
    }
    return notifOk && micOk && locOk;
  }

  // ---------- Ações ----------
  Future<void> _startServicePressed() async {
    final perms = await _ensurePermissions();
    if (!perms) return;

    setState(() => running = true);
    await _saveRunning(true);

    final ok = await startService();
    if (!mounted) return;

    if (!ok) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Serviço iniciado (modo compatível).'),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Serviço iniciado'),
        ),
      );
    }

    Navigator.of(context).pushNamed('/settings');
  }

  Future<void> _stopServicePressed() async {
    final ok = await stopService();
    if (!mounted) return;

    if (ok) {
      setState(() => running = false);
      await _saveRunning(false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Serviço parado')),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Falha ao parar serviço')),
      );
    }
  }

  Future<void> _toggleHibernation() async {
    final newValue = !hibernationOn;
    setState(() => hibernationOn = newValue);
    await _saveHibernation(newValue);
  }

  Future<void> _toggleHibAgenda() async {
    setState(() => _hibAgendaEnabled = !_hibAgendaEnabled);
    await _saveHibAgenda();
  }

  Future<void> _toggleHibDay(int index) async {
    setState(() {
      _hibDays[index] = !_hibDays[index];
    });
    await _saveHibAgenda();
  }

  TimeOfDay _minutesToTime(int minutes) {
    final h = minutes ~/ 60;
    final m = minutes % 60;
    return TimeOfDay(hour: h, minute: m);
  }

  String _formatMinutes(int minutes) {
    final t = _minutesToTime(minutes);
    final hh = t.hour.toString().padLeft(2, '0');
    final mm = t.minute.toString().padLeft(2, '0');
    return '$hh:$mm';
  }

  Future<void> _pickHibTime({required bool isStart}) async {
    final initialMinutes = isStart ? _hibStartMinutes : _hibEndMinutes;
    final initial = _minutesToTime(initialMinutes);

    final picked = await showTimePicker(
      context: context,
      initialTime: initial,
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: const ColorScheme.dark(
              primary: Colors.cyan,
              surface: Color(0xFF111216),
            ),
          ),
          child: child ?? const SizedBox.shrink(),
        );
      },
    );

    if (picked == null) return;

    final newMinutes = picked.hour * 60 + picked.minute;

    if (isStart) {
      setState(() {
        _hibStartMinutes = newMinutes;
        if (_hibEndMinutes < _hibStartMinutes) {
          _hibEndMinutes = _hibStartMinutes;
        }
      });
      await _saveHibAgenda();
    } else {
      if (newMinutes < _hibStartMinutes) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Horário fim não pode ser menor que o horário início.',
            ),
          ),
        );
        return;
      }
      setState(() {
        _hibEndMinutes = newMinutes;
      });
      await _saveHibAgenda();
    }
  }

  Widget _buildDayChip(int index, String label) {
    final selected = _hibDays[index];
    return GestureDetector(
      onTap: () => _toggleHibDay(index),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: selected ? AnjoTheme.neonGreen : Colors.white30,
            width: 1.2,
          ),
          color: selected ? Colors.white.withOpacity(0.08) : Colors.transparent,
        ),
        child: Text(
          label,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 12,
          ),
        ),
      ),
    );
  }

  // ---------- UI ----------
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AnjoTheme.bg,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        title: const Text(''),
        iconTheme: const IconThemeData(color: Colors.white),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            tooltip: 'Configurações',
            onPressed: () => Navigator.of(context).pushNamed('/settings'),
          ),
        ],
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFF050A1A), Color(0xFF0A1430)],
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 560),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.start,
                    children: [
                      const SizedBox(height: 8),
                      const Text(
                        'ANJO DA GUARDA',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 26,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 1.5,
                        ),
                      ),
                      const SizedBox(height: 24),

                      // CARD PRINCIPAL
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(24),
                          gradient: const LinearGradient(
                            colors: [
                              Color(0x3300FFFF),
                              Color(0x330066FF),
                            ],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                          border: Border.all(
                            color: AnjoTheme.neonBlue,
                            width: 1.5,
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: AnjoTheme.neonBlue.withOpacity(0.4),
                              blurRadius: 20,
                              spreadRadius: -5,
                              offset: const Offset(0, 8),
                            ),
                          ],
                        ),
                        child: Column(
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                              children: [
                                _NeonButton(
                                  label: 'Iniciar serviço',
                                  color: AnjoTheme.neonGreen,
                                  isActive: running,
                                  onTap: _startServicePressed,
                                ),
                                _NeonButton(
                                  label: 'Parar serviço',
                                  color: AnjoTheme.neonRed,
                                  isActive: !running,
                                  onTap: _stopServicePressed,
                                ),
                              ],
                            ),
                            const SizedBox(height: 16),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                const Text(
                                  'Estado do serviço:',
                                  style: TextStyle(
                                    color: Colors.white70,
                                    fontSize: 14,
                                  ),
                                ),
                                Text(
                                  running ? 'ATIVO' : 'INATIVO',
                                  style: TextStyle(
                                    color: running
                                        ? AnjoTheme.neonGreen
                                        : Colors.grey,
                                    fontWeight: FontWeight.bold,
                                    fontSize: 14,
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),

                      const SizedBox(height: 24),

                      // CARD HIBERNAÇÃO + AGENDA
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: AnjoTheme.cardBlue.withOpacity(0.8),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(
                            color: AnjoTheme.neonBlue.withOpacity(0.6),
                            width: 1,
                          ),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                const Text(
                                  'Modo hibernação',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 14,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                                GestureDetector(
                                  onTap: _toggleHibernation,
                                  child: _OnOffPill(isOn: hibernationOn),
                                ),
                              ],
                            ),
                            const SizedBox(height: 16),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                const Text(
                                  'Agenda automática',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 13,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                                GestureDetector(
                                  onTap: _toggleHibAgenda,
                                  child: _OnOffPill(isOn: _hibAgendaEnabled),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Container(
                              width: double.infinity,
                              padding: const EdgeInsets.symmetric(
                                horizontal: 12,
                                vertical: 10,
                              ),
                              decoration: BoxDecoration(
                                color: Colors.black.withOpacity(0.25),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(
                                _hibAgendaEnabled
                                    ? 'Agenda ligada'
                                    : 'Agenda desligada',
                                style: const TextStyle(
                                  color: Colors.white70,
                                  fontSize: 12,
                                ),
                              ),
                            ),
                            const SizedBox(height: 16),
                            const Text(
                              'Dias da semana:',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 13,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                            const SizedBox(height: 8),
                            Column(
                              children: [
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    _buildDayChip(0, 'Seg'),
                                    _buildDayChip(1, 'Ter'),
                                    _buildDayChip(2, 'Qua'),
                                    _buildDayChip(3, 'Qui'),
                                    _buildDayChip(4, 'Sex'),
                                  ],
                                ),
                                const SizedBox(height: 4),
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    _buildDayChip(5, 'Sáb'),
                                    _buildDayChip(6, 'Dom'),
                                  ],
                                ),
                              ],
                            ),
                            const SizedBox(height: 16),
                            const Text(
                              'Horário:',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 13,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                            const SizedBox(height: 8),
                            Row(
                              children: [
                                _HibTimeBox(
                                  label: 'Início',
                                  time: _formatMinutes(_hibStartMinutes),
                                  onTap: () =>
                                      _pickHibTime(isStart: true),
                                ),
                                _HibTimeBox(
                                  label: 'Fim',
                                  time: _formatMinutes(_hibEndMinutes),
                                  onTap: () =>
                                      _pickHibTime(isStart: false),
                                ),
                              ],
                            ),
                            const SizedBox(height: 16),
                            const Divider(
                              color: Colors.white24,
                              height: 1,
                            ),
                            const SizedBox(height: 12),
                            const Text(
                              'Quando hibernação está ON:',
                              style: TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.bold,
                                fontSize: 14,
                              ),
                            ),
                            const SizedBox(height: 8),
                            const Text(
                              '• SOS por voz (palavra-chave) PAUSADO\n'
                              '• PIN de coação continua funcionando\n'
                              '• Tile rápido continua funcionando',
                              style: TextStyle(
                                color: Colors.white70,
                                fontSize: 13,
                                height: 1.4,
                              ),
                            ),
                          ],
                        ),
                      ),

                      const SizedBox(height: 20),

                      const Text(
                        'Para configurar:\n'
                        'Use a engrenagem (⚙️) para configurar WhatsApp, SMS, '
                        'Email e Telegram.',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: Colors.white70,
                          fontSize: 13,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// botão com borda/brilho neon
class _NeonButton extends StatelessWidget {
  final String label;
  final Color color;
  final bool isActive;
  final VoidCallback onTap;

  const _NeonButton({
    required this.label,
    required this.color,
    required this.isActive,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final effectiveColor = isActive ? color : color.withOpacity(0.35);
    final shadows = isActive
        ? [
            BoxShadow(
              color: effectiveColor.withOpacity(0.4),
              blurRadius: 16,
              spreadRadius: -4,
              offset: const Offset(0, 6),
            ),
          ]
        : <BoxShadow>[];

    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          height: 44,
          margin: const EdgeInsets.symmetric(horizontal: 4),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(30),
            border: Border.all(color: effectiveColor, width: 1.5),
            boxShadow: shadows,
          ),
          alignment: Alignment.center,
          child: Text(
            label,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: effectiveColor,
              fontWeight: FontWeight.w600,
              fontSize: 13,
            ),
          ),
        ),
      ),
    );
  }
}

// pill ON/OFF usado nos toggles
class _OnOffPill extends StatelessWidget {
  final bool isOn;

  const _OnOffPill({required this.isOn});

  _OnOffPill copyWith({bool? isOn}) =>
      _OnOffPill(isOn: isOn ?? this.isOn);

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 72,
      height: 30,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        color: Colors.black.withOpacity(0.4),
        border: Border.all(color: Colors.white24),
      ),
      child: Stack(
        children: [
          Align(
            alignment: Alignment.centerRight,
            child: Padding(
              padding: const EdgeInsets.only(right: 8),
              child: Text(
                'OFF',
                style: TextStyle(
                  color: isOn ? Colors.white54 : Colors.white,
                  fontSize: 11,
                ),
              ),
            ),
          ),
          Align(
            alignment: Alignment.centerLeft,
            child: Padding(
              padding: const EdgeInsets.only(left: 8),
              child: Text(
                'ON',
                style: TextStyle(
                  color: isOn ? Colors.white : Colors.white54,
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
          AnimatedAlign(
            duration: const Duration(milliseconds: 200),
            curve: Curves.easeOut,
            alignment:
                isOn ? Alignment.centerLeft : Alignment.centerRight,
            child: Container(
              width: 30,
              height: 30,
              margin: const EdgeInsets.symmetric(horizontal: 1),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color:
                    isOn ? AnjoTheme.neonGreen : AnjoTheme.neonRed,
                boxShadow: [
                  BoxShadow(
                    color: (isOn
                            ? AnjoTheme.neonGreen
                            : AnjoTheme.neonRed)
                        .withOpacity(0.6),
                    blurRadius: 12,
                    spreadRadius: -2,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// caixinha de horário da agenda de hibernação
class _HibTimeBox extends StatelessWidget {
  final String label;
  final String time;
  final VoidCallback onTap;

  const _HibTimeBox({
    required this.label,
    required this.time,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 4),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: Colors.black.withOpacity(0.3),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.white24),
          ),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      label,
                      style: const TextStyle(
                        color: Colors.white60,
                        fontSize: 11,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      time,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(
                Icons.access_time,
                size: 18,
                color: Colors.white70,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
