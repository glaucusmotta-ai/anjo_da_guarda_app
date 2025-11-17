package com.example.anjo_da_guarda_app

import android.content.Intent
import android.os.Build
import androidx.core.content.ContextCompat
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import android.util.Log

class MainActivity : FlutterActivity() {

    private val CH_LEGACY = "anjo_da_guarda/native"
    private val CH_SOS    = "anjo/native_sos"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        // ===== Canal legado (NÃO MEXE NO WHATSAPP): sosSend =====
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CH_LEGACY)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "sosSend" -> {
                        val text     = call.argument<String>("text") ?: "🚨 SOS ANJO DA GUARDA"
                        val lat      = call.argument<Double>("lat")
                        val lon      = call.argument<Double>("lon")
                        val tgTarget = call.argument<String>("tgTarget")

                        val smsTo    = call.argument<ArrayList<String>>("smsTo")   ?: arrayListOf()
                        val waTo     = call.argument<ArrayList<String>>("waTo")    ?: arrayListOf()
                        val emailTo  = call.argument<ArrayList<String>>("emailTo") ?: arrayListOf()

                        android.widget.Toast.makeText(this, "sosSend chamado", android.widget.Toast.LENGTH_SHORT).show()
                        android.util.Log.d("SOSDBG", "sosSend: recebendo do Dart (tgTarget, smsTo=${smsTo.size}, waTo=${waTo.size}, emailTo=${emailTo.size})")

                        Log.d("ANJO_SOS", "sosSend() chamado")
                        Log.d("ANJO_SOS", "tgTarget=" + (tgTarget ?: "null"))
                        Log.d("ANJO_SOS", "smsTo.size=" + smsTo.size + " waTo.size=" + waTo.size + " emailTo.size=" + emailTo.size)
                        Log.d("ANJO_SOS", "lat=" + (lat?.toString() ?: "null") + " lon=" + (lon?.toString() ?: "null"))

                        SosDispatcher(this).sendAll(
                            text = text,
                            lat = lat, lon = lon,
                            tgTarget = tgTarget,
                            smsTo = smsTo,
                            waTo = waTo,
                            emailTo = emailTo
                        )
                        result.success(true)
                    }
                    else -> result.notImplemented()
                }
            }

        // ===== Canal novo de controle do serviço (voz) =====
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CH_SOS)
            .setMethodCallHandler { call, result ->
                when (call.method) {

                    // Iniciar serviço (alias "audioStart")
                    "startService", "audioStart" -> {
                        try {
                            if (!AudioService.isRunning) {
                                val i = Intent(this, AudioService::class.java)
                                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                                    ContextCompat.startForegroundService(this, i)
                                } else {
                                    startService(i)
                                }
                            }
                            result.success(true)
                        } catch (t: Throwable) {
                            result.error("START_FAIL", t.message, null)
                        }
                    }

                    // Parar serviço (alias "audioStop") — não inicia se já estiver parado
                    "stopService", "audioStop" -> {
                        try {
                            if (!AudioService.isRunning) {
                                Log.d("ANJO_SOS", "stopService: já está parado")
                                result.success(true)
                                return@setMethodCallHandler
                            }
                            Log.d("ANJO_SOS", "stopService: enviando ACTION_STOP_SOS")
                            val i = Intent(this, AudioService::class.java).apply {
                                action = "ACTION_STOP_SOS"
                            }
                            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                                ContextCompat.startForegroundService(this, i)
                            } else {
                                startService(i)
                            }
                            result.success(true)
                        } catch (t: Throwable) {
                            Log.e("ANJO_SOS", "stopService: erro", t)
                            result.error("STOP_FAIL", t.message, null)
                        }
                    }


                    // Consultar status
                    "isServiceRunning" -> {
                        result.success(AudioService.isRunning)
                    }

                    // Envio direto (mesmo formato do legado)
                    "send" -> {
                        val text     = call.argument<String>("text") ?: "🚨 SOS ANJO DA GUARDA"
                        val lat      = call.argument<Double>("lat")
                        val lon      = call.argument<Double>("lon")
                        val tgTarget = call.argument<String>("tgTarget")

                        val smsTo    = call.argument<ArrayList<String>>("smsTo")   ?: arrayListOf()
                        val waTo     = call.argument<ArrayList<String>>("waTo")    ?: arrayListOf()
                        val emailTo  = call.argument<ArrayList<String>>("emailTo") ?: arrayListOf()

                        SosDispatcher(this).sendAll(
                            text = text,
                            lat = lat, lon = lon,
                            tgTarget = tgTarget,
                            smsTo = smsTo,
                            waTo = waTo,
                            emailTo = emailTo
                        )
                        result.success(true)
                    }

                    else -> result.notImplemented()
                }
            }
    }
}
