package com.example.anjo_da_guarda_app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.SystemClock
import android.provider.Settings
import android.text.SpannableString
import android.text.Spanned
import android.text.style.StyleSpan
import android.graphics.Typeface
import androidx.core.app.NotificationCompat
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import java.text.Normalizer
import android.util.Log
import androidx.core.content.ContextCompat
import android.content.pm.PackageManager
import com.google.android.gms.location.LocationServices
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.MediaType.Companion.toMediaType
import org.json.JSONObject

class AudioService : Service(), RecognitionListener {

    companion object {
        private const val NOTIF_ID   = 1001
        private const val CHANNEL_ID = "sos_audio_channel_id"
        private const val CHANNEL_NAME = "Serviço em 1º plano"
        private const val CHANNEL_DESC = "Monitoramento de palavra-chave para SOS"

        // ação explícita para parar o serviço (usaremos no próximo passo pelo Dart)
        const val ACTION_STOP = "com.example.anjo_da_guarda_app.ACTION_STOP"

        @JvmStatic var isRunning: Boolean = false
    }

    private lateinit var nm: NotificationManager
    private var recognizer: SpeechRecognizer? = null
    private lateinit var recIntent: Intent
    private val handler = Handler(Looper.getMainLooper())

    private fun fullyReleaseRecognizer() {
    try { recognizer?.cancel() } catch (_: Throwable) {}
    try { recognizer?.setRecognitionListener(null) } catch (_: Throwable) {}
    try { recognizer?.destroy() } catch (_: Throwable) {}
    recognizer = null
    }

    // Telegram
    private val http by lazy { OkHttpClient() }
    private val jsonMedia = "application/json; charset=utf-8".toMediaType()
    private val TAG = "AudioService"

    // Gatilho: "oi" -> "socorro" com 1..3s
    private val TOKENS = arrayOf("oi", "socorro")
    private val MIN_GAP_MS = 1000L
    private val MAX_GAP_MS = 3000L
    private var tokenIndex = 0
    private var lastTokenTs = 0L

    override fun onCreate() {
        super.onCreate()
        isRunning = true
        ensureSosChannel()
        nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        startForeground(NOTIF_ID, baseNotification())
        setupRecognizer()
        startListening()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == "ACTION_STOP_SOS") {
            Log.d(TAG, "Recebido ACTION_STOP_SOS — encerrando serviço")
            // Para qualquer re-listen pendente
            handler.removeCallbacksAndMessages(null)
            // Para o reconhecimento de voz
            try { recognizer?.stopListening() } catch (_: Throwable) {}
            try { recognizer?.cancel() } catch (_: Throwable) {}
            // Atualiza flag e encerra foreground
            isRunning = false
            stopForeground(true)
            stopSelf()
            return START_NOT_STICKY
        }

        // Fluxo normal: garantir recognizer e começar a escutar
        if (recognizer == null) setupRecognizer()
        startListening()
        isRunning = true
        return START_STICKY
    }


    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
    isRunning = false
    // para qualquer re-agendamento de startListening
    handler.removeCallbacksAndMessages(null)
    // solta o microfone de forma agressiva
    fullyReleaseRecognizer()
    // remove notificação e o estado de foreground
    try { stopForeground(true) } catch (_: Throwable) {}
    try { (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).cancel(NOTIF_ID) } catch (_: Throwable) {}
    super.onDestroy()
    }

    // ---------- Notificações ----------
    private fun baseNotification(): Notification {
        // texto neutro, sem nome do app
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_silent_mode) // discreto
            .setContentTitle("Serviço ativo")
            .setContentText("Monitorando palavra-chave")
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setPriority(NotificationCompat.PRIORITY_LOW) // silencioso
            .build()
    }

    private fun triggerAlert() {
        val title = SpannableString("🚨 SOS").apply {
            setSpan(StyleSpan(Typeface.BOLD), 2, length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        }
        val notif = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle(title)
            .setContentText("Alerta confirmado")
            .setStyle(NotificationCompat.BigTextStyle().bigText("🚨 SOS"))
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()
        nm.notify(NOTIF_ID, notif)

        // Disparo no Telegram (com localização se possível)
        sendTelegramAlertWithOptionalLocation()
    }

    private fun ensureSosChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val ch = NotificationChannel(
            CHANNEL_ID,
            CHANNEL_NAME,
            NotificationManager.IMPORTANCE_LOW // baixo: sem som
        ).apply {
            description = CHANNEL_DESC
            setSound(null, null) // força silencioso
            enableVibration(false)
        }
        nm.createNotificationChannel(ch)
    }

    // ---------- Reconhecimento de voz ----------
    private fun setupRecognizer() {
        if (!SpeechRecognizer.isRecognitionAvailable(this)) return
        recognizer?.destroy()
        recognizer = SpeechRecognizer.createSpeechRecognizer(this).also {
            it.setRecognitionListener(this)
        }
        recIntent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "pt-BR")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        }
    }

    private fun startListening() {
        try { recognizer?.startListening(recIntent) } catch (_: Throwable) { scheduleRestart() }
    }

    private fun stopListening() {
        try { recognizer?.stopListening() } catch (_: Throwable) {}
    }

    private fun scheduleRestart(delayMs: Long = 800) {
        handler.postDelayed({ startListening() }, delayMs)
    }

    // ---------- RecognitionListener ----------
    override fun onReadyForSpeech(params: Bundle?) {}
    override fun onBeginningOfSpeech() {}
    override fun onRmsChanged(rmsdB: Float) {}
    override fun onBufferReceived(buffer: ByteArray?) {}
    override fun onEndOfSpeech() {}
    override fun onError(error: Int) { scheduleRestart(1000) }

    override fun onResults(results: Bundle) {
        handleBundle(results)
        scheduleRestart(400)
    }

    override fun onPartialResults(partialResults: Bundle) { handleBundle(partialResults) }
    override fun onEvent(eventType: Int, params: Bundle?) {}

    private fun handleBundle(bundle: Bundle) {
        val list = bundle.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION) ?: return
        val heardRaw = list.firstOrNull() ?: return
        val heard = normalize(heardRaw)
        Log.d(TAG, "heardRaw=$heardRaw -> $heard")

        val now = SystemClock.elapsedRealtime()

        // TESTE: dispare só com uma palavra
        if (heard.contains("socorro")) {
            Log.d(TAG, "Trigger by single word")
            resetWakeSequence()
            triggerAlert()
            return
        }

        // Sequência: "oi" -> "socorro" com 1..3s entre
        if (tokenIndex == 0 && heard.contains(TOKENS[0])) {
            tokenIndex = 1
            lastTokenTs = now
        } else if (tokenIndex == 1 && heard.contains(TOKENS[1])) {
            val gap = now - lastTokenTs
            if (gap in MIN_GAP_MS..MAX_GAP_MS) {
                tokenIndex = 0
                triggerAlert()
            } else {
                resetWakeSequence()
            }
        }

        // timeout entre palavras
        if (tokenIndex > 0 && (now - lastTokenTs) > MAX_GAP_MS) {
            resetWakeSequence()
        }
    }

    private fun resetWakeSequence() {
        tokenIndex = 0
        lastTokenTs = 0L
    }

    private fun normalize(s: String): String {
        return Normalizer.normalize(s.lowercase(), Normalizer.Form.NFD)
            .replace("\\p{M}+".toRegex(), "")
            .replace("[^a-z0-9 ]".toRegex(), " ")
            .replace("\\s+".toRegex(), " ")
            .trim()
    }

    // ---------- Telegram ----------
    private fun sendTelegramMessage(html: String) {
        val token = BuildConfig.TELEGRAM_BOT_TOKEN
        val chatId = BuildConfig.TELEGRAM_CHAT_ID
        if (token.isBlank() || chatId.isBlank() || chatId == "<SUBSTITUA_PELO_SEU_CHAT_ID>") return

        val url = "https://api.telegram.org/bot${token}/sendMessage"
        val payload = JSONObject().apply {
            put("chat_id", chatId)
            put("text", html)
            put("parse_mode", "HTML")
        }.toString().toRequestBody(jsonMedia)

        Thread {
            try {
                val req = Request.Builder().url(url).post(payload).build()
                http.newCall(req).execute().use { }
            } catch (_: Throwable) { }
        }.start()
    }

    private fun sendTelegramLocation(lat: Double, lng: Double) {
        val token = BuildConfig.TELEGRAM_BOT_TOKEN
        val chatId = BuildConfig.TELEGRAM_CHAT_ID
        if (token.isBlank() || chatId.isBlank() || chatId == "<SUBSTITUA_PELO_SEU_CHAT_ID>") return

        val url = "https://api.telegram.org/bot${token}/sendLocation"
        val payload = JSONObject().apply {
            put("chat_id", chatId)
            put("latitude", lat)
            put("longitude", lng)
        }.toString().toRequestBody(jsonMedia)

        Thread {
            try {
                val req = Request.Builder().url(url).post(payload).build()
                http.newCall(req).execute().use { }
            } catch (_: Throwable) { }
        }.start()
    }

    private fun sendTelegramAlertWithOptionalLocation() {
        val base = "🚨 <b>SOS</b>"
        if (!hasLocationPermission()) {
            sendTelegramMessage("$base\n(Localização sem permissão)")
            return
        }
        val fused = LocationServices.getFusedLocationProviderClient(this)
        fused.lastLocation
            .addOnSuccessListener { loc ->
                if (loc != null) {
                    val link = "https://maps.google.com/?q=${loc.latitude},${loc.longitude}"
                    val txt = "$base\n📍 <a href=\"$link\">Abrir localização</a>"
                    sendTelegramMessage(txt)
                    sendTelegramLocation(loc.latitude, loc.longitude)
                } else {
                    sendTelegramMessage("$base\n(Localização indisponível)")
                }
            }
            .addOnFailureListener {
                sendTelegramMessage("$base\n(Localização indisponível)")
            }
    }

    private fun hasLocationPermission(): Boolean {
        val f = ContextCompat.checkSelfPermission(this, android.Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val c = ContextCompat.checkSelfPermission(this, android.Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        return f || c
    }
}
