package app.gamepad

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothSocket
import android.content.pm.ActivityInfo
import android.content.pm.PackageManager
import android.graphics.Color
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.view.View
import android.view.ViewGroup
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.WebView
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import org.json.JSONArray
import org.json.JSONObject
import java.io.OutputStream
import java.util.UUID

class MainActivity : Activity() {
    private lateinit var web: WebView
    private var sock: BluetoothSocket? = null
    private var out: OutputStream? = null
    private val spp = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")

    private fun js(s: String) = runOnUiThread { web.evaluateJavascript(s, null) }

    private val tl = object : SensorEventListener {
        override fun onSensorChanged(e: SensorEvent) { js("onTilt(${e.values[0]},${e.values[1]})") }
        override fun onAccuracyChanged(s: Sensor?, a: Int) {}
    }

    private fun closeBt() {
        try { sock?.close() } catch (_: Exception) {}
        sock = null; out = null
    }

    inner class Bridge {
        @JavascriptInterface fun vibrate(ms: Int) {
            try {
                @Suppress("DEPRECATION")
                (getSystemService(VIBRATOR_SERVICE) as Vibrator)
                    .vibrate(VibrationEffect.createOneShot(ms.toLong(), VibrationEffect.DEFAULT_AMPLITUDE))
            } catch (_: Exception) {}
        }

        @JavascriptInterface fun orient(land: Boolean) = runOnUiThread {
            requestedOrientation = if (land) ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
            else ActivityInfo.SCREEN_ORIENTATION_FULL_SENSOR
        }

        @JavascriptInterface fun exit() = runOnUiThread { finish() }

        @JavascriptInterface fun tilt(on: Boolean) = runOnUiThread {
            val m = getSystemService(SENSOR_SERVICE) as SensorManager
            m.unregisterListener(tl)
            if (on) m.registerListener(tl, m.getDefaultSensor(Sensor.TYPE_ACCELEROMETER), SensorManager.SENSOR_DELAY_GAME)
        }

        @JavascriptInterface fun scanQr() = runOnUiThread {
            GmsBarcodeScanning.getClient(this@MainActivity).startScan()
                .addOnSuccessListener { c -> c.rawValue?.let { js("onQr(${JSONObject.quote(it)})") } }
        }

        @JavascriptInterface fun btDevices(): String {
            if (Build.VERSION.SDK_INT >= 31 &&
                checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
                runOnUiThread { requestPermissions(arrayOf(Manifest.permission.BLUETOOTH_CONNECT), 1) }
                return "NOPERM"
            }
            val ad = (getSystemService(BLUETOOTH_SERVICE) as BluetoothManager).adapter ?: return "[]"
            if (!ad.isEnabled) return "OFF"
            val arr = JSONArray()
            ad.bondedDevices.forEach { arr.put(JSONObject().put("n", it.name ?: it.address).put("a", it.address)) }
            return arr.toString()
        }

        @JavascriptInterface fun btConnect(addr: String) {
            Thread {
                try {
                    val ad = (getSystemService(BLUETOOTH_SERVICE) as BluetoothManager).adapter
                    ad.cancelDiscovery()
                    val s = ad.getRemoteDevice(addr).createRfcommSocketToServiceRecord(spp)
                    s.connect(); sock = s; out = s.outputStream
                    js("onLink('bt')")
                    while (s.inputStream.read() >= 0) { }
                } catch (_: Exception) {}
                closeBt(); js("onLink('')")
            }.start()
        }

        @JavascriptInterface fun btSend(s: String) {
            try { out?.write((s + "\n").toByteArray()); out?.flush() } catch (_: Exception) { closeBt() }
        }

        @JavascriptInterface fun btClose() = closeBt()
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        if (Build.VERSION.SDK_INT >= 28) {
            window.attributes = window.attributes.also {
                it.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
            }
        }
        web = WebView(this).apply {
            setBackgroundColor(Color.BLACK)
            isHapticFeedbackEnabled = false; setOnLongClickListener { true }
            overScrollMode = View.OVER_SCROLL_NEVER
            settings.javaScriptEnabled = true; settings.domStorageEnabled = true
            addJavascriptInterface(Bridge(), "Android")
            loadUrl("file:///android_asset/app.html")
        }
        setContentView(web, ViewGroup.LayoutParams(-1, -1))
        immersive()
    }

    private fun immersive() {
        if (Build.VERSION.SDK_INT >= 30) {
            window.setDecorFitsSystemWindows(false)
            window.insetsController?.let {
                it.hide(WindowInsets.Type.systemBars())
                it.systemBarsBehavior = WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            }
        } else {
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_FULLSCREEN or
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
                View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
        }
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus); if (hasFocus) immersive()
    }

    @Suppress("DEPRECATION", "OVERRIDE_DEPRECATION")
    override fun onBackPressed() { web.evaluateJavascript("window.onBack&&window.onBack()", null) }

    override fun onDestroy() {
        (getSystemService(SENSOR_SERVICE) as SensorManager).unregisterListener(tl)
        closeBt(); super.onDestroy()
    }
}
