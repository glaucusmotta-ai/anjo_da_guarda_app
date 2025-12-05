// lib/screens/settings_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart'; // kDebugMode
import 'package:shared_preferences/shared_preferences.dart';

import '../services/settings_store.dart';
import '../services/native_sos.dart'; // quickLatLon (se quisermos usar depois)
import '../widgets/user_profile_section.dart';
import '../theme/anjo_theme.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _form = GlobalKey<FormState>();
  final _userProfileKey = GlobalKey<UserProfileSectionState>();

  // Cliente
  final _userName = TextEditingController();
  final _userPhone = TextEditingController(); // E.164
  final _userEmail = TextEditingController();

  // PINs
  final _pinMain = TextEditingController();
  final _pinDuress = TextEditingController();
  final _pinAudio = TextEditingController(); // reservado (futuro / opcional)
  bool _showPinMain = false;
  bool _showPinDuress = false;
  bool _showPinAudio = false; // compatibilidade futura

  // Senhas de áudio (coação em 2 etapas)
  final _audioToken1 = TextEditingController(); // ex: DEUS / FILHA / SOCORRO
  final _audioToken2 = TextEditingController(); // ex: AJUDA / TE AMO / ANJO

  // Preferências
  bool _pinSecondLayerEnabled = true;
  bool _qsEnabled = true; // atalho no painel rápido
  bool _audioEnabled = true; // liga/desliga disparo por voz

  // Telegram
  final _tgTarget =
      TextEditingController(); // chat_id numérico OU @username/@canal/@grupo

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
  String _zenviaToken = '';
  String _zenviaSmsFrom = '';
  String _zenviaWaFrom = '';
  String _sendgridKey = '';
  String _sendgridFrom = '';

  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _userName.dispose();
    _userPhone.dispose();
    _userEmail.dispose();
    _pinMain.dispose();
    _pinDuress.dispose();
    _pinAudio.dispose();
    _audioToken1.dispose();
    _audioToken2.dispose();
    _tgTarget.dispose();
    _smsTo1.dispose();
    _smsTo2.dispose();
    _smsTo3.dispose();
    _waTo1.dispose();
    _waTo2.dispose();
    _waTo3.dispose();
    _emailTo1.dispose();
    _emailTo2.dispose();
    _emailTo3.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final s = await SettingsStore.instance.load();

    // carrega senhas de áudio personalizadas + toggle de áudio (se houver)
    String audio1 = '';
    String audio2 = '';
    bool audioEnabled = true;
    try {
      final prefs = await SharedPreferences.getInstance();
      audio1 = prefs.getString('audioToken1') ?? '';
      audio2 = prefs.getString('audioToken2') ?? '';
      audioEnabled = prefs.getBool('audioEnabled') ?? true;
    } catch (_) {}

    setState(() {
      // Cliente
      _userName.text = s.userName ?? '';
      _userPhone.text = s.userPhone ?? '';
      _userEmail.text = s.userEmail ?? '';

      // Prefs
      _pinSecondLayerEnabled = s.pinSecondLayerEnabled;
      _qsEnabled = s.qsEnabled;
      _testCount = s.testCount;

      // PINs
      _pinMain.text = s.pinMain ?? '1234';
      _pinDuress.text = s.pinDuress ?? '2580';
      _pinAudio.text = s.pinAudio ?? '';

      // Telegram
      _tgTarget.text = s.tgTarget ?? '';

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
      _zenviaToken = s.zenviaToken ?? '';
      _zenviaSmsFrom = s.zenviaSmsFrom ?? '';
      _zenviaWaFrom = s.zenviaWaFrom ?? '';
      _sendgridKey = s.sendgridKey ?? '';
      _sendgridFrom = s.sendgridFrom ?? '';

      // Senhas de áudio coação (2 etapas)
      _audioToken1.text = audio1;
      _audioToken2.text = audio2;

      // Toggle de áudio
      _audioEnabled = audioEnabled;

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
    if (!RegExp(r'^\+\d{10,15}$').hasMatch(s)) {
      return "Formato +559999999999 (sem espaço)";
    }
    return null;
  }

  String? _validateEmail(String? v) {
    final s = v?.trim() ?? "";
    if (s.isEmpty) return null;
    if (!RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(s)) {
      return "E-mail inválido";
    }
    return null;
  }

  String? _validateTgTarget(String? v) {
    final s = v?.trim() ?? "";
    if (s.isEmpty) return null;
    // aceita número (chat_id) ou @username/@canal/@grupo
    final ok = RegExp(r'^-?\d+$').hasMatch(s) ||
        RegExp(r'^@[A-Za-z0-9_]{5,}$').hasMatch(s);
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

    // 🔹 Salva também a região de métricas (CEP, cidade, UF)
    await _userProfileKey.currentState?.saveRegion();

    final data = AppSettings(
      // Cliente
      userName: _t(_userName.text),
      userPhone: _t(_userPhone.text),
      userEmail: _t(_userEmail.text),

      // Prefs
      pinSecondLayerEnabled: _pinSecondLayerEnabled,
      qsEnabled: _qsEnabled,
      testCount: _testCount,

      // PINs
      pinMain: _t(_pinMain.text),
      pinDuress: _t(_pinDuress.text),
      pinAudio: _t(_pinAudio.text),

      // Telegram
      tgTarget: _t(_tgTarget.text),

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
      zenviaToken: _zenviaToken,
      zenviaSmsFrom: _zenviaSmsFrom,
      zenviaWaFrom: _zenviaWaFrom,
      sendgridKey: _sendgridKey,
      sendgridFrom: _sendgridFrom,
    );

    await SettingsStore.instance.saveAll(data);

    // 🔹 Grava Nome, tokens de áudio, toggle e TODOS os destinos nas SharedPreferences
    try {
      final prefs = await SharedPreferences.getInstance();

      // Nome (usado nos textos do SOS)
      await prefs.setString('nomeCompleto', _t(_userName.text));

      // Senhas de áudio + toggle
      await prefs.setString('audioToken1', _t(_audioToken1.text));
      await prefs.setString('audioToken2', _t(_audioToken2.text));
      await prefs.setBool('audioEnabled', _audioEnabled);

      // Telegram – destino
      await prefs.setString('tgTarget', _t(_tgTarget.text));

      // SMS – destinos (+E.164)
      await prefs.setString('smsTo1', _t(_smsTo1.text));
      await prefs.setString('smsTo2', _t(_smsTo2.text));
      await prefs.setString('smsTo3', _t(_smsTo3.text));

      // WhatsApp – destinos
      await prefs.setString('waTo1', _t(_waTo1.text));
      await prefs.setString('waTo2', _t(_waTo2.text));
      await prefs.setString('waTo3', _t(_waTo3.text));

      // E-mail – destinos
      await prefs.setString('emailTo1', _t(_emailTo1.text));
      await prefs.setString('emailTo2', _t(_emailTo2.text));
      await prefs.setString('emailTo3', _t(_emailTo3.text));
    } catch (_) {
      // se der erro aqui, não quebra o fluxo principal
    }

    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Configurações salvas')),
    );

    // volta para a tela da 2ª camada (PIN) e limpa o histórico
    Navigator.of(context).pushNamedAndRemoveUntil('/pin', (r) => false);
  }

  // ----- Senhas de áudio: editar token pessoal -----
  Future<void> _editAudioToken(int which) async {
    final controller = which == 1 ? _audioToken1 : _audioToken2;
    final label = which == 1 ? 'Senha 1 (armar)' : 'Senha 2 (disparar)';

    final temp = TextEditingController(text: controller.text);

    final result = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: const Color(0xFF111216),
        title: Text(
          label,
          style: const TextStyle(color: Colors.white),
        ),
        content: TextField(
          controller: temp,
          autofocus: true,
          style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(
            labelText: 'Palavra ou frase da senha',
            labelStyle: TextStyle(color: Colors.white70),
            enabledBorder: UnderlineInputBorder(
              borderSide: BorderSide(color: Colors.white30),
            ),
            focusedBorder: UnderlineInputBorder(
              borderSide: BorderSide(color: Colors.white),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('OK'),
          ),
        ],
      ),
    );

    if (result == true) {
      setState(() {
        controller.text = temp.text.trim();
      });
    }
  }

  // ----- Senhas de áudio: revelar token (pede PIN principal antes) -----
  Future<void> _revealAudioToken(int which) async {
    final pin = _t(_pinMain.text);
    if (pin.length != 4) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Defina primeiro o PIN principal nas Configurações.'),
        ),
      );
      return;
    }

    final pinController = TextEditingController();

    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: const Color(0xFF111216),
        title: const Text(
          'Confirme seu PIN',
          style: TextStyle(color: Colors.white),
        ),
        content: TextField(
          controller: pinController,
          keyboardType: TextInputType.number,
          obscureText: true,
          maxLength: 4,
          style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(
            counterText: '',
            labelText: 'PIN principal (4 dígitos)',
            labelStyle: TextStyle(color: Colors.white70),
            enabledBorder: UnderlineInputBorder(
              borderSide: BorderSide(color: Colors.white30),
            ),
            focusedBorder: UnderlineInputBorder(
              borderSide: BorderSide(color: Colors.white),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('OK'),
          ),
        ],
      ),
    );

    if (ok != true) return;

    if (_t(pinController.text) != pin) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('PIN principal incorreto')),
      );
      return;
    }

    final value = _t(which == 1 ? _audioToken1.text : _audioToken2.text);

    if (value.isEmpty) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Senha $which ainda não configurada.'),
        ),
      );
      return;
    }

    await showDialog<void>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: const Color(0xFF111216),
        title: Text(
          'Senha $which de áudio',
          style: const TextStyle(color: Colors.white),
        ),
        content: Text(
          value,
          style: const TextStyle(color: Colors.white),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Fechar'),
          ),
        ],
      ),
    );
  }

  Future<void> _testSends() async {
    //  Já usou os 2 testes? Só avisa e sai.
    if (_testCount >= 2) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Você já usou os 2 testes iniciais. '
            'Use o botão "Iniciar serviço" para o uso normal.',
          ),
        ),
      );
      return;
    }

    // incrementa contador de testes (créditos) e persiste
    setState(() => _testCount++);
    await SettingsStore.instance.setTestCount(_testCount);

    // marca flag para uso futuro na Home (se necessário)
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool('pendingTestFromSettings', true);
    } catch (_) {}

    if (!mounted) return;

    // vai para a Home; disparo real será pelo botão "Iniciar serviço"
    Navigator.of(context).pushNamed('/home');

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Teste ${_testCount}/2 preparado. '
          'Na tela inicial, toque em "Iniciar serviço" para disparar o teste.',
        ),
      ),
    );
  }

  void _showHowToTileDialog() {
    showDialog<void>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: const Color(0xFF111216),
        title: const Text(
          'Como ativar o atalho SOS',
          style: TextStyle(color: Colors.white),
        ),
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
    Color? iconColor,
    Widget? suffix,
  }) {
    return InputDecoration(
      labelText: label,
      hintText: hint,
      prefixIcon: icon != null
          ? Icon(icon, color: iconColor ?? Colors.white70)
          : null,
      suffixIcon: suffix,
      filled: true,
      fillColor: Colors.black.withOpacity(0.35),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: Colors.white24),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide(color: AnjoTheme.neonBlue, width: 1.5),
      ),
      isDense: true,
      contentPadding: const EdgeInsets.symmetric(
        horizontal: 12,
        vertical: 12,
      ),
    );
  }

  Widget _card(
    String title,
    IconData icon,
    List<Widget> children, {
    String? subtitle,
  }) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 10),
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      decoration: BoxDecoration(
        color: AnjoTheme.cardBlue.withOpacity(0.85),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: AnjoTheme.neonBlue.withOpacity(0.6),
          width: 1,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.6),
            blurRadius: 16,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(icon, size: 18, color: Colors.white70),
            const SizedBox(width: 8),
            Text(
              title,
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w700,
                letterSpacing: .3,
              ),
            ),
          ]),
          if (subtitle != null) ...[
            const SizedBox(height: 6),
            Text(
              subtitle,
              style: const TextStyle(color: Colors.white70, fontSize: 12),
            ),
          ],
          const SizedBox(height: 10),
          ...children
              .map(
                (w) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: w,
                ),
              )
              .toList(),
        ],
      ),
    );
  }

  // Pequeno "waveform" de risquinhos ocupando todo o campo
  Widget _audioWave(bool active) {
    final color = active ? Colors.white70 : Colors.white24;
    return Row(
      children: List.generate(28, (i) {
        final h = 6.0 + (i % 4) * 3.0;
        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: 1),
          child: Container(
            width: 2,
            height: h,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(1),
            ),
          ),
        );
      }),
    );
  }

  // Tile visual de áudio: faixa com risquinhos + mic + olhinho
  Widget _audioTile({
    required String description,
    required String value,
    required VoidCallback onEdit,
    required VoidCallback onReveal,
  }) {
    final hasValue = value.isNotEmpty;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          decoration: BoxDecoration(
            color: const Color(0xFF1C1D22),
            borderRadius: BorderRadius.circular(12),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          child: Row(
            children: [
              const Icon(Icons.play_arrow, size: 18, color: Colors.white70),
              const SizedBox(width: 8),
              Expanded(
                child: SizedBox(
                  height: 22,
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: _audioWave(hasValue),
                  ),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.mic, size: 20),
                tooltip: 'Definir / alterar senha',
                onPressed: onEdit,
              ),
              IconButton(
                icon: Icon(
                  Icons.visibility,
                  size: 20,
                  color: Colors.grey.shade300,
                ),
                tooltip: 'Ver senha (pede PIN)',
                onPressed: hasValue ? onReveal : null,
              ),
            ],
          ),
        ),
        const SizedBox(height: 4),
        Text(
          description,
          style: const TextStyle(
            color: Colors.white54,
            fontSize: 11,
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final baseTheme = Theme.of(context);
    final theme = baseTheme.copyWith(
      scaffoldBackgroundColor: Colors.transparent,
      textTheme: baseTheme.textTheme.apply(
        bodyColor: Colors.white,
        displayColor: Colors.white,
      ),
      inputDecorationTheme: const InputDecorationTheme(
        labelStyle: TextStyle(color: Colors.white70),
        hintStyle: TextStyle(color: Colors.white38),
      ),
    );

    // garante que não fica negativo se vier algo zoado do banco
    final testsLeft = (_testCount >= 2) ? 0 : (2 - _testCount);

    return Theme(
      data: theme,
      child: Scaffold(
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          iconTheme: const IconThemeData(color: Colors.white),
          title: const Text(
            'Configurações',
            style: TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
        body: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              colors: [Color(0xFF050A1A), Color(0xFF0A1430)],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
          ),
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : Form(
                  key: _form,
                  autovalidateMode: AutovalidateMode.onUserInteraction,
                  child: ListView(
                    padding: const EdgeInsets.fromLTRB(14, 12, 14, 90),
                    children: [
                      // 🔹 Informações adicionais / região para métricas
                      _card(
                        'Informações adicionais',
                        Icons.location_on_outlined,
                        [
                          UserProfileSection(key: _userProfileKey),
                        ],
                        subtitle:
                            'CEP, cidade, bairro e dados usados para métricas '
                            'e relatórios do Anjo da Guarda.',
                      ),

                      // Dados do cliente
                      _card('Seus dados', Icons.person, [
                        TextFormField(
                          controller: _userName,
                          textCapitalization: TextCapitalization.words,
                          style: const TextStyle(color: Colors.white),
                          decoration: _dec(
                            label: 'Nome completo',
                            icon: Icons.badge,
                          ),
                        ),
                        TextFormField(
                          controller: _userPhone,
                          keyboardType: TextInputType.phone,
                          validator: _validatePhoneE164,
                          style: const TextStyle(color: Colors.white),
                          decoration: _dec(
                            label: 'Telefone principal',
                            hint: '+559999999999',
                            icon: Icons.phone,
                          ),
                        ),
                        TextFormField(
                          controller: _userEmail,
                          keyboardType: TextInputType.emailAddress,
                          validator: _validateEmail,
                          style: const TextStyle(color: Colors.white),
                          decoration: _dec(
                            label: 'E-mail principal',
                            icon: Icons.alternate_email,
                          ),
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
                            inputFormatters: [
                              FilteringTextInputFormatter.digitsOnly
                            ],
                            obscureText: !_showPinMain,
                            validator: _validatePin4,
                            style: const TextStyle(color: Colors.white),
                            decoration: _dec(
                              label: 'PIN principal (4 dígitos)',
                              icon: Icons.password,
                              suffix: IconButton(
                                icon: Icon(
                                  _showPinMain
                                      ? Icons.visibility_off
                                      : Icons.visibility,
                                  color: Colors.grey.shade300,
                                ),
                                onPressed: () => setState(
                                  () => _showPinMain = !_showPinMain,
                                ),
                              ),
                            ),
                          ),
                          const Text(
                            'Use o PIN principal para acesso normal ao app.',
                            style:
                                TextStyle(color: Colors.white54, fontSize: 12),
                          ),
                          const SizedBox(height: 6),
                          TextFormField(
                            controller: _pinDuress,
                            maxLength: 4,
                            keyboardType: TextInputType.number,
                            inputFormatters: [
                              FilteringTextInputFormatter.digitsOnly
                            ],
                            obscureText: !_showPinDuress,
                            validator: _validatePin4,
                            style: const TextStyle(color: Colors.white),
                            decoration: _dec(
                              label: 'PIN de coação (4 dígitos)',
                              icon: Icons.warning_amber,
                              suffix: IconButton(
                                icon: Icon(
                                  _showPinDuress
                                      ? Icons.visibility_off
                                      : Icons.visibility,
                                  color: Colors.grey.shade300,
                                ),
                                onPressed: () => setState(
                                  () => _showPinDuress = !_showPinDuress,
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),

                      // Senhas de áudio (coação em 2 etapas)
                      _card(
                        'Senhas de Áudio (Coação em 2 etapas)',
                        Icons.hearing,
                        [
                          _audioTile(
                            description:
                                'Senha 1 (armar) - Usada para armar o SOS por voz',
                            value: _audioToken1.text,
                            onEdit: () => _editAudioToken(1),
                            onReveal: () => _revealAudioToken(1),
                          ),
                          _audioTile(
                            description:
                                'Senha 2 (disparar) - Dispara o SOS se dita logo após a senha 1',
                            value: _audioToken2.text,
                            onEdit: () => _editAudioToken(2),
                            onReveal: () => _revealAudioToken(2),
                          ),
                          const Text(
                            'Funcionamento: ao reconhecer a Senha 1 o sistema fica armado por ~2 segundos. '
                            'Se dentro dessa janela reconhecer a Senha 2, dispara o SOS. '
                            'Se falar só a primeira e não completar, nada é enviado.',
                            style:
                                TextStyle(color: Colors.white54, fontSize: 12),
                          ),
                        ],
                      ),

                      // Telegram
                      _card('Telegram', Icons.send, [
                        TextFormField(
                          controller: _tgTarget,
                          keyboardType: TextInputType.text,
                          validator: _validateTgTarget,
                          style: const TextStyle(color: Colors.white),
                          decoration: _dec(
                            label: 'Destino',
                            hint: 'chat_id numérico ou @canal/@grupo/@username',
                            icon: Icons.confirmation_number,
                          ),
                        ),
                        const Text(
                          'Observação: bots NÃO iniciam conversa por @username. '
                          'Para pessoa física, inicie chat com o bot (com /start) e use o chat_id numérico.',
                          style:
                              TextStyle(color: Colors.white54, fontSize: 12),
                        ),
                      ]),

                      // SMS
                      _card(
                        'SMS',
                        Icons.sms_outlined,
                        [
                          TextFormField(
                            controller: _smsTo1,
                            keyboardType: TextInputType.phone,
                            validator: _validatePhoneE164,
                            style: const TextStyle(color: Colors.white),
                            decoration: _dec(
                              label: 'Destinatário 1',
                              hint: '+559999999999',
                              icon: Icons.phone_iphone,
                            ),
                          ),
                          TextFormField(
                            controller: _smsTo2,
                            keyboardType: TextInputType.phone,
                            validator: _validatePhoneE164,
                            style: const TextStyle(color: Colors.white),
                            decoration: _dec(
                              label: 'Destinatário 2 (opcional)',
                              hint: '+559999999999',
                              icon: Icons.phone_iphone,
                            ),
                          ),
                          TextFormField(
                            controller: _smsTo3,
                            keyboardType: TextInputType.phone,
                            validator: _validatePhoneE164,
                            style: const TextStyle(color: Colors.white),
                            decoration: _dec(
                              label: 'Destinatário 3 (opcional)',
                              hint: '+559999999999',
                              icon: Icons.phone_iphone,
                            ),
                          ),
                        ],
                        subtitle:
                            'Preencha no formato +559999999999 (sem espaços).',
                      ),

                      // WhatsApp
                      _card(
                        'WhatsApp',
                        Icons.chat,
                        [
                          TextFormField(
                            controller: _waTo1,
                            keyboardType: TextInputType.phone,
                            validator: _validatePhoneE164,
                            style: const TextStyle(color: Colors.white),
                            decoration: _dec(
                              label: 'Destinatário 1',
                              hint: '+559999999999',
                              icon: Icons.chat,
                            ),
                          ),
                          TextFormField(
                            controller: _waTo2,
                            keyboardType: TextInputType.phone,
                            validator: _validatePhoneE164,
                            style: const TextStyle(color: Colors.white),
                            decoration: _dec(
                              label: 'Destinatário 2 (opcional)',
                              hint: '+559999999999',
                              icon: Icons.chat,
                            ),
                          ),
                          TextFormField(
                            controller: _waTo3,
                            keyboardType: TextInputType.phone,
                            validator: _validatePhoneE164,
                            style: const TextStyle(color: Colors.white),
                            decoration: _dec(
                              label: 'Destinatário 3 (opcional)',
                              hint: '+559999999999',
                              icon: Icons.chat,
                            ),
                          ),
                        ],
                        subtitle:
                            'Preencha no formato +559999999999 (sem espaços).',
                      ),

                      // E-mail
                      _card('E-mail', Icons.email_outlined, [
                        TextFormField(
                          controller: _emailTo1,
                          keyboardType: TextInputType.emailAddress,
                          validator: _validateEmail,
                          style: const TextStyle(color: Colors.white),
                          decoration: _dec(
                            label: 'Destinatário 1',
                            hint: 'ex: contato@dominio.com',
                            icon: Icons.person,
                          ),
                        ),
                        TextFormField(
                          controller: _emailTo2,
                          keyboardType: TextInputType.emailAddress,
                          validator: _validateEmail,
                          style: const TextStyle(color: Colors.white),
                          decoration: _dec(
                            label: 'Destinatário 2 (opcional)',
                            hint: 'ex: contato2@dominio.com',
                            icon: Icons.person,
                          ),
                        ),
                        TextFormField(
                          controller: _emailTo3,
                          keyboardType: TextInputType.emailAddress,
                          validator: _validateEmail,
                          style: const TextStyle(color: Colors.white),
                          decoration: _dec(
                            label: 'Destinatário 3 (opcional)',
                            hint: 'ex: contato3@dominio.com',
                            icon: Icons.person,
                          ),
                        ),
                        const Text(
                          'Os parâmetros do provedor de e-mail são gerenciados pelo Anjo da Guarda.',
                          style:
                              TextStyle(color: Colors.white54, fontSize: 12),
                        ),
                      ]),

                      // Preferências (apenas toggles)
                      _card('Preferências', Icons.tune, [
                        SwitchListTile(
                          value: _pinSecondLayerEnabled,
                          onChanged: (v) =>
                              setState(() => _pinSecondLayerEnabled = v),
                          title: const Text('Usar segunda camada de PIN'),
                          subtitle: const Text(
                            'Se desativar, o app abre direto sem a tela de PIN.',
                          ),
                          contentPadding: EdgeInsets.zero,
                          activeColor: AnjoTheme.neonGreen,
                        ),
                        // toggle para disparo por voz
                        SwitchListTile(
                          value: _audioEnabled,
                          onChanged: (v) =>
                              setState(() => _audioEnabled = v),
                          title: const Text('Ativar disparo por voz (beta)'),
                          subtitle: const Text(
                            'Se desativar, o SOS por áudio fica desligado; use apenas o PIN de coação.',
                          ),
                          contentPadding: EdgeInsets.zero,
                          activeColor: AnjoTheme.neonGreen,
                        ),
                        SwitchListTile(
                          value: _qsEnabled,
                          onChanged: (v) => setState(() => _qsEnabled = v),
                          title: const Text('Atalho SOS no painel rápido'),
                          subtitle: const Text(
                            'Mostra o azulejo “SOS – Anjo da Guarda” nas Configurações Rápidas.',
                          ),
                          contentPadding: EdgeInsets.zero,
                          activeColor: AnjoTheme.neonGreen,
                        ),
                        Align(
                          alignment: Alignment.centerLeft,
                          child: OutlinedButton.icon(
                            onPressed: _showHowToTileDialog,
                            icon: const Icon(Icons.help_outline),
                            label: const Text('Como ativar o atalho'),
                          ),
                        ),
                      ]),

                      // Card de salvar configurações (botão fixo)
                      _card('Salvar configurações', Icons.save_outlined, [
                        const Text(
                          'Depois de ajustar os dados e preferências, toque em '
                          'SALVAR para aplicar tudo e voltar para a tela de PIN.',
                          style: TextStyle(
                            color: Colors.white70,
                            fontSize: 12,
                          ),
                        ),
                        Align(
                          alignment: Alignment.centerRight,
                          child: ElevatedButton.icon(
                            onPressed: _save,
                            icon: const Icon(Icons.save),
                            label: const Text('Salvar'),
                          ),
                        ),
                      ]),

                      // Card de testes (separado das preferências)
                      _card('Testes (limite 2)', Icons.bolt, [
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('Testar envios'),
                          subtitle: Text(
                            _testCount < 2
                                ? 'Você ainda pode usar $testsLeft teste(s). '
                                    'Ao tocar em TESTAR, vamos abrir a tela inicial; '
                                    'o disparo acontece pelo botão "Iniciar serviço".'
                                : 'Limite de 2 testes atingido. '
                                    'Use “Iniciar serviço” para testar em produção.',
                            style: const TextStyle(color: Colors.white54),
                          ),
                          trailing: ElevatedButton.icon(
                            onPressed: _testCount >= 2 ? null : _testSends,
                            icon: const Icon(Icons.play_arrow),
                            label: const Text('Testar'),
                          ),
                        ),
                        const Text(
                          'Os testes usam o mesmo texto padrão do alerta real, '
                          'apenas marcados como teste nos controles internos.',
                          style: TextStyle(
                            color: Colors.white54,
                            fontSize: 11,
                          ),
                        ),

                        // 🔹 Botão DEV-ONLY para resetar contador de testes (só aparece em debug)
                        if (kDebugMode)
                          Align(
                            alignment: Alignment.centerRight,
                            child: TextButton.icon(
                              onPressed: () async {
                                setState(() => _testCount = 0);
                                await SettingsStore.instance.setTestCount(0);
                                if (!mounted) return;
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text(
                                      '[DEV] Contador de testes reiniciado.',
                                    ),
                                  ),
                                );
                              },
                              icon: const Icon(
                                Icons.restart_alt,
                                size: 18,
                                color: Colors.white70,
                              ),
                              label: const Text(
                                '[DEV] Resetar testes',
                                style: TextStyle(color: Colors.white70),
                              ),
                            ),
                          ),
                      ]),
                    ],
                  ),
                ),
        ),
        // botão flutuante removido: agora o SALVAR está em um card próprio
        floatingActionButton: null,
      ),
    );
  }
}
