import 'package:flutter/services.dart';

class NativeSos {
  static const _ch = MethodChannel('sos_channel');

  static Future<void> send(String text, {double? lat, double? lon}) async {
    await _ch.invokeMethod('sendSos', {
      'text': text,
      if (lat != null) 'lat': lat,
      if (lon != null) 'lon': lon,
    });
  }
}
