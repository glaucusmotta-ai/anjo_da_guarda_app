// lib/services/native_sos.dart
//
// Camada Flutter -> nativo (Kotlin).
// Aqui NÃO tem lógica de template, Zenvia, ACC, etc.
// Só empacotamos texto, localização e destinos (SettingsStore)
// e repassamos para o código nativo, que sabe como montar
// a mensagem aprovada pela Meta/Zenvia.

import 'dart:async';

import 'package:flutter/services.dart';
import 'package:geolocator/geolocator.dart';
import 'settings_store.dart';

class NativeSos {
  // IMPORTANTE:
  // Esses nomes de canal precisam bater exatamente
  // com os que você registrou no MainActivity.kt.
  static const MethodChannel _ch = MethodChannel('anjo/native_sos');

  // Fallback de compatibilidade com sua versão antiga
  static const MethodChannel _chLegacy = MethodChannel('anjo_da_guarda/native');

  // --------- Controle de loop de live tracking ---------
  static Timer? _liveTrackTimer;
  static bool _liveTrackActive = false;

  /// Inicia o serviço de áudio (foreground)
  static Future<bool> startService() async {
    try {
      final ok = await _ch.invokeMethod<bool>('startService');
      return ok == true;
    } catch (_) {
      // Versão legada não tinha start/stop; apenas retornamos false
      return false;
    }
  }

  /// Para o serviço de áudio
  static Future<bool> stopService() async {
    try {
      final ok = await _ch.invokeMethod<bool>('stopService');
      return ok == true;
    } catch (_) {
      return false;
    }
  }

  /// Verifica se o serviço está ativo (para mostrar ATIVO/INATIVO na UI)
  static Future<bool> isServiceRunning() async {
    try {
      final ok = await _ch.invokeMethod<bool>('isServiceRunning');
      return ok == true;
    } catch (_) {
      return false;
    }
  }

  /// Envia SOS usando:
  /// - texto fornecido pela tela (por ex.: "SOS pessoal"),
  /// - lat/lon (se disponíveis),
  /// - nome (opcional),
  /// - destinatários salvos no SettingsStore.
  ///
  /// O código nativo é que vai montar a mensagem no formato
  /// aprovado pela Meta/Zenvia.
  static Future<bool> send(
    String text, {
    double? lat,
    double? lon,
    String? nome,
  }) async {
    final s = await SettingsStore.instance.load();

    String? _nz(String? v) {
      final t = (v ?? '').trim();
      return t.isEmpty ? null : t;
    }

    List<String> _clean(List<String?> xs) => xs
        .map(_nz)
        .where((e) => e != null && e!.isNotEmpty)
        .map((e) => e!)
        .toList();

    final args = <String, dynamic>{
      'text': text,
      if (lat != null) 'lat': lat,
      if (lon != null) 'lon': lon,
      if (nome != null && nome.trim().isNotEmpty) 'nome': nome.trim(),
      if (_nz(s.tgTarget) != null) 'tgTarget': _nz(s.tgTarget),
      'smsTo': _clean([s.smsTo1, s.smsTo2, s.smsTo3]),
      'waTo': _clean([s.waTo1, s.waTo2, s.waTo3]),
      'emailTo': _clean([s.emailTo1, s.emailTo2, s.emailTo3]),
    };

    // DEBUG opcional (se quiser ver o pacote indo pro nativo)
    // print('NativeSos.send args: $args');

    // Tentativa primária (canal/método novo)
    try {
      final ok = await _ch.invokeMethod<bool>('send', args);
      if (ok == true) return true;
    } catch (_) {
      // cai no fallback
    }

    // Fallback p/ legado (handler antigo: sosSend no canal anjo_da_guarda/native)
    try {
      final okLegacy = await _chLegacy.invokeMethod<bool>('sosSend', args);
      return okLegacy == true;
    } catch (_) {
      return false;
    }
  }

  /// Utilitário: tenta posição atual rapidamente (com fallback p/ última conhecida).
  static Future<(double?, double?)> quickLatLon() async {
    try {
      final enabled = await Geolocator.isLocationServiceEnabled();
      if (!enabled) return (null, null);

      var perm = await Geolocator.checkPermission();
      if (perm == LocationPermission.denied) {
        perm = await Geolocator.requestPermission();
      }
      if (perm == LocationPermission.denied ||
          perm == LocationPermission.deniedForever) {
        return (null, null);
      }

      try {
        final pos = await Geolocator.getCurrentPosition(
          timeLimit: const Duration(seconds: 6),
          desiredAccuracy: LocationAccuracy.best,
        );
        return (pos.latitude, pos.longitude);
      } catch (_) {
        final last = await Geolocator.getLastKnownPosition();
        if (last == null) return (null, null);
        return (last.latitude, last.longitude);
      }
    } catch (_) {
      return (null, null);
    }
  }

  // =====================================================
  // Live tracking: loop que manda lat/lon para o nativo
  //   -> MainActivity.liveTrackUpdate -> SosDispatcher.liveTrackUpdate
  // =====================================================
  static Future<void> _liveTrackTick() async {
    try {
      final (lat, lon) = await quickLatLon();
      if (lat == null || lon == null) return;

      await _ch.invokeMethod<void>('liveTrackUpdate', {
        'lat': lat,
        'lon': lon,
      });
    } catch (_) {
      // silencioso
    }
  }

  /// Inicia o loop periódico de live tracking.
  /// Intervalo padrão: 15 segundos.
  static Future<void> startLiveTrackingLoop({
    Duration interval = const Duration(seconds: 15),
  }) async {
    if (_liveTrackActive) return;
    _liveTrackActive = true;

    // dispara uma vez imediatamente
    await _liveTrackTick();

    _liveTrackTimer?.cancel();
    _liveTrackTimer = Timer.periodic(interval, (_) async {
      if (!_liveTrackActive) return;
      await _liveTrackTick();
    });
  }

  /// Para o loop de live tracking.
  static Future<void> stopLiveTrackingLoop() async {
    _liveTrackActive = false;
    _liveTrackTimer?.cancel();
    _liveTrackTimer = null;
  }
}
