// lib/services/sos_client.dart
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:geolocator/geolocator.dart';

class SosClient {
  // Emulador → host local: use 10.0.2.2; ajuste se seu backend estiver em outro host/porta.
  static const String _apiBase = 'http://10.0.2.2:8000';
  static const String _endpoint = '$_apiBase/api/sos';

  static Future<Map<String, dynamic>> _tryGetLoc() async {
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
      ).timeout(const Duration(seconds: 5));
      return {
        "lat": pos.latitude,
        "lon": pos.longitude,
        "acc": pos.accuracy,
      };
    } catch (_) {
      return {};
    }
  }

  static Future<void> sendOnce({required bool duress, String? note}) async {
    final loc = await _tryGetLoc();
    final body = {
      ...loc,
      "text": duress ? "🚨 SOS – COAÇÃO${note!=null ? " – $note" : ""}" : "🚨 SOS${note!=null ? " – $note" : ""}",
      "s1": "", // se o backend usar, preencha aqui
      "s2": "", // idem
    };
    await http.post(Uri.parse(_endpoint),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode(body));
  }

  /// Envia localização silenciosa a cada [every], total de [times] vezes.
  static Future<void> sendPeriodic({required bool duress, Duration every = const Duration(minutes: 1), int times = 15}) async {
    for (var i = 0; i < times; i++) {
      await sendOnce(duress: duress, note: "T${i+1}/$times");
      await Future.delayed(every);
    }
  }
}
