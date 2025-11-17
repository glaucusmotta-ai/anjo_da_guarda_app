// lib/services/sos_client.dart
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:geolocator/geolocator.dart';

/// Resultado padrão de chamadas HTTP do backend
class ApiResult {
  final bool ok;
  final int status;
  final dynamic data;
  final String? error;
  const ApiResult({required this.ok, required this.status, this.data, this.error});
}

/// Base da API
/// - Emulador Android: http://10.0.2.2:8000
/// - Dispositivo físico: use --dart-define=SOS_BASE_URL=https://SEU-NGROK.ngrok-free.dev
const String _BASE_URL =
    String.fromEnvironment('SOS_BASE_URL', defaultValue: 'http://10.0.2.2:8000');

const Duration _httpTimeout = Duration(seconds: 15);
const Duration _geoTimeout  = Duration(seconds: 7);

class SosClient {
  // ----------------- Localização -----------------
  static Future<Map<String, dynamic>> _getLocation() async {
    try {
      var perm = await Geolocator.checkPermission();
      if (perm == LocationPermission.denied) {
        perm = await Geolocator.requestPermission();
      }
      if (perm == LocationPermission.deniedForever || perm == LocationPermission.denied) {
        return {};
      }

      final pos = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      ).timeout(_geoTimeout, onTimeout: () async {
        final last = await Geolocator.getLastKnownPosition();
        if (last != null) return last;
        throw TimeoutException('geo timeout');
      });

      return {
        'lat': pos.latitude,
        'lon': pos.longitude,
        'acc': pos.accuracy,
      };
    } catch (_) {
      return {};
    }
  }

  // ----------------- HTTP helper -----------------
  static Future<ApiResult> _postJson(String path, Map<String, dynamic> body) async {
    final uri = Uri.parse('$_BASE_URL$path');
    try {
      final resp = await http
          .post(
            uri,
            headers: const {
              'Content-Type': 'application/json; charset=utf-8',
              'Accept': 'application/json'
            },
            body: jsonEncode(body),
          )
          .timeout(_httpTimeout);

      dynamic data;
      try {
        data = jsonDecode(resp.body);
      } catch (_) {
        data = resp.body;
      }

      return ApiResult(ok: resp.statusCode >= 200 && resp.statusCode < 300, status: resp.statusCode, data: data);
    } on TimeoutException {
      return const ApiResult(ok: false, status: 0, data: 'timeout', error: 'timeout');
    } catch (e) {
      return ApiResult(ok: false, status: 0, data: e.toString(), error: e.toString());
    }
  }

  static String _composeText({required bool duress, String? note, String base = 'SOS – ANJO DA GUARDA'}) {
    final prefix = duress ? '🚨 $base – COAÇÃO' : '🚨 $base';
    return (note != null && note.isNotEmpty) ? '$prefix – $note' : prefix;
  }

  // =========================================================
  // A) ÚNICO: Disparo genérico via /api/sos
  //    - Backend decide: WA texto ou WA template (conforme .env)
  //    - Pode enviar 'destinatarios' (override da lista do backend)
  //    - Se 'text' vier preenchido, backend usa no modo texto
  // =========================================================
  static Future<ApiResult> sendSos({
    String? text,                    // para modo texto (WA/SMS compat no backend)
    String? nome,                    // usado pelo template WA (campo {{nome}})
    List<String>? destinatarios,     // override destino WA
    double? lat,
    double? lon,
    double? acc,
  }) async {
    Map<String, dynamic> loc;
    if (lat != null && lon != null) {
      loc = {'lat': lat, 'lon': lon, if (acc != null) 'acc': acc};
    } else {
      loc = await _getLocation();
    }
    if (!(loc.containsKey('lat') && loc.containsKey('lon'))) {
      return const ApiResult(ok: false, status: 0, data: 'no_gps', error: 'no_gps');
    }

    final body = <String, dynamic>{
      ...loc,
      if (text != null && text.isNotEmpty) 'text': text,
      if (nome != null && nome.isNotEmpty) 'nome': nome,
      if (destinatarios != null && destinatarios.isNotEmpty) 'destinatarios': destinatarios,
    };

    return _postJson('/api/sos', body);
  }

  // =========================================================
  // B) WhatsApp (atalho) — usa /api/sos por trás
  // =========================================================
  static Future<ApiResult> sendWaViaBackend({
    required String nome,
    required List<String> destinatarios,
    double? lat,
    double? lon,
    double? acc,
    String? textOverride, // se quiser forçar modo texto
  }) {
    return sendSos(
      nome: nome,
      destinatarios: destinatarios,
      lat: lat,
      lon: lon,
      acc: acc,
      text: textOverride,
    );
  }

  // =========================================================
  // C) SMS — chama /api/sos/sms (backend já gera texto padrão)
  // =========================================================
  static Future<ApiResult> sendSms({
    required List<String> toList,
    bool duress = false,
    String? note,
    double? lat,
    double? lon,
    double? acc,
  }) async {
    if (toList.isEmpty) {
      return const ApiResult(ok: false, status: 0, data: 'empty_to_list', error: 'empty_to_list');
    }

    final loc = (lat != null && lon != null)
        ? {'lat': lat, 'lon': lon, if (acc != null) 'acc': acc}
        : await _getLocation();

    if (!(loc.containsKey('lat') && loc.containsKey('lon'))) {
      return const ApiResult(ok: false, status: 0, data: 'no_gps', error: 'no_gps');
    }

    final body = {
      ...loc,
      'text': _composeText(duress: duress, note: note),
      'to_list': toList,
    };

    return _postJson('/api/sos/sms', body);
  }

  // =========================================================
  // D) Compat: endpoint antigo /api/sos (legado com s1/s2)
  // =========================================================
  static Future<ApiResult> sendOnce({required bool duress, String? note}) async {
    final loc = await _getLocation();
    if (!(loc.containsKey('lat') && loc.containsKey('lon'))) {
      return const ApiResult(ok: false, status: 0, data: 'no_gps', error: 'no_gps');
    }
    final body = {
      ...loc,
      'text': _composeText(duress: duress, note: note),
      's1': '',
      's2': '',
    };
    return _postJson('/api/sos', body);
  }

  /// Disparo periódico simples (modo legado)
  static Future<void> sendPeriodic({
    required bool duress,
    Duration every = const Duration(minutes: 1),
    int times = 15,
  }) async {
    for (var i = 0; i < times; i++) {
      await sendOnce(duress: duress, note: 'T${i + 1}/$times');
      await Future.delayed(every);
    }
  }
}
