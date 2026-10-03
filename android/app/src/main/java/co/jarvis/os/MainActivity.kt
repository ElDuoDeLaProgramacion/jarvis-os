package co.jarvis.os

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.provider.Settings
import android.text.InputType
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast

/** Ajustes (servidor y clave de la app) y el interruptor de la escucha. */
class MainActivity : Activity() {

    private lateinit var servidor: EditText
    private lateinit var token: EditText
    private lateinit var estado: TextView
    private lateinit var boton: Button
    private val reloj = Handler(Looper.getMainLooper())
    private val refrescar = object : Runnable {
        override fun run() {
            estado.text = EscuchaService.estado
            boton.text = if (EscuchaService.encendido) "Apagar la escucha" else "Activar la escucha"
            reloj.postDelayed(this, 1000)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val ajustes = getSharedPreferences("jarvis", Context.MODE_PRIVATE)
        val raiz = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 64, 48, 48)
        }
        fun etiqueta(texto: String) = raiz.addView(TextView(this).apply {
            text = texto
            setPadding(0, 32, 0, 8)
        })
        fun campo(clave: String, pista: String, oculto: Boolean) = EditText(this).apply {
            hint = pista
            setText(ajustes.getString(clave, ""))
            isSingleLine = true
            inputType = InputType.TYPE_CLASS_TEXT or
                (if (oculto) InputType.TYPE_TEXT_VARIATION_PASSWORD else InputType.TYPE_TEXT_VARIATION_URI)
            raiz.addView(this, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        }

        raiz.addView(TextView(this).apply {
            text = "JARVIS"
            textSize = 28f
        })
        raiz.addView(TextView(this).apply {
            text = "Con la escucha activa, di \"Jarvis\", espera el pitido y di tu pedido. " +
                "Funciona con la pantalla apagada y con otras apps abiertas."
        })
        etiqueta("Dirección del servidor (la misma de la app web)")
        servidor = campo("servidor", "https://servidor.tu-red.ts.net", false)
        etiqueta("Clave de la app (JARVIS_API_TOKEN)")
        token = campo("token", "La misma que pegaste en la app web", true)

        boton = Button(this).apply { setOnClickListener { alternar() } }
        raiz.addView(boton, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = 48 })
        estado = TextView(this).apply { setPadding(0, 32, 0, 0) }
        raiz.addView(estado)

        setContentView(ScrollView(this).apply { addView(raiz) })
    }

    override fun onResume() {
        super.onResume()
        reloj.post(refrescar)
    }

    override fun onPause() {
        reloj.removeCallbacks(refrescar)
        super.onPause()
    }

    private fun alternar() {
        if (EscuchaService.encendido) {
            startService(Intent(this, EscuchaService::class.java).setAction(EscuchaService.DETENER))
            return
        }
        val valores = listOf(servidor, token).map { it.text.toString().trim() }
        if (valores.any { it.isEmpty() }) {
            Toast.makeText(this, "Llena los dos campos.", Toast.LENGTH_LONG).show()
            return
        }
        getSharedPreferences("jarvis", Context.MODE_PRIVATE).edit()
            .putString("servidor", valores[0]).putString("token", valores[1])
            .apply()
        val faltan = mutableListOf(Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= 33) faltan += Manifest.permission.POST_NOTIFICATIONS
        faltan.removeAll { checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED }
        if (faltan.isNotEmpty()) {
            requestPermissions(faltan.toTypedArray(), 1)
            return
        }
        encender()
    }

    override fun onRequestPermissionsResult(codigo: Int, permisos: Array<out String>, resultados: IntArray) {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            encender()
        } else {
            Toast.makeText(this, "Sin permiso de micrófono no puedo escucharte.", Toast.LENGTH_LONG).show()
        }
    }

    @SuppressLint("BatteryLife")
    private fun encender() {
        startForegroundService(Intent(this, EscuchaService::class.java))
        // Sin esto, el ahorro de batería puede dormir la escucha con la pantalla apagada.
        if (!getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(packageName)) {
            startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                Uri.parse("package:$packageName")))
        }
    }
}
