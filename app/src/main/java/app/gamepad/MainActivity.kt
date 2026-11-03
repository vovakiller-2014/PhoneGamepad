package app.gamepad

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothSocket
import android.content.Intent
import android.content.pm.ActivityInfo
import android.content.pm.PackageManager
import android.graphics.Color
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.view.HapticFeedbackConstants
import android.view.View
import android.view.ViewGroup
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
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
    private var fcb: ValueCallback<Array<Uri>>? = null
    private val spp = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")

    private fun js(s: String) = runOnUiThread { web.evaluateJavascript(s, null) }

    private var tBase: FloatArray? = null
    private var tAcc0 = Float.NaN
    private var tLast = 0L

    private val tl = object : SensorEventListener {
        override fun onSensorChanged(e: SensorEvent) {
            val now = e.timestamp / 1_000_000
            if (now - tLast < 12) return
            tLast = now
            val deg: Double
            if (e.sensor.type == Sensor.TYPE_ACCELEROMETER) {
                val a = Math.toDegrees(Math.atan2(e.values[1].toDouble(), e.values[0].toDouble()))
                if (tAcc0.isNaN()) tAcc0 = a.toFloat()
                var d = a - tAcc0
                while (d > 180) d -= 360
                while (d < -180) d += 360
                deg = d
            } else {
                val v = e.values
                val x = v[0]; val y = v[1]; val z = v[2]
                val w = if (v.size > 3) v[3] else Math.sqrt(maxOf(0.0, 1.0 - x * x - y * y - z * z)).toFloat()
                val b = tBase
                if (b == null) { tBase = floatArrayOf(x, y, z, w); deg = 0.0 }
                else {
                    var qw = b[3] * w + b[0] * x + b[1] * y + b[2] * z
                    var qz = b[3] * z - b[0] * y + b[1] * x - b[2] * w
                    if (qw < 0) { qw = -qw; qz = -qz }
                    deg = -Math.toDegrees(2.0 * Math.atan2(qz.toDouble(), qw.toDouble()))
                }
            }
            js("onTilt($deg)")
        }
        override fun onAccuracyChanged(s: Sensor?, a: Int) {}
    }

    private fun closeBt() {
        try { sock?.close() } catch (_: Exception) {}
        sock = null; out = null
    }

    inner class Bridge {
        @JavascriptInterface fun vibrate(ms: Int) = runOnUiThread {
            try {
                val v = getSystemService(VIBRATOR_SERVICE) as Vibrator
                if (v.hasVibrator()) v.vibrate(VibrationEffect.createOneShot(maxOf(ms, 25).toLong(), VibrationEffect.DEFAULT_AMPLITUDE))
            } catch (_: Exception) {}
            try {
                @Suppress("DEPRECATION")
                window.decorView.performHapticFeedback(
                    if (ms >= 20) HapticFeedbackConstants.LONG_PRESS else HapticFeedbackConstants.KEYBOARD_TAP,
                    HapticFeedbackConstants.FLAG_IGNORE_GLOBAL_SETTING or HapticFeedbackConstants.FLAG_IGNORE_VIEW_SETTING)
            } catch (_: Exception) {}
        }

        @JavascriptInterface fun rumble(a: Int) {
            try {
                val v = getSystemService(VIBRATOR_SERVICE) as Vibrator
                if (a <= 0) v.cancel() else v.vibrate(VibrationEffect.createOneShot(1000, a.coerceIn(1, 255)))
            } catch (_: Exception) {}
        }

        @JavascriptInterface fun orient(land: Boolean) = runOnUiThread {
            requestedOrientation = if (land) ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
            else ActivityInfo.SCREEN_ORIENTATION_FULL_SENSOR
        }

        @JavascriptInterface fun share(s: String) = runOnUiThread {
            startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, s), null))
        }

        @JavascriptInterface fun exit() = runOnUiThread { finish() }

        @JavascriptInterface fun tilt(on: Boolean) = runOnUiThread {
            val m = getSystemService(SENSOR_SERVICE) as SensorManager
            m.unregisterListener(tl)
            tBase = null; tAcc0 = Float.NaN
            if (on) {
                val s = m.getDefaultSensor(Sensor.TYPE_GAME_ROTATION_VECTOR)
                    ?: m.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR)
                    ?: m.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
                m.registerListener(tl, s, 10_000)
            }
        }

        @JavascriptInterface fun tiltZero() { tBase = null; tAcc0 = Float.NaN }

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
            webChromeClient = object : WebChromeClient() {
                override fun onShowFileChooser(w: WebView?, cb: ValueCallback<Array<Uri>>?, p: WebChromeClient.FileChooserParams?): Boolean {
                    fcb?.onReceiveValue(null); fcb = cb
                    return try { startActivityForResult(p!!.createIntent(), 77); true } catch (_: Exception) { fcb = null; false }
                }
            }
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

    @Suppress("DEPRECATION", "OVERRIDE_DEPRECATION")
    override fun onActivityResult(rc: Int, res: Int, data: Intent?) {
        if (rc == 77) { fcb?.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(res, data)); fcb = null }
        else super.onActivityResult(rc, res, data)
    }

    override fun onDestroy() {
        (getSystemService(SENSOR_SERVICE) as SensorManager).unregisterListener(tl)
        closeBt(); super.onDestroy()
    }
}
