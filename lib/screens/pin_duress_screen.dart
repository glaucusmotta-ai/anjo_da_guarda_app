// lib/screens/pin_duress_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:geolocator/geolocator.dart';
import 'package:permission_handler/permission_handler.dart';

import '../services/native_sos.dart';
import '../audio_service_controller.dart'; // isServiceRunning()

class PinDuressScreen extends StatefulWidget {
  const PinDuressScreen({super.key});
  @override
  State<PinDuressScreen> createState() => _PinDuressScreenState();
}

class _PinDuressScreenState extends State<PinDuressScreen> {
  final _ctrl = TextEditingController();
  static const int _pinLen = 4;

  String _hint = "Digite seu PIN";

  static const _kPinMainKey = "pin_main";
  static const _kPinDuressKey = "pin_duress";

  String _pinMain = "1234";
  String _pinDuress = "2580";

  // Guardas anti-disparo indevido
  bool _isProcessing = false;
  DateTime? _lastDuress; // anti-repetição

  @override
  void initState() {
    super.initState();
    _loadPins();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _loadPins() async {
    final sp = await SharedPreferences.getInstance();
    setState(() {
      _pinMain = sp.getString(_kPinMainKey) ?? _pinMain;
      _pinDuress = sp.getString(_kPinDuressKey) ?? _pinDuress;
    });
  }

  Future<(double?, double?, double?)> _tryGetLatLon() async {
    try {
      final svc = await Geolocator.isLocationServiceEnabled();
      if (!svc) return (null, null, null);

      var perm = await Geolocator.checkPermission();
      if (perm == LocationPermission.denied) {
        perm = await Geolocator.requestPermission();
      }
      if (perm == LocationPermission.denied || perm == LocationPermission.deniedForever) {
        return (null, null, null);
      }

      try {
        final pos = await Geolocator.getCurrentPosition(
          desiredAccuracy: LocationAccuracy.best,
          timeLimit: const Duration(seconds: 8),
        );
        return (pos.latitude, pos.longitude, pos.accuracy);
      } catch (_) {
        final last = await Geolocator.getLastKnownPosition();
        if (last == null) return (null, null, null);
        return (last.latitude, last.longitude, last.accuracy);
      }
    } catch (_) {
      return (null, null, null);
    }
  }

  Future<void> _handlePin(String pin) async {
    if (_isProcessing) return;
    _isProcessing = true;

    // Exatamente 4 dígitos
    final is4digits = RegExp(r'^\d{4}$').hasMatch(pin);
    if (!is4digits) {
      _isProcessing = false;
      return;
    }

    // Stealth: fecha teclado
    FocusScope.of(context).unfocus();

    // ===== COAÇÃO =====
    if (pin == _pinDuress) {
      // Só dispara se o serviço de áudio estiver ATIVO
      final active = await isServiceRunning();
      if (!active) {
        _ctrl.clear();
        _isProcessing = false;
        return;
      }

      // debounce 5s entre disparos
      final now = DateTime.now();
      if (_lastDuress != null && now.difference(_lastDuress!) < const Duration(seconds: 5)) {
        _isProcessing = false;
        return;
      }
      _lastDuress = now;

      // Pega localização inicial para o primeiro alerta + startLiveTrack
      final (lat, lon, _) = await _tryGetLatLon();

      // Texto no padrão que o nativo espera (ALERTA de Contato)
      final ok = await NativeSos.send(
        "🚨 ALERTA de Contato\nSituação: sos pessoal\nSe não puder ajudar, encaminhe às autoridades.",
        lat: lat,
        lon: lon,
      );

      // Se o envio principal foi OK, liga o loop de live tracking
      if (ok) {
        await NativeSos.startLiveTrackingLoop();
      }

      _ctrl.clear();
      _isProcessing = false;

      await Future.delayed(const Duration(milliseconds: 600));
      if (!mounted) return;

      // Fecha/minimiza a atividade para modo stealth
      SystemNavigator.pop();

      // Opcional: fallback para tela preta se a atividade não fechar
      Future.delayed(const Duration(seconds: 1), () {
        if (mounted) {
          Navigator.of(context).pushReplacement(
            MaterialPageRoute(builder: (_) => const _BlankScreen()),
          );
        }
      });
      return;
    }

    // ===== PIN normal =====
    if (pin == _pinMain) {
      _ctrl.clear();
      _isProcessing = false;
      if (mounted) Navigator.of(context).pushReplacementNamed("/home");
      return;
    }

    // ===== PIN incorreto =====
    _ctrl.clear();
    _isProcessing = false;
    if (!mounted) return;
    setState(() => _hint = "PIN incorreto");
    Future.delayed(const Duration(seconds: 1), () {
      if (mounted) setState(() => _hint = "Digite seu PIN");
    });
  }

  Future<void> _onChanged(String v) async {
    if (v.length < _pinLen) return;
    await _handlePin(v);
  }

  // ===== Menu da “catraca” =====
  Future<void> _requestCorePerms() async {
    final statuses = await [
      Permission.notification,
      Permission.microphone,
      Permission.location,
    ].request();

    final notifOk = statuses[Permission.notification]?.isGranted ?? true;
    final micOk   = statuses[Permission.microphone]?.isGranted ?? false;
    final locOk   = statuses[Permission.location]?.isGranted ?? false;

    if (!mounted) return;
    final msg = 'Notificações: ${notifOk ? "OK" : "NÃO"} | '
        'Microfone: ${micOk ? "OK" : "NÃO"} | '
        'Localização: ${locOk ? "OK" : "NÃO"}';
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  void _openHomeDebug() {
    Navigator.of(context).pushReplacementNamed('/home');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,

      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        elevation: 0,
        systemOverlayStyle: SystemUiOverlayStyle.light,
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            tooltip: 'Menu',
            onPressed: () {
              showModalBottomSheet(
                context: context,
                showDragHandle: true,
                builder: (c) => SafeArea(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      ListTile(
                        leading: const Icon(Icons.lock_reset),
                        title: const Text('Solicitar permissões do app'),
                        subtitle: const Text('Notificações, Microfone e Localização'),
                        onTap: () async {
                          Navigator.pop(c);
                          await _requestCorePerms();
                        },
                      ),
                      ListTile(
                        leading: const Icon(Icons.home_outlined),
                        title: const Text('Abrir Home (debug)'),
                        onTap: () {
                          Navigator.pop(c);
                          _openHomeDebug();
                        },
                      ),
                      ListTile(
                        leading: const Icon(Icons.settings),
                        title: const Text('Configurações'),
                        onTap: () {
                          Navigator.pop(c);
                          Navigator.of(context).pushNamed('/settings');
                        },
                      ),
                      const SizedBox(height: 8),
                    ],
                  ),
                ),
              );
            },
          ),
        ],
      ),

      body: SafeArea(
        child: Center(
          child: SizedBox(
            width: 280,
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.lock_outline, size: 48, color: Colors.white70),
                const SizedBox(height: 16),
                Text(_hint, style: const TextStyle(color: Colors.white70)),
                const SizedBox(height: 8),
                TextField(
                  controller: _ctrl,
                  autofocus: true,
                  obscureText: true,
                  obscuringCharacter: '•',
                  maxLength: _pinLen,
                  maxLengthEnforcement: MaxLengthEnforcement.enforced,
                  keyboardType: TextInputType.number,
                  textInputAction: TextInputAction.done,
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  enableSuggestions: false,
                  autocorrect: false,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 28,
                    letterSpacing: 8,
                    color: Colors.white,
                  ),
                  decoration: const InputDecoration(
                    counterText: "",
                    border: InputBorder.none,
                  ),
                  onChanged: _onChanged,
                  onSubmitted: (v) => _handlePin(v),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _BlankScreen extends StatelessWidget {
  const _BlankScreen();
  @override
  Widget build(BuildContext context) =>
      const Scaffold(backgroundColor: Colors.black);
}
