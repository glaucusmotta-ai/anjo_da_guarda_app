package com.example.anjo_da_guarda_app

import android.content.Context
import android.util.Log
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import kotlin.concurrent.thread

class SosDispatcher(private val ctx: Context) {

    private val http = OkHttpClient.Builder()
        .connectTimeout(12, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()

    private val json = "application/json; charset=utf-8".toMediaType()

    private fun mapsLink(lat: Double?, lon: Double?): String? {
        if (lat == null || lon == null) return null
        return "https://www.google.com/maps/search/?api=1&query=$lat,$lon"
    }

    /** Envia para todos os canais configurados (ignora os que estiverem sem credenciais). */
    fun sendAll(text: String, lat: Double? = null, lon: Double? = null) {
        val link = mapsLink(lat, lon)
        val fullText = if (link != null) "$text\n📍 $link" else text

        thread { runCatching { sendTelegram(fullText, lat, lon) }.onFailure { Log.e("SosDispatcher", "tg", it) } }
        thread { runCatching { sendZenviaSms(fullText)         }.onFailure { Log.e("SosDispatcher", "sms", it) } }
        thread { runCatching { sendZenviaWhats(fullText)       }.onFailure { Log.e("SosDispatcher", "wa", it) } }
        thread { runCatching { sendEmailSendGrid(fullText)     }.onFailure { Log.e("SosDispatcher", "mail", it) } }
    }

    // ---------------- Telegram ----------------
    private fun sendTelegram(msg: String, lat: Double?, lon: Double?) {
        val token = BuildConfig.TELEGRAM_BOT_TOKEN
        val chatId = BuildConfig.TELEGRAM_CHAT_ID
        if (token.isBlank() || chatId.isBlank()) return

        // 1) Mensagem
        run {
            val url = "https://api.telegram.org/bot$token/sendMessage"
            val body = JSONObject()
                .put("chat_id", chatId)
                .put("text", msg)
                .put("parse_mode", "HTML")
                .toString().toRequestBody(json)
            http.newCall(Request.Builder().url(url).post(body).build()).execute().use { }
        }
        // 2) Localização (opcional)
        if (lat != null && lon != null) {
            val url = "https://api.telegram.org/bot$token/sendLocation"
            val body = JSONObject()
                .put("chat_id", chatId)
                .put("latitude", lat)
                .put("longitude", lon)
                .toString().toRequestBody(json)
            http.newCall(Request.Builder().url(url).post(body).build()).execute().use { }
        }
    }

    // ---------------- Zenvia SMS ----------------
    private fun sendZenviaSms(msg: String) {
        val token = BuildConfig.ZENVIA_TOKEN
        val from  = BuildConfig.ZENVIA_SMS_FROM
        val to    = BuildConfig.SOS_SMS_TO
        if (token.isBlank() || from.isBlank() || to.isBlank()) return

        val url = "https://api.zenvia.com/v2/channels/sms/messages"
        val body = JSONObject()
            .put("from", from)
            .put("to", to)
            .put("contents", JSONArray().put(JSONObject().put("type", "text").put("text", msg)))
            .toString().toRequestBody(json)

        val req = Request.Builder()
            .url(url)
            .addHeader("X-API-TOKEN", token)
            .post(body)
            .build()
        http.newCall(req).execute().use { }
    }

    // ---------------- Zenvia WhatsApp ----------------
    private fun sendZenviaWhats(msg: String) {
        val token = BuildConfig.ZENVIA_TOKEN
        val from  = BuildConfig.ZENVIA_WA_FROM
        val to    = BuildConfig.SOS_WA_TO
        if (token.isBlank() || from.isBlank() || to.isBlank()) return

        val url = "https://api.zenvia.com/v2/channels/whatsapp/messages"
        val body = JSONObject()
            .put("from", from)
            .put("to", to)
            .put("contents", JSONArray().put(JSONObject().put("type", "text").put("text", msg)))
            .toString().toRequestBody(json)

        val req = Request.Builder()
            .url(url)
            .addHeader("X-API-TOKEN", token)
            .post(body)
            .build()
        http.newCall(req).execute().use { }
    }

    // ---------------- E-mail (SendGrid) ----------------
    private fun sendEmailSendGrid(msg: String) {
        val key  = BuildConfig.SENDGRID_API_KEY
        val from = BuildConfig.SENDGRID_FROM
        val toRaw = BuildConfig.SOS_EMAIL_TO
        if (key.isBlank() || from.isBlank() || toRaw.isBlank()) return

        // Aceita vários destinatários separados por vírgula ou ponto-e-vírgula
        val recipients = toRaw.split(',', ';')
            .map { it.trim() }
            .filter { it.isNotEmpty() }

        if (recipients.isEmpty()) return

        val toArray = JSONArray()
        recipients.forEach { email ->
            toArray.put(JSONObject().put("email", email))
        }

        val url = "https://api.sendgrid.com/v3/mail/send"
        val body = JSONObject()
            .put("from", JSONObject().put("email", from))
            .put("personalizations", JSONArray().put(
                JSONObject().put("to", toArray)
            ))
            .put("subject", "🚨 SOS ANJO DA GUARDA")
            .put("content", JSONArray().put(
                JSONObject().put("type", "text/plain").put("value", msg)
            ))
            .toString().toRequestBody(json)

        val req = Request.Builder()
            .url(url)
            .addHeader("Authorization", "Bearer $key")
            .addHeader("Content-Type", "application/json")
            .post(body)
            .build()

        http.newCall(req).execute().use { }
    }
}
