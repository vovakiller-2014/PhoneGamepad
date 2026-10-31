package app.gamepad

import android.annotation.SuppressLint
import android.app.Activity
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.view.WindowManager
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
class MainActivity : Activity() {
    private lateinit var web: WebView
    private lateinit var form: View
    private lateinit var ip: EditText
    private lateinit var pin: EditText
    private val prefs by lazy { getSharedPreferences("gp", MODE_PRIVATE) }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private fun box(c: Int, fill: Int = Color.TRANSPARENT) = GradientDrawable().apply {
        setColor(fill); setStroke(dp(1), c); cornerRadius = dp(12).toFloat()
    }

    private fun field(h: String, type: Int) = EditText(this).apply {
        hint = h; inputType = type; isSingleLine = true
        setTextColor(Color.WHITE); setHintTextColor(0xFF666666.toInt())
        background = box(0xFF444444.toInt()); setPadding(dp(14), dp(12), dp(14), dp(12))
    }

    private fun button(t: String, c: Int, filled: Boolean) = Button(this).apply {
        text = t; isAllCaps = false; stateListAnimator = null
        setTextColor(if (filled) Color.BLACK else c)
        background = box(c, if (filled) c else Color.TRANSPARENT)
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
            setBackgroundColor(Color.BLACK); visibility = View.GONE
            isHapticFeedbackEnabled = false; setOnLongClickListener { true }
            overScrollMode = View.OVER_SCROLL_NEVER
            settings.javaScriptEnabled = true; settings.domStorageEnabled = true
            webViewClient = object : WebViewClient() {
                override fun onReceivedError(v: WebView, r: WebResourceRequest, e: WebResourceError) {
                    if (r.isForMainFrame) {
                        showForm()
                        toast("Немає зв’язку з ПК. Перевір IP, PIN і Wi-Fi")
                    }
                }
            }
        }
        ip = field("IP ПК, наприклад 192.168.0.10", InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI)
        pin = field("PIN з екрана ПК", InputType.TYPE_CLASS_NUMBER)
        ip.setText(prefs.getString("ip", "")); pin.setText(prefs.getString("pin", ""))
        val go = button("Підключитись", 0xFF2ECC71.toInt(), true).apply { setOnClickListener { connect() } }
        val scan = button("Сканувати QR", 0xFFDDDDDD.toInt(), false).apply { setOnClickListener { scan() } }
        val col = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            addView(TextView(context).apply {
                text = "Геймпад"; setTextColor(Color.WHITE); textSize = 26f; typeface = Typeface.DEFAULT_BOLD
            })
            listOf(ip, pin, go, scan).forEach {
                addView(it, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12) })
            }
        }
        form = ScrollView(this).apply {
            isFillViewport = true
            addView(FrameLayout(context).apply {
                setPadding(dp(16), dp(16), dp(16), dp(16))
                addView(col, FrameLayout.LayoutParams(dp(320), -2, Gravity.CENTER))
            })
        }
        val root = FrameLayout(this).apply {
            setBackgroundColor(Color.BLACK)
            addView(web, ViewGroup.LayoutParams(-1, -1))
            addView(form, ViewGroup.LayoutParams(-1, -1))
        }
        setContentView(root)
        immersive()
        if (ip.text.isNotEmpty() && pin.text.isNotEmpty()) connect()
    }

    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_LONG).show()

    private fun connect() {
        val h = ip.text.toString().trim(); val p = pin.text.toString().trim()
        if (h.isEmpty() || p.isEmpty()) { toast("Введи IP і PIN"); return }
        prefs.edit().putString("ip", h).putString("pin", p).apply()
        val host = if (h.contains(":")) h else "$h:8080"
        form.visibility = View.GONE; web.visibility = View.VISIBLE
        web.loadUrl("http://$host/?pin=$p")
    }

    private fun showForm() {
        web.loadUrl("about:blank"); web.visibility = View.GONE; form.visibility = View.VISIBLE
    }

    private fun scan() {
        GmsBarcodeScanning.getClient(this).startScan()
            .addOnSuccessListener { code ->
                val u = Uri.parse(code.rawValue ?: return@addOnSuccessListener)
                val h = u.host; val p = u.getQueryParameter("pin")
                if (h == null || p == null) { toast("Це не QR від програми на ПК"); return@addOnSuccessListener }
                ip.setText(if (u.port > 0) "$h:${u.port}" else h); pin.setText(p); connect()
            }
            .addOnFailureListener { toast("Сканер недоступний. Введи дані вручну") }
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
    override fun onBackPressed() {
        if (web.visibility == View.VISIBLE) showForm() else super.onBackPressed()
    }

    override fun onPause() { web.onPause(); super.onPause() }
    override fun onResume() { super.onResume(); web.onResume() }
}
