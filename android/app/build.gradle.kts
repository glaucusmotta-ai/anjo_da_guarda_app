plugins {
    id("com.android.application")
    id("kotlin-android")
    // O plugin do Flutter deve vir depois
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.example.anjo_da_guarda_app"

    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    defaultConfig {
        applicationId = "com.example.anjo_da_guarda_app"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName

        // Campos padrão (vazios) para TODAS as builds
        buildConfigField("String", "TELEGRAM_BOT_TOKEN", "\"\"")
        buildConfigField("String", "TELEGRAM_CHAT_ID", "\"\"")

        buildConfigField("String", "ZENVIA_TOKEN", "\"\"")
        buildConfigField("String", "ZENVIA_SMS_FROM", "\"\"")
        buildConfigField("String", "ZENVIA_WA_FROM", "\"\"")

        buildConfigField("String", "SENDGRID_API_KEY", "\"\"")
        buildConfigField("String", "SENDGRID_FROM", "\"\"")

        // URL do backend FastAPI (emulador falando com o PC)
        buildConfigField(
            "String",
            "BACKEND_BASE_URL",
            "\"http://10.0.2.2:8000\""
        )
    }

    // Necessário para expor BuildConfig.*
    buildFeatures {
        buildConfig = true
    }

    // Java 17
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    // Assinatura: usa o debug para testes
    signingConfigs {
        getByName("debug") {
            // default debug keystore
        }
    }

    buildTypes {
        // Segredos para testes locais (debug)
        debug {
            // --- TELEGRAM ---
            buildConfigField(
                "String",
                "TELEGRAM_BOT_TOKEN",
                "\"8218538803:AAF4f01L5YpdnhqmYMKHtZPWIwZomK58yJ4\""
            )
            buildConfigField(
                "String",
                "TELEGRAM_CHAT_ID",
                "\"548741187\""
            )

            // --- ZENVIA (SMS/WhatsApp) ---
            buildConfigField(
                "String",
                "ZENVIA_TOKEN",
                "\"FiFdXfsHjfE9Yk-MH2glzc1uyXB_IKqTaYYC\""
            )
            buildConfigField(
                "String",
                "ZENVIA_SMS_FROM",
                "\"glaucusmotta\""
            )
            buildConfigField(
                "String",
                "ZENVIA_WA_FROM",
                "\"5511961704582\""
            )

            // --- SENDGRID (E-mail desativado no app; e-mail fica via backend/Zoho) ---
            buildConfigField(
                "String",
                "SENDGRID_API_KEY",
                "\"contato@3g-brasil.comUI\""
            )
            buildConfigField(
                "String",
                "SENDGRID_FROM",
                "\"alerta@3g-brasil.com\""
            )

            // Backend também no debug
            buildConfigField(
                "String",
                "BACKEND_BASE_URL",
                "\"http://10.0.2.2:8000\""
            )
        }

        release {
            // (para testes) assina com o debug; em produção usar keystore própria
            signingConfig = signingConfigs.getByName("debug")
            isMinifyEnabled = false
            isShrinkResources = false
        }
    }
}

flutter {
    source = "../.."
}

dependencies {
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.google.android.gms:play-services-location:21.3.0")
}
