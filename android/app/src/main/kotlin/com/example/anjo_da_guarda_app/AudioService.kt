package com.example.anjo_da_guarda_app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.graphics.Typeface
import android.media.AudioManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.SystemClock
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.text.SpannableString
import android.text.Spanned
import android.text.style.StyleSpan
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import android.content.pm.PackageManager
import com.google.android.gms.location.LocationServices
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.MediaType.Companion.toMediaType
import org.json.JSONObject
import java.text.Normalizer
import java.util.Calendar

class AudioService : Service(), RecognitionListener {

    companion object {
        private const val NOTIF_ID   = 1001
        private const val CHANNEL_ID = "sos_audio_channel_id"
        private const val CHANNEL_NAME = "Serviço em 1º plano"
        private const val CHANNEL_DESC = "Monitoramento de palavra-chave para SOS"

        // 👉 Template oficial da Meta/Zenvia (mesmo do backend/SosDispatcher)
        private const val ZENVIA_WA_TEMPLATE_ID = "406d05ec-cd3c-4bca-add3-ddd521aef484"

        // AÇÃO QUE O NATIVE SOS ESTÁ ENVIANDO (ACTION_STOP_SOS)
        const val ACTION_STOP = "ACTION_STOP_SOS"

        // Intervalo para reavaliar hibernação/agenda
        private const val HIBERNATION_INTERVAL_MS = 5_000L   // 5 segundos

        @JvmStatic
        var isRunning: Boolean = false
    }

    private lateinit var nm: NotificationManager
    private var recognizer: SpeechRecognizer? = null
    private lateinit var recIntent: Intent
    private val handler = Handler(Looper.getMainLooper())

    // Loop da hibernação / agenda
    private val hibernationHandler = Handler(Looper.getMainLooper())
    private val hibernationRunnable = object : Runnable {
        override fun run() {
            try {
                updateHibernationFromPrefsAndApply("timer")
            } catch (t: Throwable) {
                Log.e(TAG, "Erro no loop de hibernação", t)
            }
            // reavalia a cada HIBERNATION_INTERVAL_MS
            hibernationHandler.postDelayed(this, HIBERNATION_INTERVAL_MS)
        }
    }

    private var audioManager: AudioManager? = null

    // HTTP (Telegram + Zenvia + SendGrid)
    private val http by lazy { OkHttpClient() }
    private val jsonMedia = "application/json; charset=utf-8".toMediaType()
    private val TAG = "AudioService"

    // ------------- Senhas de áudio em 2 etapas -------------
    // Se não houver nada salvo, usamos "socorro" -> "anjo"
    private var firstTokenNorm: String = "socorro"
    private var secondTokenNorm: String = "anjo"

    // estado da sequência (1ª senha dita -> aguardando 2ª por até 2s)
    private var isArmed: Boolean = false
    private var armedAtMs: Long = 0L
    private var resetArmedRunnable: Runnable? = null
    private val MAX_WINDOW_MS = 2000L  // 2 segundos

    // Proteção contra disparos duplicados em curto intervalo
    private var lastAlertAtMs: Long = 0L
    private val MIN_ALERT_INTERVAL_MS = 5000L  // 5 segundos

    // Estado lógico do áudio (depois de hibernação / agenda / toggle geral)
    private var audioGloballyEnabled: Boolean = true
    private var lastLogicalAudioEnabled: Boolean? = null

    override fun onCreate() {
        super.onCreate()
        isRunning = true
        ensureSosChannel()
        nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager

        loadAudioTokensFromPrefs()
        setupRecognizer()

        // Notificação de foreground básica
        startForeground(NOTIF_ID, baseNotification())

        // Aplica hibernação / agenda / áudio habilitado logo na criação
        updateHibernationFromPrefsAndApply("onCreate")

        // Inicia loop de reavaliação
        hibernationHandler.post(hibernationRunnable)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val action = intent?.action
        Log.d(TAG, "onStartCommand action=$action")

        if (action == ACTION_STOP) {
            Log.d(TAG, "ACTION_STOP recebido — encerrando serviço de áudio")

            // Para re-listen e loop de hibernação
            handler.removeCallbacksAndMessages(null)
            hibernationHandler.removeCallbacksAndMessages(null)

            // Reseta sequência de wake word
            resetWakeSequence()

            // Libera recognizer / microfone
            fullyReleaseRecognizer()

            isRunning = false
            try { stopForeground(true) } catch (_: Throwable) {}
            stopSelf()

            return START_NOT_STICKY
        }

        // Fluxo normal – reaplica preferências
        if (recognizer == null) {
            setupRecognizer()
        }
        updateHibernationFromPrefsAndApply("onStartCommand")
        isRunning = true
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        isRunning = false
        handler.removeCallbacksAndMessages(null)
        hibernationHandler.removeCallbacksAndMessages(null)
        resetWakeSequence()
        fullyReleaseRecognizer()
        try { stopForeground(true) } catch (_: Throwable) {}
        try {
            (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).cancel(NOTIF_ID)
        } catch (_: Throwable) {}
        super.onDestroy()
    }

    // ---------- Notificações ----------

    private fun baseNotification(): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_silent_mode)
            .setContentTitle("Serviço ativo")
            .setContentText("Monitorando palavra-chave")
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun notifyAudioStateChange(activated: Boolean) {
        // Texto discreto padrão solicitado
        val text = if (activated) {
            "Audio Anjo da Guarda modo ativado"
        } else {
            "Audio Anjo da Guarda modo desativado"
        }

        val notifId = 1002
        val notif = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_silent_mode)
            .setContentTitle("Anjo da Guarda")
            .setContentText(text)
            .setAutoCancel(true)
            .setOngoing(false)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()

        nm.notify(notifId, notif)
    }

    private fun triggerAlert() {
        val now = SystemClock.elapsedRealtime()
        val diff = now - lastAlertAtMs
        if (diff in 1..MIN_ALERT_INTERVAL_MS) {
            Log.d(TAG, "Ignorando alerta duplicado (diff=${diff}ms)")
            return
        }
        lastAlertAtMs = now

        val title = SpannableString("🚨 SOS").apply {
            setSpan(
                StyleSpan(Typeface.BOLD),
                2,
                length,
                Spanned.SPAN_EXCLUSIVE_EXCLUSIVE
            )
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

        // Disparo multi-canal (Telegram + SMS + WhatsApp + E-mail)
        sendTelegramAlertWithOptionalLocation()
    }

    private fun ensureSosChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val ch = NotificationChannel(
            CHANNEL_ID,
            CHANNEL_NAME,
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = CHANNEL_DESC
            setSound(null, null)
            enableVibration(false)
        }
        nm.createNotificationChannel(ch)
    }

    // ---------- Controle de hibernação / agenda / áudio ----------

    private fun readBoolCompat(
        prefs: SharedPreferences,
        key: String,
        default: Boolean
    ): Boolean {
        val all = prefs.all
        val raw = all[key] ?: return default
        return when (raw) {
            is Boolean -> raw
            is String -> raw.equals("true", ignoreCase = true) || raw == "1"
            is Number -> raw.toInt() != 0
            else -> default
        }
    }

    private fun readIntCompat(
        prefs: SharedPreferences,
        key: String,
        default: Int
    ): Int {
        val all = prefs.all
        val raw = all[key] ?: return default
        return when (raw) {
            is Int -> raw
            is Long -> raw.toInt()
            is Float -> raw.toInt()
            is Double -> raw.toInt()
            is String -> raw.toIntOrNull() ?: default
            else -> default
        }
    }

    private fun applyAudioEnabledState(
        enabled: Boolean,
        reason: String,
        hibernationActive: Boolean
    ) {
        val prev = lastLogicalAudioEnabled
        if (prev != null && prev == enabled) {
            // Nada mudou; não notifica
            return
        }
        lastLogicalAudioEnabled = enabled
        audioGloballyEnabled = enabled

        Log.d(
            TAG,
            "applyAudioEnabledState(enabled=$enabled, hibernationActive=$hibernationActive, reason=$reason)"
        )

        if (enabled) {
            if (recognizer == null) {
                setupRecognizer()
            }
            startListening()
            notifyAudioStateChange(activated = true)
        } else {
            stopListening()
            notifyAudioStateChange(activated = false)
        }
    }

    private fun updateHibernationFromPrefsAndApply(reason: String) {
        val prefs = getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)

        // Flag global das Configurações (Settings) para áudio
        val audioEnabledFlag =
            readBoolCompat(prefs, "flutter.audioEnabled", true) ||
            readBoolCompat(prefs, "flutter.audio_enabled", false)

        // Toggle manual da pill "Modo hibernação"
        val manualHibernation =
            readBoolCompat(prefs, "flutter.hibernationOn", false) ||
            readBoolCompat(prefs, "flutter.hibernation_on", false) ||
            readBoolCompat(prefs, "flutter.hibernationEnabled", false) ||
            readBoolCompat(prefs, "flutter.hibernation_enabled", false)

        // Agendamento automático (dias + horário)
        val autoEnabled =
            readBoolCompat(prefs, "flutter.hibernationAutoEnabled", false) ||
            readBoolCompat(prefs, "flutter.hibernation_auto_enabled", false)

        var autoHibernation = false

        if (autoEnabled) {
            val cal = Calendar.getInstance()
            val hour = cal.get(Calendar.HOUR_OF_DAY)
            val minute = cal.get(Calendar.MINUTE)
            val minuteOfDay = hour * 60 + minute

            val dow = cal.get(Calendar.DAY_OF_WEEK) // 1=Sunday .. 7=Saturday
            val daySuffix = when (dow) {
                Calendar.MONDAY -> "mon"
                Calendar.TUESDAY -> "tue"
                Calendar.WEDNESDAY -> "wed"
                Calendar.THURSDAY -> "thu"
                Calendar.FRIDAY -> "fri"
                Calendar.SATURDAY -> "sat"
                Calendar.SUNDAY -> "sun"
                else -> "mon"
            }

            val dayOn =
                readBoolCompat(prefs, "flutter.hibernation_${daySuffix}", false) ||
                readBoolCompat(prefs, "flutter.hibernation${daySuffix.replaceFirstChar { it.uppercase() }}", false)

            if (dayOn) {
                var startMin = readIntCompat(prefs, "flutter.hibernationStartMinutes", -1)
                if (startMin < 0) {
                    startMin = readIntCompat(prefs, "flutter.hibernation_start_minutes", -1)
                }
                var endMin = readIntCompat(prefs, "flutter.hibernationEndMinutes", -1)
                if (endMin < 0) {
                    endMin = readIntCompat(prefs, "flutter.hibernation_end_minutes", -1)
                }

                if (startMin >= 0 && endMin >= 0) {
                    if (startMin == endMin) {
                        // janela vazia
                        autoHibernation = false
                    } else if (endMin > startMin) {
                        // janela no mesmo dia
                        autoHibernation = (minuteOfDay in startMin until endMin)
                    } else {
                        // janela atravessando meia-noite (ex: 22h–05h)
                        autoHibernation =
                            (minuteOfDay >= startMin) || (minuteOfDay < endMin)
                    }
                }
            }
        }

        val hibernationActive = manualHibernation || autoHibernation
        val logicalAudioEnabled = audioEnabledFlag && !hibernationActive

        Log.d(
            TAG,
            "updateHibernation(reason=$reason) audioEnabledFlag=$audioEnabledFlag " +
                "manualH=$manualHibernation autoEnabled=$autoEnabled autoH=$autoHibernation " +
                "=> logicalEnabled=$logicalAudioEnabled"
        )

        applyAudioEnabledState(logicalAudioEnabled, reason, hibernationActive)
    }

    // ---------- Reconhecimento de voz ----------

    private fun fullyReleaseRecognizer() {
        try { recognizer?.cancel() } catch (_: Throwable) {}
        try { recognizer?.setRecognitionListener(null) } catch (_: Throwable) {}
        try { recognizer?.destroy() } catch (_: Throwable) {}
        recognizer = null
    }

    private fun loadAudioTokensFromPrefs() {
        try {
            val prefs = getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
            val raw1 = prefs.getString("flutter.audioToken1", null)
                ?: prefs.getString("flutter.audio_token_1", null)
            val raw2 = prefs.getString("flutter.audioToken2", null)
                ?: prefs.getString("flutter.audio_token_2", null)

            val n1 = raw1?.let { normalize(it) }?.takeIf { it.isNotBlank() }
            val n2 = raw2?.let { normalize(it) }?.takeIf { it.isNotBlank() }

            if (n1 != null && n2 != null) {
                firstTokenNorm = n1
                secondTokenNorm = n2
                Log.d(TAG, "Tokens de áudio carregados: '$firstTokenNorm' -> '$secondTokenNorm'")
            } else {
                Log.d(TAG, "Usando tokens padrão de áudio: '$firstTokenNorm' -> '$secondTokenNorm'")
            }
        } catch (t: Throwable) {
            Log.e(TAG, "Erro ao ler tokens de áudio das SharedPreferences", t)
        }
    }

    private fun setupRecognizer() {
        if (!SpeechRecognizer.isRecognitionAvailable(this)) return
        recognizer?.destroy()
        recognizer = SpeechRecognizer.createSpeechRecognizer(this).also {
            it.setRecognitionListener(this)
        }
        recIntent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
            )
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "pt-BR")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        }
    }

    private fun startListening() {
        if (!audioGloballyEnabled) {
            Log.d(TAG, "startListening: abortado porque audioGloballyEnabled=false")
            return
        }

        val am = audioManager ?: run {
            try {
                audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager
            } catch (_: Throwable) {}
            audioManager
        }

        // Se tiver mídia tocando (YouTube, Spotify, vídeos...), não escuta
        try {
            if (am != null && am.isMusicActive) {
                Log.d(TAG, "Mídia em reprodução; adiando escuta para não interferir")
                scheduleRestart(3000)
                return
            }
        } catch (t: Throwable) {
            Log.e(TAG, "Erro ao checar isMusicActive em startListening", t)
        }

        try {
            recognizer?.startListening(recIntent)
        } catch (_: Throwable) {
            scheduleRestart()
        }
    }

    private fun stopListening() {
        try { recognizer?.stopListening() } catch (_: Throwable) {}
    }

    private fun scheduleRestart(delayMs: Long = 800) {
        if (!audioGloballyEnabled) {
            Log.d(TAG, "scheduleRestart: abortado porque audioGloballyEnabled=false")
            return
        }
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
        if (!audioGloballyEnabled) {
            Log.d(TAG, "handleBundle: ignorando porque audioGloballyEnabled=false")
            return
        }

        // Se estiver com mídia tocando, não processa para não atrapalhar
        try {
            val am = audioManager
            if (am != null && am.isMusicActive) {
                Log.d(TAG, "Mídia em reprodução; pausando reconhecimento por alguns segundos")
                stopListening()
                scheduleRestart(3000)
                return
            }
        } catch (t: Throwable) {
            Log.e(TAG, "Erro ao checar isMusicActive em handleBundle", t)
        }

        val list = bundle.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION) ?: return
        val heardRaw = list.firstOrNull() ?: return
        val heard = normalize(heardRaw)
        Log.d(TAG, "heardRaw=$heardRaw -> $heard")

        if (firstTokenNorm.isBlank() || secondTokenNorm.isBlank()) {
            return
        }

        val now = SystemClock.elapsedRealtime()

        // Frase com as duas senhas já na ordem correta
        val idx1 = heard.indexOf(firstTokenNorm)
        if (idx1 >= 0) {
            val idx2 = heard.indexOf(secondTokenNorm, idx1 + firstTokenNorm.length)
            if (idx2 > idx1) {
                Log.d(TAG, "Sequência completa detectada em uma única frase")
                resetWakeSequence()
                triggerAlert()
                return
            }
        }

        // 1ª senha (arma o sistema por até 2s)
        if (!isArmed && heard.contains(firstTokenNorm)) {
            Log.d(TAG, "Primeira senha de áudio detectada; armando por 2s")
            armSequence(now)
            return
        }

        // Já armado: espera a 2ª senha dentro da janela
        if (isArmed) {
            val elapsed = now - armedAtMs
            if (elapsed > MAX_WINDOW_MS) {
                Log.d(TAG, "Janela de 2s estourada ($elapsed ms); resetando")
                resetWakeSequence()
                return
            }

            if (heard.contains(secondTokenNorm)) {
                Log.d(TAG, "Segunda senha de áudio detectada dentro da janela ($elapsed ms); disparando SOS")
                resetWakeSequence()
                triggerAlert()
            }
        }
    }

    private fun armSequence(now: Long) {
        isArmed = true
        armedAtMs = now
        resetArmedRunnable?.let { handler.removeCallbacks(it) }
        resetArmedRunnable = Runnable {
            Log.d(TAG, "Janela de 2s expirou; voltando para estado estático")
            resetWakeSequence()
        }
        handler.postDelayed(resetArmedRunnable!!, MAX_WINDOW_MS)
    }

    private fun resetWakeSequence() {
        isArmed = false
        armedAtMs = 0L
        resetArmedRunnable?.let { handler.removeCallbacks(it) }
        resetArmedRunnable = null
    }

    private fun normalize(s: String): String {
        return Normalizer.normalize(s.lowercase(), Normalizer.Form.NFD)
            .replace("\\p{M}+".toRegex(), "")
            .replace("[^a-z0-9 ]".toRegex(), " ")
            .replace("\\s+".toRegex(), " ")
            .trim()
    }

    // ---------- Helpers de SharedPreferences (destinos) ----------

    private fun loadTelegramTargetFromPrefs(): String? {
        return try {
            val prefs = getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
            val raw = prefs.getString("flutter.tgTarget", null)
            raw?.trim()?.takeIf { it.isNotEmpty() }
        } catch (t: Throwable) {
            Log.e(TAG, "Erro ao ler tgTarget das SharedPreferences", t)
            null
        }
    }

    private fun loadPhonesFromPrefs(baseKey: String): List<String> {
        val prefs = getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
        val result = mutableListOf<String>()

        // Tenta tanto padrão "smsTo1" quanto "sms_to_1" (e equivalente para "wa")
        for (i in 1..3) {
            val k1 = "flutter.${baseKey}To$i"
            val k2 = "flutter.${baseKey}_to_$i"

            val v1 = prefs.getString(k1, null)
            val v2 = prefs.getString(k2, null)

            listOf(v1, v2).forEach { raw ->
                if (!raw.isNullOrBlank()) {
                    // remove espaços, parênteses etc., mas mantém '+'
                    val cleaned = raw.replace("[^0-9+]".toRegex(), "")
                    if (cleaned.isNotBlank()) {
                        result.add(cleaned)
                    }
                }
            }
        }
        return result.distinct()
    }

    private fun loadEmailsFromPrefs(): List<String> {
        val prefs = getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
        val result = mutableListOf<String>()

        for (i in 1..3) {
            val k1 = "flutter.emailTo$i"
            val k2 = "flutter.email_to_$i"

            val v1 = prefs.getString(k1, null)
            val v2 = prefs.getString(k2, null)

            listOf(v1, v2).forEach { raw ->
                val cleaned = raw?.trim()
                if (!cleaned.isNullOrBlank()) {
                    result.add(cleaned)
                }
            }
        }
        return result.distinct()
    }

    // ---------- Texto padrão Meta/Zenvia ----------

    private fun buildAlertText(nome: String, lat: Double?, lon: Double?): String {
        return if (lat != null && lon != null) {
            val link = "https://maps.google.com/?q=$lat,$lon"
            """
🚨 ALERTA de $nome
Situação: sos pessoal
Localização (mapa): $link

Se não puder ajudar, encaminhe às autoridades.
""".trimIndent()
        } else {
            """
🚨 ALERTA de $nome
Situação: sos pessoal
Localização: não informada

Se não puder ajudar, encaminhe às autoridades.
""".trimIndent()
        }
    }

    // ---------- Telegram ----------

    private fun sendTelegramMessage(texto: String) {
        val token = BuildConfig.TELEGRAM_BOT_TOKEN

        val fromPrefs = loadTelegramTargetFromPrefs()
        val fromBuildConfig = BuildConfig.TELEGRAM_CHAT_ID
        val chatId = when {
            !fromPrefs.isNullOrBlank() -> fromPrefs
            !fromBuildConfig.isBlank()
                    && fromBuildConfig != "123456789,987654321"
                    && fromBuildConfig != "<SUBSTITUA_PELO_SEU_CHAT_ID>" -> fromBuildConfig
            else -> ""
        }

        val tokenBlank = token.isBlank()
        val chatBlank = chatId.isBlank()
        Log.d(TAG, "sendTelegramMessage: tokenBlank=$tokenBlank chatBlank=$chatBlank")

        if (tokenBlank || chatBlank) {
            Log.w(TAG, "sendTelegramMessage abortado: conferir TELEGRAM_BOT_TOKEN / tgTarget / TELEGRAM_CHAT_ID")
            return
        }

        val url = "https://api.telegram.org/bot${token}/sendMessage"
        val payload = JSONObject().apply {
            put("chat_id", chatId)
            put("text", texto)
            put("parse_mode", "HTML")
        }.toString().toRequestBody(jsonMedia)

        Thread {
            try {
                val req = Request.Builder().url(url).post(payload).build()
                http.newCall(req).execute().use { resp ->
                    Log.d(TAG, "sendTelegramMessage HTTP=${resp.code} body=${resp.body?.string()}")
                }
            } catch (t: Throwable) {
                Log.e(TAG, "sendTelegramMessage erro", t)
            }
        }.start()
    }

    private fun sendTelegramLocation(lat: Double, lng: Double) {
        val token = BuildConfig.TELEGRAM_BOT_TOKEN

        val fromPrefs = loadTelegramTargetFromPrefs()
        val fromBuildConfig = BuildConfig.TELEGRAM_CHAT_ID
        val chatId = when {
            !fromPrefs.isNullOrBlank() -> fromPrefs
            !fromBuildConfig.isBlank()
                    && fromBuildConfig != "123456789,987654321"
                    && fromBuildConfig != "<SUBSTITUA_PELO_SEU_CHAT_ID>" -> fromBuildConfig
            else -> ""
        }

        val tokenBlank = token.isBlank()
        val chatBlank = chatId.isBlank()
        Log.d(TAG, "sendTelegramLocation: tokenBlank=$tokenBlank chatBlank=$chatBlank")

        if (tokenBlank || chatBlank) {
            Log.w(TAG, "sendTelegramLocation abortado: conferir TELEGRAM_BOT_TOKEN / tgTarget / TELEGRAM_CHAT_ID")
            return
        }

        val url = "https://api.telegram.org/bot${token}/sendLocation"
        val payload = JSONObject().apply {
            put("chat_id", chatId)
            put("latitude", lat)
            put("longitude", lng)
        }.toString().toRequestBody(jsonMedia)

        Thread {
            try {
                val req = Request.Builder().url(url).post(payload).build()
                http.newCall(req).execute().use { resp ->
                    Log.d(TAG, "sendTelegramLocation HTTP=${resp.code}")
                }
            } catch (t: Throwable) {
                Log.e(TAG, "sendTelegramLocation erro", t)
            }
        }.start()
    }

    // ---------- SMS / WhatsApp (Zenvia) ----------

    private fun sendZenviaSms(nome: String, lat: Double?, lon: Double?) {
        val token = BuildConfig.ZENVIA_TOKEN
        val from = BuildConfig.ZENVIA_SMS_FROM

        if (token.isBlank() || from.isBlank()) {
            Log.w(TAG, "sendZenviaSms abortado: ZENVIA_TOKEN ou ZENVIA_SMS_FROM vazios")
            return
        }

        val tos = loadPhonesFromPrefs("sms")
        if (tos.isEmpty()) {
            Log.w(TAG, "sendZenviaSms: nenhum destinatário configurado para SMS (prefs smsTo1/sms_to_1 etc.)")
            return
        }

        val texto = buildAlertText(nome, lat, lon)
        val url = "https://api.zenvia.com/v2/channels/sms/messages"

        Thread {
            tos.forEach { to ->
                try {
                    val json = """
{
  "from": "$from",
  "to": "$to",
  "contents": [
    {
      "type": "text",
      "text": ${JSONObject.quote(texto)}
    }
  ]
}
""".trimIndent()

                    val req = Request.Builder()
                        .url(url)
                        .addHeader("X-API-TOKEN", token)
                        .addHeader("Content-Type", "application/json")
                        .post(json.toRequestBody(jsonMedia))
                        .build()

                    http.newCall(req).execute().use { resp ->
                        Log.d(TAG, "sendZenviaSms to=$to HTTP=${resp.code}")
                    }
                } catch (t: Throwable) {
                    Log.e(TAG, "sendZenviaSms erro para $to", t)
                }
            }
        }.start()
    }

    private fun sendZenviaWhatsapp(nome: String, lat: Double?, lon: Double?) {
        val token = BuildConfig.ZENVIA_TOKEN
        val from = BuildConfig.ZENVIA_WA_FROM

        if (token.isBlank() || from.isBlank()) {
            Log.w(TAG, "sendZenviaWhatsapp abortado: ZENVIA_TOKEN ou ZENVIA_WA_FROM vazios")
            return
        }

        // Template oficial exige link de rastreamento (URL completa)
        if (lat == null || lon == null) {
            Log.w(TAG, "sendZenviaWhatsapp abortado: sem lat/lon para usar o template oficial Meta/Zenvia")
            return
        }

        // Números vindos do layout no formato +5599..., removemos o '+'
        val tos = loadPhonesFromPrefs("wa")
            .map { it.replace("+", "") }
            .filter { it.isNotBlank() }
            .distinct()

        if (tos.isEmpty()) {
            Log.w(TAG, "sendZenviaWhatsapp: nenhum destinatário configurado para WhatsApp (prefs waTo1/wa_to_1 etc.)")
            return
        }

        val url = "https://api.zenvia.com/v2/channels/whatsapp/messages"

        // MESMO PADRÃO DO BACKEND: link_rastreamento = "https://maps.google.com/?q=lat,lon"
        val linkRastreamento = "https://maps.google.com/?q=$lat,$lon"

        Thread {
            tos.forEach { to ->
                try {
                    val json = """
{
  "from": "$from",
  "to": "$to",
  "contents": [
    {
      "type": "template",
      "templateId": "$ZENVIA_WA_TEMPLATE_ID",
      "fields": {
        "nome": ${JSONObject.quote(nome)},
        "link_rastreamento": ${JSONObject.quote(linkRastreamento)}
      }
    }
  ]
}
""".trimIndent()

                    Log.d(
                        TAG,
                        "sendZenviaWhatsapp(template) to=$to link_rastreamento=$linkRastreamento"
                    )

                    val req = Request.Builder()
                        .url(url)
                        .addHeader("X-API-TOKEN", token)
                        .addHeader("Content-Type", "application/json")
                        .post(json.toRequestBody(jsonMedia))
                        .build()

                    http.newCall(req).execute().use { resp ->
                        val bodyStr = resp.body?.string()
                        Log.d(TAG, "sendZenviaWhatsapp to=$to HTTP=${resp.code} body=$bodyStr")
                    }
                } catch (t: Throwable) {
                    Log.e(TAG, "sendZenviaWhatsapp erro para $to", t)
                }
            }
        }.start()
    }

    // ---------- E-mail (SendGrid) ----------

    private fun sendSendgridEmail(nome: String, lat: Double?, lon: Double?) {
        val apiKey = BuildConfig.SENDGRID_API_KEY
        val fromEmail = BuildConfig.SENDGRID_FROM

        if (apiKey.isBlank() || fromEmail.isBlank()) {
            Log.w(TAG, "sendSendgridEmail abortado: SENDGRID_API_KEY ou SENDGRID_FROM vazios")
            return
        }

        val tos = loadEmailsFromPrefs()
        if (tos.isEmpty()) {
            Log.w(TAG, "sendSendgridEmail: nenhum destinatário configurado (prefs emailTo1/email_to_1 etc.)")
            return
        }

        val texto = buildAlertText(nome, lat, lon)
        val subject = "SOS - ALERTA de $nome"
        val url = "https://api.sendgrid.com/v3/mail/send"

        Thread {
            tos.forEach { to ->
                try {
                    val json = """
{
  "personalizations": [
    {
      "to": [
        { "email": ${JSONObject.quote(to)} }
      ],
      "subject": ${JSONObject.quote(subject)}
    }
  ],
  "from": {
    "email": ${JSONObject.quote(fromEmail)},
    "name": "Anjo da Guarda"
  },
  "content": [
    {
      "type": "text/plain",
      "value": ${JSONObject.quote(texto)}
    }
  ]
}
""".trimIndent()

                    val req = Request.Builder()
                        .url(url)
                        .addHeader("Authorization", "Bearer $apiKey")
                        .addHeader("Content-Type", "application/json")
                        .post(json.toRequestBody(jsonMedia))
                        .build()

                    http.newCall(req).execute().use { resp ->
                        Log.d(TAG, "sendSendgridEmail to=$to HTTP=${resp.code}")
                    }
                } catch (t: Throwable) {
                    Log.e(TAG, "sendSendgridEmail erro para $to", t)
                }
            }
        }.start()
    }

    // ---------- Disparo multi-canal com ou sem localização ----------

    private fun sendTelegramAlertWithOptionalLocation() {
        // pega o nome salvo nas SharedPreferences do Flutter
        val prefs = getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
        val nome = prefs.getString("flutter.nomeCompleto", null)
            ?.takeIf { it.isNotBlank() }
            ?: "nome"

        fun fireAll(lat: Double?, lon: Double?) {
            val msg = buildAlertText(nome, lat, lon)
            sendTelegramMessage(msg)
            sendZenviaSms(nome, lat, lon)
            sendZenviaWhatsapp(nome, lat, lon)
            sendSendgridEmail(nome, lat, lon)

            if (lat != null && lon != null) {
                sendTelegramLocation(lat, lon)
            }
        }

        if (!hasLocationPermission()) {
            fireAll(null, null)
            return
        }

        val fused = LocationServices.getFusedLocationProviderClient(this)
        fused.lastLocation
            .addOnSuccessListener { loc ->
                if (loc != null) {
                    fireAll(loc.latitude, loc.longitude)
                } else {
                    fireAll(null, null)
                }
            }
            .addOnFailureListener {
                fireAll(null, null)
            }
    }

    // ---------- Permissão de localização ----------

    private fun hasLocationPermission(): Boolean {
        val fine = ContextCompat.checkSelfPermission(
            this,
            android.Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        val coarse = ContextCompat.checkSelfPermission(
            this,
            android.Manifest.permission.ACCESS_COARSE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        return fine || coarse
    }
}
