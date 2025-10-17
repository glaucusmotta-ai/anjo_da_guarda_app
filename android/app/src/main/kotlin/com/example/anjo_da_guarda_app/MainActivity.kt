package com.example.anjo_da_guarda_app

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "sos_channel")
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "sendSos" -> {
                        val text = call.argument<String>("text") ?: "🚨 SOS ANJO DA GUARDA"
                        val lat = call.argument<Double>("lat")
                        val lon = call.argument<Double>("lon")
                        SosDispatcher(this).sendAll(text, lat, lon)
                        result.success(true)
                    }
                    else -> result.notImplemented()
                }
            }
    }
}
