// lib/services/settings_store.dart
import 'package:shared_preferences/shared_preferences.dart';

class AppSettings {
  // Dados do cliente
  final String? userName;
  final String? userPhone; // E.164 (+55...)
  final String? userEmail;

  // Preferências
  final bool pinSecondLayerEnabled;
  final bool qsEnabled;      // Quick Settings Tile
  final int  testCount;      // 0..2

  // PINs
  final String? pinMain;     // 4 dígitos
  final String? pinDuress;   // 4 dígitos
  final String? pinAudio;    // reservado

  // Telegram
  final String? tgTarget;    // chat_id numérico ou @username/@canal
  final String? tgBotToken;  // opcional (normalmente via BuildConfig)

  // SMS (3)
  final String? smsTo1, smsTo2, smsTo3;

  // WhatsApp (3)
  final String? waTo1, waTo2, waTo3;

  // E-mail (3)
  final String? emailTo1, emailTo2, emailTo3;

  // Segredos (opcionais)
  final String? zenviaToken, zenviaSmsFrom, zenviaWaFrom;
  final String? sendgridKey, sendgridFrom;

  const AppSettings({
    this.userName,
    this.userPhone,
    this.userEmail,
    this.pinSecondLayerEnabled = true,
    this.qsEnabled = true,
    this.testCount = 0,
    this.pinMain,
    this.pinDuress,
    this.pinAudio,
    this.tgTarget,
    this.tgBotToken,
    this.smsTo1, this.smsTo2, this.smsTo3,
    this.waTo1,  this.waTo2,  this.waTo3,
    this.emailTo1, this.emailTo2, this.emailTo3,
    this.zenviaToken, this.zenviaSmsFrom, this.zenviaWaFrom,
    this.sendgridKey, this.sendgridFrom,
  });

  AppSettings copyWith({
    String? userName,
    String? userPhone,
    String? userEmail,
    bool? pinSecondLayerEnabled,
    bool? qsEnabled,
    int?  testCount,
    String? pinMain,
    String? pinDuress,
    String? pinAudio,
    String? tgTarget,
    String? tgBotToken,
    String? smsTo1, String? smsTo2, String? smsTo3,
    String? waTo1,  String? waTo2,  String? waTo3,
    String? emailTo1, String? emailTo2, String? emailTo3,
    String? zenviaToken, String? zenviaSmsFrom, String? zenviaWaFrom,
    String? sendgridKey, String? sendgridFrom,
  }) {
    return AppSettings(
      userName: userName ?? this.userName,
      userPhone: userPhone ?? this.userPhone,
      userEmail: userEmail ?? this.userEmail,
      pinSecondLayerEnabled: pinSecondLayerEnabled ?? this.pinSecondLayerEnabled,
      qsEnabled: qsEnabled ?? this.qsEnabled,
      testCount: testCount ?? this.testCount,
      pinMain: pinMain ?? this.pinMain,
      pinDuress: pinDuress ?? this.pinDuress,
      pinAudio: pinAudio ?? this.pinAudio,
      tgTarget: tgTarget ?? this.tgTarget,
      tgBotToken: tgBotToken ?? this.tgBotToken,
      smsTo1: smsTo1 ?? this.smsTo1,
      smsTo2: smsTo2 ?? this.smsTo2,
      smsTo3: smsTo3 ?? this.smsTo3,
      waTo1: waTo1 ?? this.waTo1,
      waTo2: waTo2 ?? this.waTo2,
      waTo3: waTo3 ?? this.waTo3,
      emailTo1: emailTo1 ?? this.emailTo1,
      emailTo2: emailTo2 ?? this.emailTo2,
      emailTo3: emailTo3 ?? this.emailTo3,
      zenviaToken: zenviaToken ?? this.zenviaToken,
      zenviaSmsFrom: zenviaSmsFrom ?? this.zenviaSmsFrom,
      zenviaWaFrom: zenviaWaFrom ?? this.zenviaWaFrom,
      sendgridKey: sendgridKey ?? this.sendgridKey,
      sendgridFrom: sendgridFrom ?? this.sendgridFrom,
    );
  }
}

class SettingsStore {
  SettingsStore._();
  static final SettingsStore instance = SettingsStore._();

  // Keys
  static const _kUserName  = 'user_name';
  static const _kUserPhone = 'user_phone';
  static const _kUserEmail = 'user_email';

  static const _kPinSecondEnabled = 'pin_second_enabled';
  static const _kQsEnabled        = 'qs_enabled';
  static const _kTestCount        = 'test_count';

  static const _kPinMain   = 'pin_main';
  static const _kPinDuress = 'pin_duress';
  static const _kPinAudio  = 'pin_audio';

  static const _kTgTarget  = 'tg_target';
  static const _kTgToken   = 'tg_bot_token';

  static const _kSmsTo1 = 'sms_to1';
  static const _kSmsTo2 = 'sms_to2';
  static const _kSmsTo3 = 'sms_to3';

  static const _kWaTo1 = 'wa_to1';
  static const _kWaTo2 = 'wa_to2';
  static const _kWaTo3 = 'wa_to3';

  static const _kEmailTo1 = 'email_to1';
  static const _kEmailTo2 = 'email_to2';
  static const _kEmailTo3 = 'email_to3';

  static const _kZenviaToken   = 'zenvia_token';
  static const _kZenviaSmsFrom = 'zenvia_sms_from';
  static const _kZenviaWaFrom  = 'zenvia_wa_from';
  static const _kSendGridKey   = 'sendgrid_key';
  static const _kSendGridFrom  = 'sendgrid_from';

  // -------- Helpers --------
  static String? _nn(String? s) {
    final t = (s ?? '').trim();
    return t.isEmpty ? null : t;
  }

  Future<void> _setOrRemove(SharedPreferences sp, String k, String? v) async {
    final t = _nn(v);
    if (t == null) {
      await sp.remove(k);
    } else {
      await sp.setString(k, t);
    }
  }

  // v == null → preserva; v != null → grava (ou remove se vazio)
  Future<void> _setOrKeep(SharedPreferences sp, String k, String? v) async {
    if (v == null) return;
    await _setOrRemove(sp, k, v);
  }

  // -------- Load --------
  Future<AppSettings> load() async {
    final sp = await SharedPreferences.getInstance();
    String _gs(String k, {String def = ''}) => (sp.getString(k) ?? def).trim();

    return AppSettings(
      userName:  _nn(_gs(_kUserName)),
      userPhone: _nn(_gs(_kUserPhone)),
      userEmail: _nn(_gs(_kUserEmail)),

      pinSecondLayerEnabled: sp.getBool(_kPinSecondEnabled) ?? true,
      qsEnabled:              sp.getBool(_kQsEnabled)        ?? true,
      testCount:             (sp.getInt(_kTestCount) ?? 0).clamp(0, 2),

      pinMain:   _gs(_kPinMain,   def: '1234'),
      pinDuress: _gs(_kPinDuress, def: '2580'),
      pinAudio:  _gs(_kPinAudio),

      tgTarget:   _nn(_gs(_kTgTarget)),
      tgBotToken: _nn(_gs(_kTgToken)),

      smsTo1: _nn(_gs(_kSmsTo1)), smsTo2: _nn(_gs(_kSmsTo2)), smsTo3: _nn(_gs(_kSmsTo3)),
      waTo1:  _nn(_gs(_kWaTo1)),  waTo2:  _nn(_gs(_kWaTo2)),  waTo3:  _nn(_gs(_kWaTo3)),
      emailTo1: _nn(_gs(_kEmailTo1)), emailTo2: _nn(_gs(_kEmailTo2)), emailTo3: _nn(_gs(_kEmailTo3)),

      zenviaToken:   _nn(_gs(_kZenviaToken)),
      zenviaSmsFrom: _nn(_gs(_kZenviaSmsFrom)),
      zenviaWaFrom:  _nn(_gs(_kZenviaWaFrom)),
      sendgridKey:   _nn(_gs(_kSendGridKey)),
      sendgridFrom:  _nn(_gs(_kSendGridFrom)),
    );
  }

  // -------- Save (preserva quando valor é null) --------
  Future<void> saveAll(AppSettings s) async {
    final sp = await SharedPreferences.getInstance();

    // bool/int sempre escritos
    await sp.setBool(_kPinSecondEnabled, s.pinSecondLayerEnabled);
    await sp.setBool(_kQsEnabled,        s.qsEnabled);
    await sp.setInt (_kTestCount,        s.testCount.clamp(0, 2));

    // strings com preservação
    await _setOrKeep(sp, _kUserName,  s.userName);
    await _setOrKeep(sp, _kUserPhone, s.userPhone);
    await _setOrKeep(sp, _kUserEmail, s.userEmail);

    await _setOrKeep(sp, _kPinMain,   s.pinMain ?? '1234');
    await _setOrKeep(sp, _kPinDuress, s.pinDuress ?? '2580');
    await _setOrKeep(sp, _kPinAudio,  s.pinAudio);

    await _setOrKeep(sp, _kTgTarget,  s.tgTarget);
    await _setOrKeep(sp, _kTgToken,   s.tgBotToken);

    await _setOrKeep(sp, _kSmsTo1, s.smsTo1);
    await _setOrKeep(sp, _kSmsTo2, s.smsTo2);
    await _setOrKeep(sp, _kSmsTo3, s.smsTo3);

    await _setOrKeep(sp, _kWaTo1, s.waTo1);
    await _setOrKeep(sp, _kWaTo2, s.waTo2);
    await _setOrKeep(sp, _kWaTo3, s.waTo3);

    await _setOrKeep(sp, _kEmailTo1, s.emailTo1);
    await _setOrKeep(sp, _kEmailTo2, s.emailTo2);
    await _setOrKeep(sp, _kEmailTo3, s.emailTo3);

    await _setOrKeep(sp, _kZenviaToken,   s.zenviaToken);
    await _setOrKeep(sp, _kZenviaSmsFrom, s.zenviaSmsFrom);
    await _setOrKeep(sp, _kZenviaWaFrom,  s.zenviaWaFrom);
    await _setOrKeep(sp, _kSendGridKey,   s.sendgridKey);
    await _setOrKeep(sp, _kSendGridFrom,  s.sendgridFrom);
  }

  // Compatibilidade
  Future<void> save(AppSettings s) => saveAll(s);

  Future<void> setTestCount(int n) async {
    final sp = await SharedPreferences.getInstance();
    await sp.setInt(_kTestCount, n.clamp(0, 2));
  }
}
