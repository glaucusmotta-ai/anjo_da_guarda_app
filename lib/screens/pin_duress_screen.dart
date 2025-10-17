// lib/screens/pin_duress_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:geolocator/geolocator.dart';

import '../services/native_sos.dart';

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
    // Reentrância
    if (_isProcessing) return;
    _isProcessing = true;

    // Validação forte: exatamente 4 dígitos
    final is4digits = RegExp(r'^\d{4}$').hasMatch(pin);
    if (!is4digits) {
      _isProcessing = false;
      return;
    }

    // Stealth: fecha teclado (só depois de validar)
    FocusScope.of(context).unfocus();

    // ===== COAÇÃO =====
    if (pin == _pinDuress) {
      // Debounce 5s
      final now = DateTime.now();
      if (_lastDuress != null && now.difference(_lastDuress!) < const Duration(seconds: 5)) {
        _isProcessing = false;
        return;
      }
      _lastDuress = now;

      final (lat, lon, acc) = await _tryGetLatLon();
      final accTxt = (acc != null) ? " (±${acc.round()} m)" : "";
      await NativeSos.send("🚨 SOS – COAÇÃO$accTxt", lat: lat, lon: lon);

      if (!mounted) return;
      // Limpa campo e vai para tela neutra
      _ctrl.clear();
      _isProcessing = false;

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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
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
                  style: const TextStyle(fontSize: 28, letterSpacing: 8, color: Colors.white),
                  decoration: const InputDecoration(
                    counterText: "",
                    border: InputBorder.none,
                  ),
                  onChanged: _onChanged,
                  onSubmitted: _handlePin,
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
  Widget build(BuildContext context) => const Scaffold(backgroundColor: Colors.black);
}
