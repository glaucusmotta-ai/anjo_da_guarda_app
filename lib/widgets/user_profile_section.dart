// lib/widgets/user_profile_section.dart
import 'package:flutter/material.dart';

import '../models/user_profile.dart';
import '../services/cep_service.dart';
import '../storage/user_profile_storage.dart';

class UserProfileSection extends StatefulWidget {
  const UserProfileSection({super.key});

  @override
  UserProfileSectionState createState() => UserProfileSectionState();
}

/// State público para podermos chamar saveRegion() a partir da SettingsScreen
class UserProfileSectionState extends State<UserProfileSection> {
  final _formKey = GlobalKey<FormState>();

  final _nameController = TextEditingController();
  final _cepController = TextEditingController();
  final _cityController = TextEditingController();
  final _ufController = TextEditingController();

  final _cepService = CepService();
  final _storage = UserProfileStorage();

  bool _loadingCep = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final profile = await _storage.loadProfile();
    setState(() {
      _nameController.text = profile.displayName;
      _cepController.text = profile.cep;
      _cityController.text = profile.city;
      _ufController.text = profile.uf;
    });
  }

  @override
  void dispose() {
    _nameController.dispose();
    _cepController.dispose();
    _cityController.dispose();
    _ufController.dispose();
    super.dispose();
  }

  /// Chamado pela SettingsScreen quando o usuário toca no botão "Salvar"
  Future<void> saveRegion() async {
    if (!(_formKey.currentState?.validate() ?? true)) return;

    final profile = UserProfile(
      displayName: _nameController.text.trim(),
      cep: _cepController.text.trim(),
      city: _cityController.text.trim(),
      uf: _ufController.text.trim(),
    );

    await _storage.saveProfile(profile);
  }

  String? _validateCep(String? v) {
    final digits = (v ?? '').replaceAll(RegExp(r'\D'), '');
    if (digits.isEmpty) return null; // opcional
    if (digits.length != 8) return 'CEP deve ter 8 dígitos';
    return null;
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

  Future<void> _onCepChanged(String value) async {
    final digits = value.replaceAll(RegExp(r'\D'), '');
    if (digits.length != 8) return;

    setState(() => _loadingCep = true);
    try {
      final info = await _cepService.lookupCep(digits);
      if (info != null && mounted) {
        setState(() {
          _cityController.text = info.city;
          _ufController.text = info.uf;
        });
      }
    } finally {
      if (mounted) setState(() => _loadingCep = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      color: const Color(0xFF111216),
      elevation: 2,
      margin: const EdgeInsets.symmetric(vertical: 10),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: const [
                Icon(Icons.insights, size: 18, color: Colors.white70),
                SizedBox(width: 8),
                Text(
                  'Informação adicional',
                  style: TextStyle(
                    color: Colors.white70,
                    fontWeight: FontWeight.w700,
                    letterSpacing: .3,
                  ),
                ),
              ]),
              const SizedBox(height: 6),
              const Text(
                'Isso ajuda o app Anjo da Guarda a identificar as regiões de maior vulnerabilidade. '
                'Esses dados NÃO ficam visíveis para outros usuários.',
                style: TextStyle(color: Colors.white54, fontSize: 12),
              ),
              const SizedBox(height: 12),

              // Nome NÃO aparece aqui para não duplicar com "Seus dados"
              TextFormField(
                controller: _cepController,
                keyboardType: TextInputType.number,
                validator: _validateCep,
                onChanged: _onCepChanged,
                decoration: _dec(
                  label: 'CEP',
                  hint: 'Somente números',
                  icon: Icons.location_on_outlined,
                  suffix: _loadingCep
                      ? const SizedBox(
                          height: 16,
                          width: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : null,
                ),
              ),
              const SizedBox(height: 10),
              TextFormField(
                controller: _cityController,
                textCapitalization: TextCapitalization.words,
                decoration: _dec(
                  label: 'Cidade',
                  icon: Icons.location_city_outlined,
                ),
              ),
              const SizedBox(height: 10),
              TextFormField(
                controller: _ufController,
                textCapitalization: TextCapitalization.characters,
                maxLength: 2,
                decoration: _dec(
                  label: 'Estado (UF)',
                  hint: 'SP, RJ, MG...',
                  icon: Icons.map_outlined,
                ),
              ),

              // 🔹 SEM botão "Salvar região" aqui.
              // O salvamento é feito junto com o botão "Salvar" da tela.
            ],
          ),
        ),
      ),
    );
  }
}
