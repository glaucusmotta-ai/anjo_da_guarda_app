import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/settings_store.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _pinMain = TextEditingController();
  final _pinDuress = TextEditingController();

  final _tgToken = TextEditingController();
  final _tgChatId = TextEditingController();

  final _zenToken = TextEditingController();
  final _zenSmsFrom = TextEditingController();
  final _sosSmsTo = TextEditingController();
  final _zenWaFrom = TextEditingController();
  final _sosWaTo = TextEditingController();

  final _sgKey = TextEditingController();
  final _sgFrom = TextEditingController();
  final _sosEmailTo = TextEditingController();

  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _pinMain.dispose();
    _pinDuress.dispose();
    _tgToken.dispose();
    _tgChatId.dispose();
    _zenToken.dispose();
    _zenSmsFrom.dispose();
    _sosSmsTo.dispose();
    _zenWaFrom.dispose();
    _sosWaTo.dispose();
    _sgKey.dispose();
    _sgFrom.dispose();
    _sosEmailTo.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final s = await SettingsStore.instance.load();
    setState(() {
      _pinMain.text = s.pinMain ?? "";
      _pinDuress.text = s.pinDuress ?? "";
      _tgToken.text = s.tgBotToken ?? "";
      _tgChatId.text = s.tgChatId ?? "";
      _zenToken.text = s.zenviaToken ?? "";
      _zenSmsFrom.text = s.zenviaSmsFrom ?? "";
      _sosSmsTo.text = s.sosSmsTo ?? "";
      _zenWaFrom.text = s.zenviaWaFrom ?? "";
      _sosWaTo.text = s.sosWaTo ?? "";
      _sgKey.text = s.sendgridKey ?? "";
      _sgFrom.text = s.sendgridFrom ?? "";
      _sosEmailTo.text = s.sosEmailTo ?? "";
      _loading = false;
    });
  }

  String _t(String s) => s.trim();

  Future<void> _save() async {
    final pinOk = (String v) => v.isEmpty || RegExp(r'^\d{4}$').hasMatch(v);
    if (!pinOk(_pinMain.text) || !pinOk(_pinDuress.text)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('PINs devem ter 4 dígitos (ou deixe em branco).')),
      );
      return;
    }

    final data = AppSettings(
      pinMain: _t(_pinMain.text),
      pinDuress: _t(_pinDuress.text),
      tgBotToken: _t(_tgToken.text),
      tgChatId: _t(_tgChatId.text),
      zenviaToken: _t(_zenToken.text),
      zenviaSmsFrom: _t(_zenSmsFrom.text),
      sosSmsTo: _t(_sosSmsTo.text),
      zenviaWaFrom: _t(_zenWaFrom.text),
      sosWaTo: _t(_sosWaTo.text),
      sendgridKey: _t(_sgKey.text),
      sendgridFrom: _t(_sgFrom.text),
      sosEmailTo: _t(_sosEmailTo.text),
    );

    await SettingsStore.instance.saveAll(data);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Configurações salvas.')),
    );
    Navigator.pop(context);
  }

  Widget _section(String title) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 18, 4, 8),
        child: Text(title,
            style: const TextStyle(
              fontWeight: FontWeight.w700,
              color: Colors.white70,
              fontSize: 13,
              letterSpacing: .6,
            )),
      );

  InputDecoration _dec(String label, {String? hint}) => InputDecoration(
        labelText: label,
        hintText: hint,
        border: const OutlineInputBorder(),
        isDense: true,
        helperText: hint == null ? ' ' : null,
      );

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: const Text('Configurações'),
        actions: [
          IconButton(icon: const Icon(Icons.save), onPressed: _save, tooltip: 'Salvar'),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(14),
              child: Column(
                children: [
                  _section('PINs'),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _pinMain,
                          maxLength: 4,
                          keyboardType: TextInputType.number,
                          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                          obscureText: true,
                          decoration: _dec('PIN principal', hint: '4 dígitos'),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: TextField(
                          controller: _pinDuress,
                          maxLength: 4,
                          keyboardType: TextInputType.number,
                          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                          obscureText: true,
                          decoration: _dec('PIN de coação', hint: '4 dígitos'),
                        ),
                      ),
                    ],
                  ),

                  _section('Telegram'),
                  TextField(
                    controller: _tgToken,
                    obscureText: true,
                    decoration: _dec('Bot Token', hint: 'vazio = usar BuildConfig'),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _tgChatId,
                    keyboardType: TextInputType.number,
                    decoration: _dec('Chat ID', hint: 'ex: 548741187'),
                  ),

                  _section('Zenvia (SMS/WhatsApp)'),
                  TextField(
                    controller: _zenToken,
                    obscureText: true,
                    decoration: _dec('Zenvia API Token', hint: 'vazio = usar BuildConfig'),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _zenSmsFrom,
                          keyboardType: TextInputType.phone,
                          decoration: _dec('SMS From', hint: 'ex: 55119...'),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: TextField(
                          controller: _sosSmsTo,
                          keyboardType: TextInputType.phone,
                          decoration: _dec('SMS To', hint: 'ex: 55119...'),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _zenWaFrom,
                          keyboardType: TextInputType.phone,
                          decoration: _dec('Whats From', hint: 'ex: 55119...'),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: TextField(
                          controller: _sosWaTo,
                          keyboardType: TextInputType.phone,
                          decoration: _dec('Whats To', hint: 'ex: 55119...'),
                        ),
                      ),
                    ],
                  ),

                  _section('E-mail (SendGrid)'),
                  TextField(
                    controller: _sgKey,
                    obscureText: true,
                    decoration: _dec('SendGrid API Key', hint: 'vazio = usar BuildConfig'),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _sgFrom,
                    keyboardType: TextInputType.emailAddress,
                    decoration: _dec('Remetente (from)', hint: 'ex: alerta@dominio.com'),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _sosEmailTo,
                    keyboardType: TextInputType.emailAddress,
                    decoration: _dec('Destinatários', hint: 'separe por vírgula'),
                  ),

                  const SizedBox(height: 18),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: _save,
                      icon: const Icon(Icons.save),
                      label: const Text('Salvar'),
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}
