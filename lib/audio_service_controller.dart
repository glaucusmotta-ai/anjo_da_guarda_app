import 'package:flutter/services.dart';
import 'package:permission_handler/permission_handler.dart';

class AudioCtl {
  static const _ch = MethodChannel('sos_audio_channel');

  static Future<String> start() async {
    // pede permissões (Android 13+ pede notificação também)
    await Permission.microphone.request();
    await Permission.notification.request();
    await _ch.invokeMethod('startService');
    return 'serviço iniciado';
  }

  static Future<String> stop() async {
    await _ch.invokeMethod('stopService');
    return 'serviço parado';
  }
}
