package co.jarvis.os

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import android.os.PowerManager
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import org.json.JSONObject
import org.vosk.Model
import org.vosk.Recognizer
import org.vosk.android.RecognitionListener
import org.vosk.android.SpeechService
import org.vosk.android.StorageService
import java.util.Locale
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Escucha "Jarvis" todo el tiempo, también con la pantalla apagada (servicio en primer plano con
 * notificación fija). La palabra se detecta en el celular con Vosk (modelo pequeño en español), sin
 * cuenta ni internet: un reconocedor que solo conoce "jarvis" y unas palabras señuelo
 * (res/raw/gramatica.json), así gasta poco y lo demás no se confunde con "jarvis".
 * Al oírlo: pitido, graba la orden, la manda al servidor, lee la respuesta en voz alta y, si JARVIS
 * preguntó algo, escucha la contestación sin necesidad de decir "Jarvis" otra vez.
 */
class EscuchaService : Service() {

    companion object {
        const val DETENER = "co.jarvis.os.DETENER"
        private const val CANAL = "escucha"
        private const val AVISO = 1

        @Volatile var estado = "Apagado"
            private set
        @Volatile var encendido = false
            private set
    }

    private var modelo: Model? = null
    private var oido: SpeechService? = null
    private var reconocedor: Recognizer? = null
    private var servidor: Servidor? = null
    private var voz: TextToSpeech? = null
    private val vozLista = CountDownLatch(1)
    private var despierto: PowerManager.WakeLock? = null
    private val ocupado = AtomicBoolean(false)

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(CANAL, "Escucha de Jarvis", NotificationManager.IMPORTANCE_LOW))
        voz = TextToSpeech(this) { ok ->
            if (ok == TextToSpeech.SUCCESS) {
                voz?.language = Locale("es", "ES")
                voz?.setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ASSISTANT)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
            }
            vozLista.countDown()
        }
        despierto = getSystemService(PowerManager::class.java)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "jarvis:escucha").apply { acquire() }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == DETENER) {
            stopSelf()
            return START_NOT_STICKY
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(AVISO, aviso("Iniciando…", null), ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        } else {
            startForeground(AVISO, aviso("Iniciando…", null))
        }
        val ajustes = getSharedPreferences("jarvis", Context.MODE_PRIVATE)
        servidor = Servidor(ajustes.getString("servidor", "")!!, ajustes.getString("token", "")!!)
        if (encendido) return START_STICKY
        encendido = true
        mostrar("Preparando el oído…")
        Thread {
            try {
                // El modelo viaja dentro del APK (assets/modelo); la primera vez se copia a la memoria.
                modelo = modelo ?: Model(StorageService.sync(this, "modelo", "modelo"))
                escuchar()
            } catch (e: Exception) {
                mostrar("No pude preparar el oído: ${e.message}")
            }
        }.start()
        return START_STICKY
    }

    override fun onDestroy() {
        if (encendido) estado = "Apagado"
        encendido = false
        soltarMicrofono()
        modelo?.close()
        voz?.shutdown()
        despierto?.let { if (it.isHeld) it.release() }
        super.onDestroy()
    }

    private fun escuchar() {
        try {
            val gramatica = resources.openRawResource(R.raw.gramatica).bufferedReader().readText()
            val r = Recognizer(modelo, 16000f, gramatica)
            reconocedor = r
            oido = SpeechService(r, 16000f).also {
                it.startListening(object : RecognitionListener {
                    override fun onPartialResult(json: String?) = revisar(json, "partial")
                    override fun onResult(json: String?) = revisar(json, "text")
                    override fun onFinalResult(json: String?) {}
                    override fun onError(e: Exception?) = mostrar("Error del micrófono: ${e?.message}")
                    override fun onTimeout() {}
                })
            }
            mostrar("Di \"Jarvis\" y, tras el pitido, tu pedido.")
        } catch (e: Exception) {
            mostrar("No pude abrir el micrófono: ${e.message}")
        }
    }

    private fun revisar(json: String?, campo: String) {
        val texto = runCatching { JSONObject(json ?: "{}").optString(campo) }.getOrDefault("")
        if (Regex("\\bjarvis\\b").containsMatchIn(texto)) detectado()
    }

    private fun soltarMicrofono() {
        oido?.let { it.stop(); it.shutdown() }
        oido = null
        reconocedor?.close()
        reconocedor = null
    }

    private fun detectado() {
        if (!ocupado.compareAndSet(false, true)) return
        Thread { atender() }.start()
    }

    private fun atender() {
        try {
            soltarMicrofono()   // para grabar la orden
            val s = servidor ?: return
            while (encendido) {
                pitido()
                mostrar("Te escucho…")
                val wav = Grabadora.grabar { encendido } ?: break
                mostrar("Pensando…")
                val desde = s.ultimo()
                val pedido = s.voz(wav)
                if (pedido.isBlank()) {
                    hablar("No te entendí.")
                    break
                }
                mostrar("Pensando: $pedido")
                val respuesta = s.respuesta(desde) { encendido }
                if (respuesta.isBlank()) break
                mostrar(respuesta)
                hablar(respuesta)
                if (!respuesta.trim().endsWith("?")) break   // si JARVIS preguntó, la contestación va sin "Jarvis"
            }
        } catch (e: Exception) {
            val error = "No pude hablar con el servidor: ${e.message}"
            mostrar(error)
            hablar("No pude hablar con el servidor.")
        } finally {
            ocupado.set(false)
            if (encendido) escuchar()
        }
    }

    private fun pitido() {
        runCatching {
            val tono = ToneGenerator(AudioManager.STREAM_MUSIC, 70)
            tono.startTone(ToneGenerator.TONE_PROP_BEEP, 150)
            Thread.sleep(220)
            tono.release()
        }
    }

    /** Lee el texto en voz alta y espera a que termine (para no oírse a sí mismo). */
    private fun hablar(texto: String) {
        val tts = voz ?: return
        if (!vozLista.await(10, TimeUnit.SECONDS)) return
        val fin = CountDownLatch(1)
        tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(id: String?) {}
            override fun onDone(id: String?) = fin.countDown()
            @Deprecated("Deprecated in Java")
            override fun onError(id: String?) = fin.countDown()
        })
        val limpio = texto.replace(Regex("[*_#`>|]"), "").take(TextToSpeech.getMaxSpeechInputLength() - 1)
        if (tts.speak(limpio, TextToSpeech.QUEUE_FLUSH, Bundle(), "jarvis") == TextToSpeech.SUCCESS) {
            fin.await(3, TimeUnit.MINUTES)
        }
    }

    private fun mostrar(texto: String) {
        estado = texto
        getSystemService(NotificationManager::class.java).notify(AVISO, aviso("JARVIS", texto))
    }

    private fun aviso(titulo: String, texto: String?): Notification {
        val abrir = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE)
        val detener = PendingIntent.getService(this, 1, Intent(this, EscuchaService::class.java).setAction(DETENER),
            PendingIntent.FLAG_IMMUTABLE)
        return Notification.Builder(this, CANAL)
            .setSmallIcon(R.drawable.notificacion)
            .setContentTitle(titulo)
            .setContentText(texto ?: "Escuchando \"Jarvis\"")
            .setStyle(Notification.BigTextStyle().bigText(texto ?: "Escuchando \"Jarvis\""))
            .setContentIntent(abrir)
            .setOngoing(true)
            .addAction(Notification.Action.Builder(null, "Apagar", detener).build())
            .build()
    }
}
