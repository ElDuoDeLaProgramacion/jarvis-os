plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "co.jarvis.os"
    compileSdk = 34

    defaultConfig {
        applicationId = "co.jarvis.os"
        minSdk = 26
        targetSdk = 34
        versionCode = (System.getenv("GITHUB_RUN_NUMBER") ?: "1").toInt()
        versionName = "1.0." + (System.getenv("GITHUB_RUN_NUMBER") ?: "0")
    }

    // El workflow deja la misma clave en cada versión (caché de Actions) para que el APK nuevo
    // se instale encima del anterior. Sin ella, se usa la clave de depuración de la máquina.
    val clave = rootProject.file("debug.keystore")
    if (clave.exists()) {
        signingConfigs.getByName("debug").storeFile = clave
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("com.alphacephei:vosk-android:0.3.75")
    implementation("net.java.dev.jna:jna:5.13.0@aar")
}
