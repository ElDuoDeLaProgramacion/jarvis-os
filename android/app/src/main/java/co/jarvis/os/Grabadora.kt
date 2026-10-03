package co.jarvis.os

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.sqrt

/** Graba una orden: empieza cuando oye voz y para tras un silencio. Devuelve un WAV o null si nadie habló. */
object Grabadora {
    private const val TASA = 16_000
    private const val BLOQUE = TASA / 10          // 100 ms
    private const val ESPERA_VOZ = 6_000          // ms sin que empiece a hablar: nada
    private const val SILENCIO_FIN = 1_300        // ms de silencio que cierran la orden
    private const val MAXIMO = 15_000             // ms de orden como mucho

    @SuppressLint("MissingPermission")
    fun grabar(sigue: () -> Boolean): ByteArray? {
        val minimo = AudioRecord.getMinBufferSize(TASA, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val grabadora = AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, TASA, AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT, maxOf(minimo, BLOQUE * 4))
        val pcm = ByteArrayOutputStream()
        val bloque = ShortArray(BLOQUE)
        var ruido = Double.MAX_VALUE
        val antes = ArrayDeque<ByteArray>()     // lo último antes de hablar, para no cortar la primera sílaba
        var hablo = false
        var silencio = 0
        var ms = 0
        try {
            grabadora.startRecording()
            while (sigue() && ms < MAXIMO) {
                val leidos = grabadora.read(bloque, 0, BLOQUE)
                if (leidos <= 0) break
                ms += 100
                val nivel = sqrt((0 until leidos).sumOf { bloque[it].toDouble() * bloque[it] } / leidos)
                val bytes = ByteBuffer.allocate(leidos * 2).order(ByteOrder.LITTLE_ENDIAN)
                for (i in 0 until leidos) bytes.putShort(bloque[i])
                // Los primeros 300 ms miden el ruido de fondo (el bloque más bajo, por si ya empezó a hablar).
                if (ms <= 300) ruido = minOf(ruido, nivel)
                val umbral = maxOf(ruido * 2.5, 400.0)
                if (nivel > umbral) {
                    if (!hablo) antes.forEach { pcm.write(it) }
                    hablo = true
                    silencio = 0
                } else silencio += 100
                if (hablo) {
                    pcm.write(bytes.array())
                    if (silencio >= SILENCIO_FIN) break
                } else {
                    antes.addLast(bytes.array())
                    if (antes.size > 3) antes.removeFirst()
                    if (ms >= ESPERA_VOZ) break
                }
            }
        } finally {
            runCatching { grabadora.stop() }
            grabadora.release()
        }
        return if (hablo && pcm.size() > TASA / 2) wav(pcm.toByteArray()) else null
    }

    private fun wav(pcm: ByteArray): ByteArray {
        val c = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
        c.put("RIFF".toByteArray()).putInt(36 + pcm.size).put("WAVE".toByteArray())
        c.put("fmt ".toByteArray()).putInt(16).putShort(1).putShort(1).putInt(TASA).putInt(TASA * 2)
            .putShort(2).putShort(16)
        c.put("data".toByteArray()).putInt(pcm.size)
        return c.array() + pcm
    }
}
