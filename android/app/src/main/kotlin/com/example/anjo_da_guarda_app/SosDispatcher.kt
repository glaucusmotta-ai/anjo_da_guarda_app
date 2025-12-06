package com.example.anjo_da_guarda_app

import android.content.Context
import android.content.pm.PackageManager
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import androidx.core.content.ContextCompat
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.Priority
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.text.Normalizer
import java.util.concurrent.TimeUnit
import kotlin.concurrent.thread

class SosDispatcher(private val ctx: Context) {

    private val http = OkHttpClient.Builder()
        .connectTimeout(12, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()

    private val json = "application/json; charset=utf-8".toMediaType()

    // ---------------------------------------------------------
    // Backend de Live Tracking (FastAPI)
    // ---------------------------------------------------------
    private val liveTrackBaseUrl = "https://anjo-track.3g-brasil.com"
    private val liveTrackEnabled = true

    // Controle de loop de live tracking (Android nativo)
    private var liveTrackCallback: LocationCallback? = null
    private var liveTrackStopAtMs: Long = 0L
    private val liveTrackIntervalMs: Long = 15_000L            // 15s entre updates
    private val liveTrackMaxDurationMs: Long = 30 * 60 * 1000L // 30 minutos

    // Deixa o número só com dígitos (remove +, (), espaço, traço etc.)
    private fun normalizeMsisdn(raw: String): String =
        raw.filter { it.isDigit() }

    // ---------- Helpers ----------
    private fun mapsLink(lat: Double?, lon: Double?): String? {
        if (lat == null || lon == null) return null
        // Mesmo padrão do modelo aprovado pela Zenvia/Meta
        return "https://maps.google.com/?q=$lat,$lon"
    }

    private fun stripForSms(s: String): String {
        // SMS da Zenvia costuma rejeitar alguns caracteres (erro 011). Removemos acentos/emoji.
        var t = Normalizer.normalize(s, Normalizer.Form.NFD)
            .replace("\\p{M}+".toRegex(), "")
        // remove caracteres de controle/emoji
        t = t.replace("[^\\x20-\\x7E\\n]".toRegex(), "")
        // limite de segurança
        if (t.length > 700) t = t.take(700)
        return t
    }

    // Lê o "nome completo" salvo pelo Flutter nas SharedPreferences
    private fun getNomeCompletoFromPrefs(): String? {
        return try {
            val prefs = ctx.getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
            val possibleKeys = listOf(
                "flutter.nomeCompleto",
                "flutter.nome_completo",
                "flutter.userFullName",
                "flutter.user_name"
            )
            for (key in possibleKeys) {
                val v = prefs.getString(key, null)?.trim()
                if (!v.isNullOrEmpty()) {
                    Log.d("ANJO_SOS", "nomeCompleto encontrado em $key = $v")
                    return v
                }
            }
            null
        } catch (t: Throwable) {
            Log.e("ANJO_SOS", "erro ao ler nome completo das prefs", t)
            null
        }
    }

    private fun logResp(tag: String, resp: Response) {
        val code = resp.code
        val body = try {
            resp.body?.string() ?: ""
        } catch (_: Throwable) {
            "<no-body>"
        }
        Log.d(tag, "HTTP $code :: $body")
    }

    // ---------------------------------------------------------
    // Live Tracking – /api/live-track/start
    // ---------------------------------------------------------
    private fun startLiveTrack(text: String, lat: Double?, lon: Double?): String? {
        if (!liveTrackEnabled) return null
        if (liveTrackBaseUrl.isBlank()) {
            Log.d("LIVE_TRACK", "skip start: baseUrl vazio (nao configurado)")
            return null
        }
        if (lat == null || lon == null) {
            Log.d("LIVE_TRACK", "skip start: sem coordenadas")
            return null
        }

        val base = liveTrackBaseUrl.trimEnd('/')
        val url = "$base/api/live-track/start"

        val nome = getNomeCompletoFromPrefs() ?: "Contato"

        return try {
            val bodyJson = JSONObject()
                .put("nome", nome)
                .put("text", text)
                .put("lat", lat)
                .put("lon", lon)
                .put("origem", "app_android")

            val reqBody = bodyJson.toString().toRequestBody(json)

            val client = http.newBuilder()
                .connectTimeout(3, TimeUnit.SECONDS)
                .readTimeout(5, TimeUnit.SECONDS)
                .build()

            client.newCall(
                Request.Builder()
                    .url(url)
                    .post(reqBody)
                    .build()
            ).execute().use { resp ->
                val rawBody = resp.body?.string() ?: ""
                Log.d("LIVE_TRACK", "start HTTP ${resp.code} :: $rawBody")

                if (!resp.isSuccessful) return null

                val obj = JSONObject(rawBody)
                val ok = obj.optBoolean("ok", false)
                if (!ok) return null

                val sessionId = obj.optString("session_id", "").trim()
                if (sessionId.isNotEmpty()) {
                    try {
                        val prefs =
                            ctx.getSharedPreferences("ANJO_LIVE_TRACK", Context.MODE_PRIVATE)
                        prefs.edit().putString("session_id", sessionId).apply()
                        Log.d("LIVE_TRACK", "session_id salvo: $sessionId")
                    } catch (t: Throwable) {
                        Log.e("LIVE_TRACK", "erro ao salvar session_id", t)
                    }
                }

                obj.optString("tracking_url").takeIf { it.isNotBlank() }
            }
        } catch (t: Throwable) {
            Log.e("LIVE_TRACK", "erro startLiveTrack", t)
            null
        }
    }

    // ---------------------------------------------------------
    // Live Tracking – /api/live-track/update
    // ---------------------------------------------------------
    private fun updateLiveTrackInternal(lat: Double?, lon: Double?) {
        if (!liveTrackEnabled) return
        if (liveTrackBaseUrl.isBlank()) {
            Log.d("LIVE_TRACK", "skip update: baseUrl vazio")
            return
        }
        if (lat == null || lon == null) {
            Log.d("LIVE_TRACK", "skip update: sem coordenadas")
            return
        }

        val prefs = ctx.getSharedPreferences("ANJO_LIVE_TRACK", Context.MODE_PRIVATE)
        val sessionId = prefs.getString("session_id", null)?.trim()
        if (sessionId.isNullOrEmpty()) {
            Log.d("LIVE_TRACK", "skip update: session_id vazio")
            return
        }

        val base = liveTrackBaseUrl.trimEnd('/')
        val url = "$base/api/live-track/update"

        try {
            val bodyJson = JSONObject()
                .put("session_id", sessionId)
                .put("lat", lat)
                .put("lon", lon)

            val reqBody = bodyJson.toString().toRequestBody(json)

            val client = http.newBuilder()
                .connectTimeout(3, TimeUnit.SECONDS)
                .readTimeout(5, TimeUnit.SECONDS)
                .build()

            client.newCall(
                Request.Builder()
                    .url(url)
                    .post(reqBody)
                    .build()
            ).execute().use { resp ->
                val rawBody = resp.body?.string()?.take(200) ?: ""
                Log.d("LIVE_TRACK", "update HTTP ${resp.code} :: $rawBody")
            }
        } catch (t: Throwable) {
            Log.e("LIVE_TRACK", "erro updateLiveTrack", t)
        }
    }

    // Método público chamado pelo Flutter (via NativeSos), se quiser:
    fun liveTrackUpdate(lat: Double?, lon: Double?) {
        thread {
            updateLiveTrackInternal(lat, lon)
        }
    }

    // ---------- Permissão de localização (para o loop interno) ----------
    private fun hasLocationPermission(): Boolean {
        val fine = ContextCompat.checkSelfPermission(
            ctx,
            android.Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        val coarse = ContextCompat.checkSelfPermission(
            ctx,
            android.Manifest.permission.ACCESS_COARSE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        return fine || coarse
    }

    // ---------- Loop interno de live tracking (requestLocationUpdates) ----------
    private fun startLiveTrackLoop() {
        if (!liveTrackEnabled) {
            Log.d("LIVE_TRACK", "loop nao iniciado: liveTrackEnabled=false")
            return
        }
        if (liveTrackBaseUrl.isBlank()) {
            Log.d("LIVE_TRACK", "loop nao iniciado: baseUrl vazio")
            return
        }
        if (!hasLocationPermission()) {
            Log.w("LIVE_TRACK", "loop nao iniciado: sem permissao de localizacao")
            return
        }
        // Evita criar 2 loops em paralelo
        if (liveTrackCallback != null) {
            Log.d("LIVE_TRACK", "loop ja em execucao, nao recriando")
            return
        }

        val fused = LocationServices.getFusedLocationProviderClient(ctx)

        liveTrackStopAtMs = SystemClock.elapsedRealtime() + liveTrackMaxDurationMs

        val request = LocationRequest.Builder(
            Priority.PRIORITY_BALANCED_POWER_ACCURACY,
            liveTrackIntervalMs
        )
            .setMinUpdateIntervalMillis(liveTrackIntervalMs)
            .setMaxUpdateDelayMillis(liveTrackIntervalMs * 2)
            .build()

        liveTrackCallback = object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                val now = SystemClock.elapsedRealtime()
                if (now > liveTrackStopAtMs) {
                    Log.d("LIVE_TRACK", "loop encerrado por timeout (30min)")
                    fused.removeLocationUpdates(this)
                    liveTrackCallback = null
                    return
                }

                val loc = result.lastLocation
                if (loc != null) {
                    Log.d(
                        "LIVE_TRACK",
                        "loop update lat=${loc.latitude} lon=${loc.longitude}"
                    )
                    thread {
                        try {
                            updateLiveTrackInternal(loc.latitude, loc.longitude)
                        } catch (e: Throwable) {
                            Log.e("LIVE_TRACK", "erro updateLiveTrack (loop)", e)
                        }
                    }
                } else {
                    Log.d("LIVE_TRACK", "loop sem lastLocation (null)")
                }
            }
        }

        fused.requestLocationUpdates(
            request,
            liveTrackCallback!!,
            Looper.getMainLooper()
        )

        Log.d("LIVE_TRACK", "loop iniciado (intervalo=${liveTrackIntervalMs}ms)")
    }

    fun stopLiveTrackLoop() {
        liveTrackCallback?.let { cb ->
            val fused = LocationServices.getFusedLocationProviderClient(ctx)
            fused.removeLocationUpdates(cb)
        }
        liveTrackCallback = null
        liveTrackStopAtMs = 0L
        Log.d("LIVE_TRACK", "loop parado manualmente")
    }

    /**
     * Envia para os canais usando segredos do BuildConfig e destinatários vindos da UI.
     */
    fun sendAll(
        text: String,
        lat: Double?, lon: Double?,
        tgTarget: String?,
        smsTo: List<String>,
        waTo: List<String>,
        emailTo: List<String>
    ) {
        // Tudo em segundo plano para não violar StrictMode (NetworkOnMainThread)
        thread {
            // texto base (sem link)
            val baseText = text

            // Nome completo para todos os canais que precisam
            val nomeCompleto = getNomeCompletoFromPrefs() ?: "Contato"

            // 1) Tenta iniciar live tracking e pegar o tracking_url
            val trackingLink = startLiveTrack(baseText, lat, lon)

            // 1.1) Se conseguiu criar sessão, inicia o loop nativo de updates
            if (trackingLink != null) {
                startLiveTrackLoop()
            }

            // 2) Se não vier tracking_url, cai no link tradicional do Google Maps
            val link = trackingLink ?: mapsLink(lat, lon)

            // Texto completo p/ canais que usam texto direto
            val fullText = if (link != null) {
                "$baseText\nLocalização (mapa): $link"
            } else {
                baseText
            }

            Log.d(
                "ANJO_SOS",
                "dispatch -> smsTo=${smsTo.size} waTo=${waTo.size} emailTo=${emailTo.size} " +
                        "lat=$lat lon=$lon trackingLink=$trackingLink"
            )

            // TELEGRAM
            thread {
                try {
                    sendTelegram(fullText, tgTarget, lat, lon)
                } catch (t: Throwable) {
                    Log.e("TG", "falha TG", t)
                }
            }

            // SMS (Zenvia)
            thread {
                try {
                    sendZenviaSms(fullText, smsTo)
                } catch (t: Throwable) {
                    Log.e("ZENVIA_SMS", "falha SMS", t)
                }
            }

            // WHATSAPP (Zenvia – usando TEMPLATE aprovado)
            thread {
                try {
                    sendZenviaWhats(fullText, waTo, link)
                } catch (t: Throwable) {
                    Log.e("ZENVIA_WA", "falha WA geral", t)
                }
            }

            // E-MAIL – via backend FastAPI (/api/email-sos)
            thread {
                try {
                    val finalTracking = trackingLink ?: link
                    sendEmailViaBackend(
                        nomeCompleto,
                        lat,
                        lon,
                        finalTracking,
                        emailTo
                    )
                } catch (t: Throwable) {
                    Log.e("MAIL_BACKEND", "falha MAIL via backend", t)
                }
            }
        }
    }

    // ---------------- Telegram ----------------
    private fun sendTelegram(msg: String, target: String?, lat: Double?, lon: Double?) {
        val token = BuildConfig.TELEGRAM_BOT_TOKEN
        if (token.isBlank()) {
            Log.d("TG", "skip: TELEGRAM_BOT_TOKEN vazio")
            return
        }
        val chatId = ((target ?: "").trim().ifEmpty { BuildConfig.TELEGRAM_CHAT_ID })
        if (chatId.isBlank()) {
            Log.d("TG", "skip: chat_id vazio/placeholder")
            return
        }

        // 1) Mensagem
        run {
            val url = "https://api.telegram.org/bot$token/sendMessage"
            val body = JSONObject()
                .put("chat_id", chatId)
                .put("text", msg)
                .put("parse_mode", "HTML")
                .toString().toRequestBody(json)

            val req = Request.Builder().url(url).post(body).build()
            http.newCall(req).execute().use { logResp("TG", it) }
        }

        // 2) Localização (opcional)
        if (lat != null && lon != null) {
            val url = "https://api.telegram.org/bot$token/sendLocation"
            val body = JSONObject()
                .put("chat_id", chatId)
                .put("latitude", lat)
                .put("longitude", lon)
                .toString().toRequestBody(json)

            val req = Request.Builder().url(url).post(body).build()
            http.newCall(req).execute().use { logResp("TG", it) }
        }
    }

    // ---------------- Zenvia SMS (com logs) ----------------
    private fun sendZenviaSms(msg: String, list: List<String>) {
        val token = BuildConfig.ZENVIA_TOKEN
        val from = BuildConfig.ZENVIA_SMS_FROM
        Log.d(
            "ZENVIA_SMS",
            "start to=${list.size} tokenBlank=${token.isBlank()} fromBlank=${from.isBlank()}"
        )
        if (token.isBlank() || from.isBlank()) {
            Log.w("ZENVIA_SMS", "skip: missing token/from")
            return
        }
        if (list.isEmpty()) {
            Log.w("ZENVIA_SMS", "skip: empty recipients list")
            return
        }

        val url = "https://api.zenvia.com/v2/channels/sms/messages"

        // Ajusta "ALERTA de Contato" -> "ALERTA de {Nome Completo}"
        val nomeCompleto = getNomeCompletoFromPrefs()
        val adjustedMsg = if (!nomeCompleto.isNullOrBlank()) {
            val pattern = Regex("ALERTA de\\s+Contato", RegexOption.IGNORE_CASE)
            val replaced = pattern.replace(msg) { "ALERTA de $nomeCompleto" }
            Log.d("ZENVIA_SMS", "msg ajustada com nomeCompleto='$nomeCompleto'")
            replaced
        } else {
            msg
        }

        val safeMsg = stripForSms(adjustedMsg)

        list.filter { it.isNotBlank() }.forEach { to ->
            try {
                val body = JSONObject()
                    .put("from", from)
                    .put("to", to)
                    .put(
                        "contents",
                        JSONArray().put(
                            JSONObject()
                                .put("type", "text")
                                .put("text", safeMsg)
                        )
                    )
                    .toString().toRequestBody(json)

                val req = Request.Builder()
                    .url(url)
                    .addHeader("X-API-TOKEN", token)
                    .post(body)
                    .build()

                http.newCall(req).execute().use { resp ->
                    val respBody = resp.body?.string()?.take(400)
                    Log.d("ZENVIA_SMS", "HTTP ${resp.code} to=$to body=$respBody")
                }
            } catch (t: Throwable) {
                Log.e("ZENVIA_SMS", "err to=$to", t)
            }
        }
    }

    // =============================================================
    //  ZENVIA WHATSAPP – TEMPLATE APROVADO
    // =============================================================
    private fun sendZenviaWhats(
        msg: String,
        list: List<String>,
        linkRastreamento: String?
    ) {
        val token = BuildConfig.ZENVIA_TOKEN
        val from = BuildConfig.ZENVIA_WA_FROM

        Log.d(
            "ZENVIA_WA",
            "start WA to=${list.size} tokenBlank=${token.isBlank()} fromBlank=${from.isBlank()} link=$linkRastreamento"
        )

        if (token.isBlank() || from.isBlank()) {
            Log.w("ZENVIA_WA", "skip WA: token/from vazios")
            return
        }

        // Normaliza tudo para SÓ dígitos (igual no backend FastAPI)
        val tos = list
            .map { normalizeMsisdn(it) }
            .filter { it.isNotBlank() }
            .distinct()

        Log.d("ZENVIA_WA", "tosNormalized=$tos")
        if (tos.isEmpty()) {
            Log.w("ZENVIA_WA", "skip WA: lista vazia depois de normalizar")
            return
        }

        // Link de rastreamento para o campo {{link_rastreamento}}
        val trackingLink = (linkRastreamento ?: "https://maps.google.com/?q=0,0").trim()
        Log.d("ZENVIA_WA", "using link_rastreamento=$trackingLink")

        val templateId = "406d05ec-cd3c-4bca-add3-ddd521aef484"

        val nome = getNomeCompletoFromPrefs() ?: extractNomeFromText(msg)

        val url = "https://api.zenvia.com/v2/channels/whatsapp/messages"

        tos.forEach { to ->
            try {
                val fields = JSONObject()
                    .put("nome", nome)
                    .put("link_rastreamento", trackingLink)

                val contents = JSONArray().put(
                    JSONObject()
                        .put("type", "template")
                        .put("templateId", templateId)
                        .put("fields", fields)
                )

                val body = JSONObject()
                    .put("from", from)
                    .put("to", to)
                    .put("contents", contents)
                    .toString()
                    .toRequestBody(json)

                val req = Request.Builder()
                    .url(url)
                    .addHeader("X-API-TOKEN", token)
                    .post(body)
                    .build()

                http.newCall(req).execute().use { resp ->
                    val respBody = resp.body?.string()?.take(400)
                    Log.d("ZENVIA_WA", "HTTP ${resp.code} to=$to body=$respBody")
                }
            } catch (t: Throwable) {
                Log.e("ZENVIA_WA", "err to=$to", t)
            }
        }
    }

    // Fallback para extrair nome do texto
    private fun extractNomeFromText(msg: String): String {
        val marker = "ALERTA de "
        val idx = msg.indexOf(marker)
        if (idx >= 0) {
            val start = idx + marker.length
            val endIdx = msg.indexOf('\n', start)
            val raw = if (endIdx >= 0) {
                msg.substring(start, endIdx)
            } else {
                msg.substring(start)
            }.trim()

            if (raw.isNotEmpty()) {
                return raw
            }
        }
        return "Contato"
    }

    // ---------------- E-mail via backend FastAPI ----------------
    private fun sendEmailViaBackend(
        msg: String,
        list: List<String>,
        trackingLink: String?
    ) {
        val baseUrl = liveTrackBaseUrl
        if (baseUrl.isBlank()) {
            Log.d("MAIL_BACKEND", "skip MAIL: baseUrl vazio")
            return
        }

        // Mesmo se a lista vier vazia, deixamos o backend decidir o fallback
        val emails = list.filter { it.isNotBlank() }.map { it.trim() }

        val emailsLog = if (emails.isEmpty()) {
            "(vazio - backend vai usar fallback do .env)"
        } else {
            emails.joinToString()
        }
        Log.d(
            "MAIL_BACKEND",
            "preparando chamada /api/email-sos emails=$emailsLog tracking=$trackingLink"
        )

        val base = baseUrl.trimEnd('/')
        val url = "$base/api/email-sos"

        try {
            val toArr = JSONArray()
            emails.forEach { toArr.put(it) }

            val bodyJson = JSONObject()
                .put("subject", "SOS – Anjo da Guarda")
                .put("text", msg)
                .put("to_list", toArr)

            if (!trackingLink.isNullOrBlank()) {
                bodyJson.put("tracking_url", trackingLink)
            }

            val reqBody = bodyJson.toString().toRequestBody(json)

            val req = Request.Builder()
                .url(url)
                .post(reqBody)
                .build()

            http.newCall(req).execute().use { resp ->
                val rawBody = resp.body?.string()?.take(400) ?: ""
                Log.d("MAIL_BACKEND", "HTTP ${resp.code} :: $rawBody")
            }
        } catch (t: Throwable) {
            Log.e("MAIL_BACKEND", "erro ao enviar e-mail via backend", t)
        }
    }

