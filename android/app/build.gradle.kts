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

        // ===== BuildConfig disponíveis no código (escopo global) =====
        // Zenvia - token (já existia no seu arquivo)
        buildConfigField(
            "String",
            "ZENVIA_TOKEN",
            "\"FiFdXfsHjfE9Yk-MH2glzc1uyXB_IKqTaYYC\""
        )
    }

    // Necessário para expor BuildConfig.*
    buildFeatures { buildConfig = true }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    kotlinOptions { jvmTarget = "11" }

    // Assinatura: usa o debug para testes
    signingConfigs {
        getByName("debug")
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

            // --- ZENVIA (preencha com seus dados reais) ---
            buildConfigField(
                "String",
                "ZENVIA_SMS_FROM",
                "\"SEU_REMETENTE_SMS\""        // ex: "5511961704582"
            )
            buildConfigField(
                "String",
                "ZENVIA_WA_FROM",
                "\"SEU_REMETENTE_WHATSAPP\""   // ex: "5511961704582"
            )
            buildConfigField(
                "String",
                "SOS_SMS_TO",
                "\"5511974152712\""
            )
            buildConfigField(
                "String",
                "SOS_WA_TO",
                "\"5511974152712\""
            )

            // --- SENDGRID (e-mail) ---
            buildConfigField(
                "String",
                "SENDGRID_API_KEY",
                "\"SUA_SENDGRID_KEY\""
            )
            buildConfigField(
                "String",
                "SENDGRID_FROM",
                "\"seu-remetente@dominio.com\""
            )
            buildConfigField(
                "String",
                "SOS_EMAIL_TO",
                "\"glaucusmotta@gmail.com,glaucusmotta@hotmail.com\""
            )
        }

        release {
            // Keystore de debug apenas para testes (não usar em produção)
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
