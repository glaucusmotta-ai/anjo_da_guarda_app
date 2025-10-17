import 'package:shared_preferences/shared_preferences.dart';

/// Chaves de configuração persistidas localmente.
/// Obs: Se algum campo ficar vazio, o nativo usa o fallback do BuildConfig.* (debug).
class SettingsKeys {
  // PINs
  static const pinMain = 'pin_main';
  static const pinDuress = 'pin_duress';

  // Telegram
  static const tgBotToken = 'tg_bot_token';
  static const tgChatId   = 'tg_chat_id';

  // Zenvia (SMS/WhatsApp)
  static const zenviaToken  = 'zenvia_token';
  static const zenviaSmsFrom = 'zenvia_sms_from';
  static const sosSmsTo      = 'sos_sms_to';
  static const zenviaWaFrom  = 'zenvia_wa_from';
  static const sosWaTo       = 'sos_wa_to';

  // SendGrid (e-mail)
  static const sendgridKey  = 'sendgrid_api_key';
  static const sendgridFrom = 'sendgrid_from';
  static const sosEmailTo   = 'sos_email_to';
}

/// Modelo simples (tudo opcional). Campos vazios significam “usar fallback do nativo”.
class AppSettings {
  // PINs
  String? pinMain;
  String? pinDuress;

  // Telegram
  String? tgBotToken;
  String? tgChatId;

  // Zenvia
  String? zenviaToken;
  String? zenviaSmsFrom;
  String? sosSmsTo;
  String? zenviaWaFrom;
  String? sosWaTo;

  // SendGrid
  String? sendgridKey;
  String? sendgridFrom;
  String? sosEmailTo;

  AppSettings({
    this.pinMain,
    this.pinDuress,
    this.tgBotToken,
    this.tgChatId,
    this.zenviaToken,
    this.zenviaSmsFrom,
    this.sosSmsTo,
    this.zenviaWaFrom,
    this.sosWaTo,
    this.sendgridKey,
    this.sendgridFrom,
    this.sosEmailTo,
  });

  Map<String, String> toMap() {
    final m = <String, String>{};
    void put(String k, String? v) { if (v != null) m[k] = v; }
    put(SettingsKeys.pinMain, pinMain);
    put(SettingsKeys.pinDuress, pinDuress);

    put(SettingsKeys.tgBotToken, tgBotToken);
    put(SettingsKeys.tgChatId, tgChatId);

    put(SettingsKeys.zenviaToken, zenviaToken);
    put(SettingsKeys.zenviaSmsFrom, zenviaSmsFrom);
    put(SettingsKeys.sosSmsTo, sosSmsTo);
    put(SettingsKeys.zenviaWaFrom, zenviaWaFrom);
    put(SettingsKeys.sosWaTo, sosWaTo);

    put(SettingsKeys.sendgridKey, sendgridKey);
    put(SettingsKeys.sendgridFrom, sendgridFrom);
    put(SettingsKeys.sosEmailTo, sosEmailTo);
    return m;
  }

  static AppSettings fromPrefs(SharedPreferences sp) {
    String? g(String k) => sp.getString(k);
    return AppSettings(
      pinMain: g(SettingsKeys.pinMain),
      pinDuress: g(SettingsKeys.pinDuress),
      tgBotToken: g(SettingsKeys.tgBotToken),
      tgChatId: g(SettingsKeys.tgChatId),
      zenviaToken: g(SettingsKeys.zenviaToken),
      zenviaSmsFrom: g(SettingsKeys.zenviaSmsFrom),
      sosSmsTo: g(SettingsKeys.sosSmsTo),
      zenviaWaFrom: g(SettingsKeys.zenviaWaFrom),
      sosWaTo: g(SettingsKeys.sosWaTo),
      sendgridKey: g(SettingsKeys.sendgridKey),
      sendgridFrom: g(SettingsKeys.sendgridFrom),
      sosEmailTo: g(SettingsKeys.sosEmailTo),
    );
  }
}

/// API simples para carregar/salvar configurações.
class SettingsStore {
  SettingsStore._();
  static final instance = SettingsStore._();

  Future<AppSettings> load() async {
    final sp = await SharedPreferences.getInstance();
    return AppSettings.fromPrefs(sp);
    // Obs: se algum campo vier null/empty, o nativo usará BuildConfig.* (fallback em debug)
  }

  /// Salva apenas os campos não nulos de [data]. Para limpar um campo, passe string vazia "".
  Future<void> savePartial(AppSettings data) async {
    final sp = await SharedPreferences.getInstance();
    final map = data.toMap();
    for (final e in map.entries) {
      await sp.setString(e.key, e.value);
    }
  }

  /// Atalho para salvar todos os campos (aceita null -> ignora).
  Future<void> saveAll(AppSettings data) => savePartial(data);
}
