package com.example.anjo_da_guarda_app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.app.PendingIntent
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import com.example.anjo_da_guarda_app.R   // mantém o import do R

class MainActivity : FlutterActivity() {

    private val CHANNEL = "sos_audio_channel"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "startService" -> {
                        ContextCompat.startForegroundService(
                            this, Intent(this, AudioService::class.java)
                        )
                        result.success(true)
                    }
                    "stopService" -> {
                        stopService(Intent(this, AudioService::class.java))
                        result.success(true)
                    }
                    else -> result.notImplemented()
                }
            }
    }
}

class AudioService : Service() {

    // >>> Se o canal antigo já foi criado no aparelho, mude o ID para outro (ex.: "_v2")
    private val CHANNEL_ID = "sos_audio_channel_v2"
    private val NOTIF_ID = 1

    override fun onCreate() {
        super.onCreate()
        createChannel()

        // Ao tocar na notificação, abre o app
        val tapIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val tapPendingIntent = PendingIntent.getActivity(
            this, 0, tapIntent, PendingIntent.FLAG_IMMUTABLE
        )

        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_mic)
            .setContentTitle("Anjo da Guarda")
            .setContentText("Vigilância de voz ativa")
            .setOngoing(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setPriority(NotificationCompat.PRIORITY_HIGH) // prioridade alta no Android < 8
            .setContentIntent(tapPendingIntent)
            .setAutoCancel(false)
            .build()

        startForeground(NOTIF_ID, notification)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_STICKY
    override fun onBind(intent: Intent?): IBinder? = null

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
            val chan = NotificationChannel(
                CHANNEL_ID,
                "Anjo da Guarda",
                NotificationManager.IMPORTANCE_HIGH   // alta importância para aparecer no topo
            ).apply {
                setSound(null, null)          // sem som
                enableVibration(false)        // sem vibração
                lockscreenVisibility = Notification.VISIBILITY_PUBLIC
                setShowBadge(false)
            }
            nm.createNotificationChannel(chan)
        }
    }
}
