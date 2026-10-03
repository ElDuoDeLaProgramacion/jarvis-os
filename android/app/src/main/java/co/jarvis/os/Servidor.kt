package co.jarvis.os

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** La API de servidor/api.py: manda el audio a /api/voz y lee las respuestas en /api/conversacion. */
class Servidor(direccion: String, private val token: String) {

    private val base = direccion.trim().removeSuffix("/").removeSuffix("/app").removeSuffix("/")

    private fun abrir(ruta: String, espera: Int): HttpURLConnection =
        (URL(base + ruta).openConnection() as HttpURLConnection).apply {
            connectTimeout = 15_000
            readTimeout = espera
            setRequestProperty("Authorization", "Bearer $token")
        }

    private fun leer(c: HttpURLConnection): JSONObject {
        val codigo = c.responseCode
        val cuerpo = (if (codigo < 400) c.inputStream else c.errorStream)?.bufferedReader()?.readText() ?: ""
        c.disconnect()
        if (codigo == 401) throw Exception("la clave de la app no es correcta")
        if (codigo >= 400) throw Exception(runCatching { JSONObject(cuerpo).getString("error") }.getOrDefault("error $codigo"))
        return JSONObject(cuerpo)
    }

    /** Número del último mensaje, para leer solo lo que llegue después. */
    fun ultimo(): Int {
        val mensajes = leer(abrir("/api/conversacion?desde=0", 20_000)).getJSONArray("mensajes")
        return if (mensajes.length() == 0) 0 else mensajes.getJSONObject(mensajes.length() - 1).getInt("n")
    }

    /** Devuelve lo que el servidor entendió ("" si nada). Si entendió algo, ya quedó pedido. */
    fun voz(wav: ByteArray): String {
        val c = abrir("/api/voz", 180_000)
        c.requestMethod = "POST"
        c.doOutput = true
        c.setRequestProperty("Content-Type", "audio/wav")
        c.setFixedLengthStreamingMode(wav.size)
        c.outputStream.use { it.write(wav) }
        return leer(c).optString("texto", "")
    }

    /** Espera a que JARVIS termine y devuelve sus respuestas posteriores a [desde]. */
    fun respuesta(desde: Int, sigue: () -> Boolean): String {
        val limite = System.currentTimeMillis() + 20 * 60_000
        while (sigue() && System.currentTimeMillis() < limite) {
            Thread.sleep(1500)
            val datos = leer(abrir("/api/conversacion?desde=$desde", 20_000))
            if (datos.getBoolean("ocupado")) continue
            val mensajes = datos.getJSONArray("mensajes")
            val textos = (0 until mensajes.length()).map { mensajes.getJSONObject(it) }
                .filter { it.getString("de") == "jarvis" }.map { it.getString("texto") }
            if (textos.isNotEmpty()) return textos.joinToString(" ")
        }
        return ""
    }
}
