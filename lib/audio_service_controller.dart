import 'package:flutter/services.dart';

const _channel = MethodChannel('sos_audio_channel');

Future<bool> startService() async {
  final ok = await _channel.invokeMethod('startService');
  return (ok == true);
}

Future<bool> stopService() async {
  final ok = await _channel.invokeMethod('stopService');
  return (ok == true);
}
