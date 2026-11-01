plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val ksFile: String? = System.getenv("KS_FILE")
val ksPass: String? = System.getenv("KS_PASS")
val useKey = ksFile != null && ksPass != null && file(ksFile).length() > 0

android {
    namespace = "app.gamepad"
    compileSdk = 34
    defaultConfig {
        applicationId = "app.gamepad"
        minSdk = 26
        targetSdk = 34
        versionCode = 3
        versionName = "3.0"
    }
    signingConfigs {
        if (useKey) {
            create("rel") {
                storeFile = file(ksFile!!)
                storePassword = ksPass
                keyAlias = "gamepad"
                keyPassword = ksPass
            }
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            signingConfig = signingConfigs.getByName(if (useKey) "rel" else "debug")
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
        }
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
}

dependencies { implementation("com.google.android.gms:play-services-code-scanner:16.1.0") }
