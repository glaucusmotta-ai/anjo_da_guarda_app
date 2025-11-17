// lib/screens/settings_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/settings_store.dart';
import '../services/native_sos.dart'; // usamos p/ "Testar envios"

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _form = GlobalKey<FormState>();

  // Cliente
  final _userName  = TextEditingController();
  final _userPhone = TextEditingController(); // E.164
  final _userEmail = TextEditingController();

  // PINs
  final _pinMain   = TextEditingController();
  final _pinDuress = TextEditingController();
  final _pinAudio  = TextEditingController(); // PIN do áudio (futuro)
  bool _showPinMain = false;
  bool _showPinDuress = false;
  bool _showPinAudio = false;

  // Preferências
  bool _pinSecondLayerEnabled = true;
  bool _qsEnabled = true; // atalho no painel rápido

  // Telegram
  final _tgTarget = TextEditingController(); // chat_id numérico OU @username/@canal/@grupo

  // SMS (3 destinatários)
  final _smsTo1 = TextEditingController();
  final _smsTo2 = TextEditingController();
  final _smsTo3 = TextEditingController();

  // WhatsApp (3 destinatários)
  final _waTo1 = TextEditingController();
  final _waTo2 = TextEditingController();
  final _waTo3 = TextEditingController();

  // E-mail (3 destinatários)
  final _emailTo1 = TextEditingController();
  final _emailTo2 = TextEditingController();
  final _emailTo3 = TextEditingController();

  int _testCount = 0; // 0..2

  // Segredos (ocultos — não exibidos)
  String _zenviaToken   = '';
  String _zenviaSmsFrom = '';
  String _zenviaWaFrom  = '';
  String _sendgridKey   = '';
  String _sendgridFrom  = '';

  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _userName.dispose(); _userPhone.dispose(); _userEmail.dispose();
    _pinMain.dispose(); _pinDuress.dispose(); _pinAudio.dispose();
    _tgTarget.dispose();
    _smsTo1.dispose(); _smsTo2.dispose(); _smsTo3.dispose();
    _waTo1.dispose(); _waTo2.dispose(); _waTo3.dispose();
    _emailTo1.dispose(); _emailTo2.dispose(); _emailTo3.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final s = await SettingsStore.instance.load();
    setState(() {
      // Cliente
      _userName.text  = s.userName ?? '';
      _userPhone.text = s.userPhone ?? '';
      _userEmail.text = s.userEmail ?? '';

      // Prefs
      _pinSecondLayerEnabled = s.pinSecondLayerEnabled;
      _qsEnabled = s.qsEnabled;
      _testCount = s.testCount;

      // PINs
      _pinMain.text   = s.pinMain ?? '1234';
      _pinDuress.text = s.pinDuress ?? '2580';
      _pinAudio.text  = s.pinAudio ?? '';

      // Telegram
      _tgTarget.text  = s.tgTarget ?? '';

      // SMS
      _smsTo1.text = s.smsTo1 ?? '';
      _smsTo2.text = s.smsTo2 ?? '';
      _smsTo3.text = s.smsTo3 ?? '';

      // WhatsApp
      _waTo1.text = s.waTo1 ?? '';
      _waTo2.text = s.waTo2 ?? '';
      _waTo3.text = s.waTo3 ?? '';

      // E-mail
      _emailTo1.text = s.emailTo1 ?? '';
      _emailTo2.text = s.emailTo2 ?? '';
      _emailTo3.text = s.emailTo3 ?? '';

      // Segredos (ocultos)
      _zenviaToken   = s.zenviaToken ?? '';
      _zenviaSmsFrom = s.zenviaSmsFrom ?? '';
      _zenviaWaFrom  = s.zenviaWaFrom ?? '';
      _sendgridKey   = s.sendgridKey ?? '';
      _sendgridFrom  = s.sendgridFrom ?? '';

      _loading = false;
    });
  }

  String _t(String s) => s.trim();

  String? _validatePin4(String? v) {
    final s = v?.trim() ?? "";
    if (s.isEmpty) return null; // opcional
    if (!RegExp(r'^\d{4}$').hasMatch(s)) return "Use 4 dígitos";
    return null;
  }

  String? _validatePhoneE164(String? v) {
    final s = v?.trim() ?? "";
    if (s.isEmpty) return null;
    if (!RegExp(r'^\+\d{10,15}$').hasMatch(s)) return "Formato +559999999999 (sem espaço)";
    return null;
  }

  String? _validateEmail(String? v) {
    final s = v?.trim() ?? "";
    if (s.isEmpty) return null;
    if (!RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(s)) return "E-mail inválido";
    return null;
  }

  String? _validateTgTarget(String? v) {
    final s = v?.trim() ?? "";
    if (s.isEmpty) return null;
    // aceita número (chat_id) ou @username/@canal/@grupo
    final ok = RegExp(r'^-?\d+$').hasMatch(s) || RegExp(r'^@[A-Za-z0-9_]{5,}$').hasMatch(s);
    if (!ok) return "Use chat_id numérico ou @canal/@grupo/@username";
    return null;
  }

  Future<void> _save() async {
    if (!(_form.currentState?.validate() ?? false)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Corrija os campos destacados')),
      );
      return;
    }

    final data = AppSettings(
      // Cliente
      userName:  _t(_userName.text),
      userPhone: _t(_userPhone.text),
      userEmail: _t(_userEmail.text),

      // Prefs
      pinSecondLayerEnabled: _pinSecondLayerEnabled,
      qsEnabled: _qsEnabled,
      testCount: _testCount,

      // PINs
      pinMain:   _t(_pinMain.text),
      pinDuress: _t(_pinDuress.text),
      pinAudio:  _t(_pinAudio.text),

      // Telegram
      tgTarget:  _t(_tgTarget.text),

      // SMS
      smsTo1: _t(_smsTo1.text),
      smsTo2: _t(_smsTo2.text),
      smsTo3: _t(_smsTo3.text),

      // WhatsApp
      waTo1: _t(_waTo1.text),
      waTo2: _t(_waTo2.text),
      waTo3: _t(_waTo3.text),

      // E-mail
      emailTo1: _t(_emailTo1.text),
      emailTo2: _t(_emailTo2.text),
      emailTo3: _t(_emailTo3.text),

      // Segredos (inalterados pela UI)
      zenviaToken:   _zenviaToken,
      zenviaSmsFrom: _zenviaSmsFrom,
      zenviaWaFrom:  _zenviaWaFrom,
      sendgridKey:   _sendgridKey,
      sendgridFrom:  _sendgridFrom,
    );

    await SettingsStore.instance.saveAll(data);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Configurações salvas')),
    );
    // vai direto para a tela da 2ª camada (PIN) e limpa o histórico
    Navigator.of(context).pushNamedAndRemoveUntil('/pin', (r) => false);
    }

  Future<void> _testSends() async {
    // reseta contador se tiver estourado
    if (_testCount >= 2) {
      _testCount = 0;
      await SettingsStore.instance.setTestCount(0);
    }

    // pega localização (necessária pro link do mapa do template)
    final ll = await NativeSos.quickLatLon();
    final lat = ll.$1, lon = ll.$2;
    if (lat == null || lon == null) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Ative a Localização para o teste (gera o link do mapa).')),
      );
      return;
    }

    // incrementa contador e persiste
    setState(() => _testCount++);
    await SettingsStore.instance.setTestCount(_testCount);

    // texto alinhado ao template (sem emojis/aspas especiais)
    final ok = await NativeSos.send("sos pessoal", lat: lat, lon: lon);

    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(ok ? 'Teste enviado (${_testCount}/2)' : 'Falha no envio')),
    );
  }


  void _showHowToTileDialog() {
    showDialog<void>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: const Color(0xFF111216),
        title: const Text('Como ativar o atalho SOS', style: TextStyle(color: Colors.white)),
        content: const Text(
          '1) Deslize duas vezes para baixo na barra de status.\n'
          '2) Toque em “Editar” ou no lápis.\n'
          '3) Arraste o azulejo “SOS – Anjo da Guarda” para a área ativa.\n'
          '4) Salve. Opcional: habilite na tela de bloqueio nas configurações rápidas do sistema.',
          style: TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Ok'),
          ),
        ],
      ),
    );
  }

  InputDecoration _dec({
    required String label,
    String? hint,
    IconData? icon,
    Widget? suffix,
  }) {
    return InputDecoration(
      labelText: label,
      hintText: hint,
      prefixIcon: icon != null ? Icon(icon) : null,
      suffixIcon: suffix,
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
      isDense: true,
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
    );
  }

  Widget _card(String title, IconData icon, List<Widget> children, {String? subtitle}) {
    return Card(
      color: const Color(0xFF111216),
      elevation: 2,
      margin: const EdgeInsets.symmetric(vertical: 10),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(icon, size: 18, color: Colors.white70),
              const SizedBox(width: 8),
              Text(
                title,
                style: const TextStyle(
                  color: Colors.white70,
                  fontWeight: FontWeight.w700,
                  letterSpacing: .3,
                ),
              ),
            ]),
            if (subtitle != null) ...[
              const SizedBox(height: 6),
              Text(subtitle, style: const TextStyle(color: Colors.white54, fontSize: 12)),
            ],
            const SizedBox(height: 10),
            ...children.map((w) => Padding(padding: const EdgeInsets.only(bottom: 10), child: w)),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context).copyWith(
      scaffoldBackgroundColor: Colors.black,
      inputDecorationTheme: const InputDecorationTheme(
        labelStyle: TextStyle(color: Colors.white70),
        hintStyle: TextStyle(color: Colors.white38),
      ),
      textTheme: Theme.of(context).textTheme.apply(bodyColor: Colors.white, displayColor: Colors.white),
    );

    final testsLeft = 2 - _testCount;

    return Theme(
      data: theme,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Configurações'),
          backgroundColor: const Color(0xFF0D0E12),
          actions: [
            IconButton(icon: const Icon(Icons.save), onPressed: _save, tooltip: 'Salvar'),
          ],
        ),
        body: _loading
            ? const Center(child: CircularProgressIndicator())
            : Form(
                key: _form,
                autovalidateMode: AutovalidateMode.onUserInteraction,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(14, 12, 14, 90),
                  children: [
                    // Preferências
                    _card('Preferências', Icons.tune, [
                      SwitchListTile(
                        value: _pinSecondLayerEnabled,
                        onChanged: (v) => setState(() => _pinSecondLayerEnabled = v),
                        title: const Text('Usar segunda camada de PIN'),
                        subtitle: const Text('Se desativar, o app abre direto sem a tela de PIN.'),
                        contentPadding: EdgeInsets.zero,
                      ),
                      SwitchListTile(
                        value: _qsEnabled,
                        onChanged: (v) => setState(() => _qsEnabled = v),
                        title: const Text('Atalho SOS no painel rápido'),
                        subtitle: const Text('Mostra o azulejo “SOS – Anjo da Guarda” nas Configurações Rápidas.'),
                        contentPadding: EdgeInsets.zero,
                      ),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: OutlinedButton.icon(
                          onPressed: _showHowToTileDialog,
                          icon: const Icon(Icons.help_outline),
                          label: const Text('Como ativar o atalho'),
                        ),
                      ),
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        title: const Text('Testar envios'),
                        subtitle: Text(
                          _testCount < 2
                              ? 'Você ainda pode fazer $testsLeft teste(s).'
                              : 'Limite de testes atingido. Use “Iniciar serviço”.',
                          style: const TextStyle(color: Colors.white54),
                        ),
                        trailing: ElevatedButton.icon(
                          onPressed: _testCount >= 2 ? null : _testSends,
                          icon: const Icon(Icons.bolt),
                          label: const Text('Testar'),
                        ),
                      ),
                    ]),

                    // Dados do cliente
                    _card('Seus dados', Icons.person, [
                      TextFormField(
                        controller: _userName,
                        textCapitalization: TextCapitalization.words,
                        decoration: _dec(label: 'Nome completo', icon: Icons.badge),
                      ),
                      TextFormField(
                        controller: _userPhone,
                        keyboardType: TextInputType.phone,
                        validator: _validatePhoneE164,
                        decoration: _dec(label: 'Telefone principal', hint: '+559999999999', icon: Icons.phone),
                      ),
                      TextFormField(
                        controller: _userEmail,
                        keyboardType: TextInputType.emailAddress,
                        validator: _validateEmail,
                        decoration: _dec(label: 'E-mail principal', icon: Icons.alternate_email),
                      ),
                    ]),

                    // PINs
                    _card(
                      'PINs',
                      Icons.lock_outline,
                      [
                        TextFormField(
                          controller: _pinMain,
                          maxLength: 4,
                          keyboardType: TextInputType.number,
                          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                          obscureText: !_showPinMain,
                          validator: _validatePin4,
                          decoration: _dec(
                            label: 'PIN principal (4 dígitos)',
                            icon: Icons.password,
                            suffix: IconButton(
                              icon: Icon(_showPinMain ? Icons.visibility_off : Icons.visibility),
                              onPressed: () => setState(() => _showPinMain = !_showPinMain),
                            ),
                          ),
                        ),
                        const Text(
                          'Use o PIN principal para acesso normal ao app.',
                          style: TextStyle(color: Colors.white54, fontSize: 12),
                        ),
                        const SizedBox(height: 6),
                        TextFormField(
                          controller: _pinDuress,
                          maxLength: 4,
                          keyboardType: TextInputType.number,
                          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                          obscureText: !_showPinDuress,
                          validator: _validatePin4,
                          decoration: _dec(
                            label: 'PIN de coação (4 dígitos)',
                            icon: Icons.warning_amber,
                            suffix: IconButton(
                              icon: Icon(_showPinDuress ? Icons.visibility_off : Icons.visibility),
                              onPressed: () => setState(() => _showPinDuress = !_showPinDuress),
                            ),
                          ),
                        ),
                      ],
                    ),

                    // PIN do Áudio (oculto/futuro)
                    _card(
                      'PIN do Áudio (opcional)',
                      Icons.mic_none,
                      [
                        TextFormField(
                          controller: _pinAudio,
                          maxLength: 4,
                          keyboardType: TextInputType.number,
                          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                          obscureText: !_showPinAudio,
                          validator: _validatePin4,
                          decoration: _dec(
                            label: 'PIN do áudio',
                            hint: '4 dígitos para desbloqueio por voz (futuro)',
                            icon: Icons.mic,
                            suffix: IconButton(
                              icon: Icon(_showPinAudio ? Icons.visibility_off : Icons.visibility),
                              onPressed: () => setState(() => _showPinAudio = !_showPinAudio),
                            ),
                          ),
                        ),
                        const Text(
                          'Reservado para modo de ativação por voz. Não interfere no PIN de coação.',
                          style: TextStyle(color: Colors.white54, fontSize: 12),
                        ),
                      ],
                    ),

                    // Telegram (chat_id OU @canal/@grupo/@username)
                    _card('Telegram', Icons.send, [
                      TextFormField(
                        controller: _tgTarget,
                        keyboardType: TextInputType.text,
                        validator: _validateTgTarget,
                        decoration: _dec(
                          label: 'Destino',
                          hint: 'chat_id numérico ou @canal/@grupo/@username',
                          icon: Icons.confirmation_number,
                        ),
                      ),
                      const Text(
                        'Observação: bots NÃO iniciam conversa por @username. '
                        'Para pessoa física, inicie chat com o bot (com /start) e use o chat_id numérico.',
                        style: TextStyle(color: Colors.white54, fontSize: 12),
                      ),
                    ]),

                    // SMS
                    _card('SMS', Icons.sms_outlined, [
                      TextFormField(
                        controller: _smsTo1,
                        keyboardType: TextInputType.phone,
                        validator: _validatePhoneE164,
                        decoration: _dec(label: 'Destinatário 1', hint: '+559999999999', icon: Icons.phone_iphone),
                      ),
                      TextFormField(
                        controller: _smsTo2,
                        keyboardType: TextInputType.phone,
                        validator: _validatePhoneE164,
                        decoration: _dec(label: 'Destinatário 2 (opcional)', hint: '+559999999999', icon: Icons.phone_iphone),
                      ),
                      TextFormField(
                        controller: _smsTo3,
                        keyboardType: TextInputType.phone,
                        validator: _validatePhoneE164,
                        decoration: _dec(label: 'Destinatário 3 (opcional)', hint: '+559999999999', icon: Icons.phone_iphone),
                      ),
                    ],
                    subtitle: 'Preencha no formato +559999999999 (sem espaços).'),

                    // WhatsApp
                    _card('WhatsApp', Icons.chat, [
                      TextFormField(
                        controller: _waTo1,
                        keyboardType: TextInputType.phone,
                        validator: _validatePhoneE164,
                        decoration: _dec(label: 'Destinatário 1', hint: '+559999999999', icon: Icons.chat),
                      ),
                      TextFormField(
                        controller: _waTo2,
                        keyboardType: TextInputType.phone,
                        validator: _validatePhoneE164,
                        decoration: _dec(label: 'Destinatário 2 (opcional)', hint: '+559999999999', icon: Icons.chat),
                      ),
                      TextFormField(
                        controller: _waTo3,
                        keyboardType: TextInputType.phone,
                        validator: _validatePhoneE164,
                        decoration: _dec(label: 'Destinatário 3 (opcional)', hint: '+559999999999', icon: Icons.chat),
                      ),
                    ],
                    subtitle: 'Preencha no formato +559999999999 (sem espaços).'),

                    // E-mail
                    _card('E-mail', Icons.email_outlined, [
                      TextFormField(
                        controller: _emailTo1,
                        keyboardType: TextInputType.emailAddress,
                        validator: _validateEmail,
                        decoration: _dec(label: 'Destinatário 1', hint: 'ex: contato@dominio.com', icon: Icons.person),
                      ),
                      TextFormField(
                        controller: _emailTo2,
                        keyboardType: TextInputType.emailAddress,
                        validator: _validateEmail,
                        decoration: _dec(label: 'Destinatário 2 (opcional)', hint: 'ex: contato2@dominio.com', icon: Icons.person),
                      ),
                      TextFormField(
                        controller: _emailTo3,
                        keyboardType: TextInputType.emailAddress,
                        validator: _validateEmail,
                        decoration: _dec(label: 'Destinatário 3 (opcional)', hint: 'ex: contato3@dominio.com', icon: Icons.person),
                      ),
                      const Text(
                        'Os parâmetros do provedor de e-mail são gerenciados pelo Anjo da Guarda.',
                        style: TextStyle(color: Colors.white54, fontSize: 12),
                      ),
                    ]),
                  ],
                ),
              ),
        floatingActionButton: _loading
            ? null
            : FloatingActionButton.extended(
                onPressed: _save,
                icon: const Icon(Icons.save),
                label: const Text('Salvar'),
              ),
      ),
    );
  }
}
