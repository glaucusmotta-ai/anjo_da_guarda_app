// lib/audio_service_controller.dart
import 'package:flutter/services.dart';

const MethodChannel _ch = MethodChannel('anjo/native_sos');

Future<bool> startService() async {
  final ok = await _ch.invokeMethod<bool>('startService');
  return ok == true;
}

Future<bool> stopService() async {
  final ok = await _ch.invokeMethod<bool>('stopService');
  return ok == true;
}

Future<bool> isServiceRunning() async {
  final ok = await _ch.invokeMethod<bool>('isServiceRunning');
  return ok == true;
}
