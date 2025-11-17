package com.example.anjo_da_guarda_app

import android.content.Context
import android.util.Log
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.MediaType.Companion.toMediaType
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

    private fun logResp(tag: String, resp: Response) {
        val code = resp.code
        val body = try { resp.body?.string() ?: "" } catch (_: Throwable) { "<no-body>" }
        Log.d(tag, "HTTP $code :: $body")
    }
   
    /**
     * Envia para os canais usando segredos do BuildConfig e destinatários vindos da UI:
     *  - tgTarget: chat_id numérico ou @canal/@grupo/@username (precisa conversa iniciada p/ PF)
     *  - smsTo/waTo/emailTo: listas de destinatários (podem estar vazias)
     */
    fun sendAll(
        text: String,
        lat: Double?, lon: Double?,
        tgTarget: String?,
        smsTo: List<String>,
        waTo: List<String>,
        emailTo: List<String>
    ) {
        val link = mapsLink(lat, lon)
        val fullText = if (link != null) "$text\nLocalização (mapa): $link" else text

        Log.d(
            "ANJO_SOS",
            "dispatch -> smsTo=${smsTo.size} waTo=${waTo.size} emailTo=${emailTo.size} " +
                    "lat=$lat lon=$lon"
        )

        // TELEGRAM (ainda disponível, mas não é prioridade)
        thread {
            runCatching { sendTelegram(fullText, tgTarget, lat, lon) }
                .onFailure { Log.e("TG", "falha TG", it) }
        }

        // SMS (Zenvia)
        thread {
            runCatching { sendZenviaSms(fullText, smsTo) }
                .onFailure { Log.e("ZENVIA_SMS", "falha SMS", it) }
        }

        // WHATSAPP (Zenvia – usando TEMPLATE aprovado)
        thread {
            runCatching { sendZenviaWhats(fullText, waTo, lat, lon) }
                .onFailure { Log.e("ZENVIA_WA", "falha WA geral", it) }
        }

        // E-MAIL (SendGrid)
        thread {
            runCatching { sendEmailSendGrid(fullText, emailTo) }
                .onFailure { Log.e("MAIL", "falha MAIL", it) }
        }
    }

    // ---------------- Telegram ----------------
    private fun sendTelegram(msg: String, target: String?, lat: Double?, lon: Double?) {
        val token = BuildConfig.TELEGRAM_BOT_TOKEN
        if (token.isBlank()) { Log.d("TG", "skip: TELEGRAM_BOT_TOKEN vazio"); return }
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
        val from  = BuildConfig.ZENVIA_SMS_FROM
        Log.d("ZENVIA_SMS", "start to=${list.size} tokenBlank=${token.isBlank()} fromBlank=${from.isBlank()}")
        if (token.isBlank() || from.isBlank()) {
            Log.w("ZENVIA_SMS", "skip: missing token/from")
            return
        }
        if (list.isEmpty()) {
            Log.w("ZENVIA_SMS", "skip: empty recipients list")
            return
        }

        val url = "https://api.zenvia.com/v2/channels/sms/messages"
        val safeMsg = stripForSms(msg)

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

   //---------------- Zenvia WhatsApp (TEMPLATE aprovado) ----------------
    private fun sendZenviaWhats(
        msg: String,
        list: List<String>,
        lat: Double?,
        lon: Double?
    ) {
        val token = BuildConfig.ZENVIA_TOKEN
        val from  = BuildConfig.ZENVIA_WA_FROM

        Log.d(
            "ZENVIA_WA",
            "start WA to=${list.size} tokenBlank=${token.isBlank()} fromBlank=${from.isBlank()} lat=$lat lon=$lon"
        )

        if (token.isBlank() || from.isBlank()) {
            Log.w("ZENVIA_WA", "skip WA: token/from vazios")
            return
        }

        // Normaliza tudo para SÓ dígitos (igual no backend FastAPI)
        val tos = list
            .map { normalizeMsisdn(it) }
            .filter { it.isNotBlank() }

        Log.d("ZENVIA_WA", "tosNormalized=$tos")
        if (tos.isEmpty()) {
            Log.w("ZENVIA_WA", "skip WA: lista vazia depois de normalizar")
            return
        }

        // Mesmo padrão do backend: "?q=lat,lon" em local_aproximado
        val locParam = if (lat != null && lon != null) {
            "?q=$lat,$lon"
        } else {
            "?q=0,0"
        }
        Log.d("ZENVIA_WA", "using local_aproximado=$locParam")

        // TEMPLATE já aprovado na Zenvia/Meta
        val templateId = "30db2264-c09a-4ae5-afc6-e2aeb234bb0c"
        val nome = extractNomeFromText(msg)

        val url = "https://api.zenvia.com/v2/channels/whatsapp/messages"

        tos.forEach { to ->
            try {
                val fields = JSONObject()
                    .put("nome", nome)
                    .put("local_aproximado", locParam)

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

    // Tira o nome a partir da primeira linha da mensagem "ALERTA de ..."
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


    // ---------------- E-mail (SendGrid) ----------------
    private fun sendEmailSendGrid(msg: String, list: List<String>) {
        val key  = BuildConfig.SENDGRID_API_KEY
        val from = BuildConfig.SENDGRID_FROM
        if (key.isBlank() || from.isBlank()) {
            Log.d("MAIL", "skip MAIL: key/from vazios")
            return
        }
        val tos = list.filter { it.isNotBlank() }
        if (tos.isEmpty()) {
            Log.d("MAIL", "skip MAIL: lista vazia")
            return
        }

        val url = "https://api.sendgrid.com/v3/mail/send"
        val toArr = JSONArray()
        tos.forEach { toArr.put(JSONObject().put("email", it)) }

        val body = JSONObject()
            .put("from", JSONObject().put("email", from))
            .put("personalizations", JSONArray().put(JSONObject().put("to", toArr)))
            .put("subject", "SOS – Anjo da Guarda")
            .put(
                "content",
                JSONArray().put(
                    JSONObject()
                        .put("type", "text/plain")
                        .put("value", msg)
                )
            )
            .toString().toRequestBody(json)

        val req = Request.Builder()
            .url(url)
            .addHeader("Authorization", "Bearer $key")
            .addHeader("Content-Type", "application/json")
            .post(body)
            .build()

        http.newCall(req).execute().use { logResp("MAIL", it) }
    }
}

