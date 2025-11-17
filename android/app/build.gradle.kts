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
    }

    // Necessário para expor BuildConfig.*
    buildFeatures { buildConfig = true }

    // Use Java 17 (recomendado pelas versões atuais do Flutter/AGP)
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }

    // Assinatura: usa o debug para testes
    signingConfigs {
        getByName("debug")
    }

    buildTypes {
        // Segredos para testes locais (debug)
        debug {
            // --- TELEGRAM ---
            // BOT TOKEN fica no BuildConfig; o destino (chat_id/@canal) vem da UI
            buildConfigField(
                "String",
                "TELEGRAM_BOT_TOKEN",
                "\"\""
            )

            // --- ZENVIA (SMS/WhatsApp) ---
            // Token e remetentes (FROM) são nossos e não aparecem na UI
            buildConfigField(
                "String",
                "ZENVIA_TOKEN",
                "\"FiFdXfsHjfE9Yk-MH2glzc1uyXB_IKqTaYYC\""
            )
            buildConfigField(
                "String",
                "ZENVIA_SMS_FROM",
                "\"glaucusmotta\""        // o MESMO from que você usa hoje no Zenvia
            )
            buildConfigField(
                "String",
                "ZENVIA_WA_FROM",
                "\"5511961704582\""   // o MESMO from que você usa hoje no Zenvia
            )

            // --- SENDGRID (E-mail) ---
            // Aqui vai a CHAVE da API do SendGrid (não é e-mail)
            buildConfigField(
                "String",
                "SENDGRID_API_KEY",
                "\"\""   // coloque aqui a API key real do SendGrid quando tiver
            )
            // E-mail remetente que você vai cadastrar/verificar no SendGrid
            buildConfigField(
                "String",
                "SENDGRID_FROM",
                "\"contato@3g-brasil.com\""
            )
        }

        release {
            // (para testes) assina com o debug; em produção use seu keystore
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
