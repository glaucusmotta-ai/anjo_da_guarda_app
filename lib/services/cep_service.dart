// lib/services/cep_service.dart

import 'dart:convert';
import 'package:http/http.dart' as http;

class CepInfo {
  final String city;
  final String uf;

  CepInfo({
    required this.city,
    required this.uf,
  });

  factory CepInfo.fromJson(Map<String, dynamic> json) {
    return CepInfo(
      city: (json['localidade'] ?? '') as String,
      uf: (json['uf'] ?? '') as String,
    );
  }
}

class CepService {
  /// `cepDigits` deve vir só com números (ex: "04094000")
  Future<CepInfo?> lookupCep(String cepDigits) async {
    final uri = Uri.parse('https://viacep.com.br/ws/$cepDigits/json/');
    final resp = await http.get(uri);

    if (resp.statusCode != 200) return null;

    final data = json.decode(resp.body) as Map<String, dynamic>;
    if (data['erro'] == true) return null;

    return CepInfo.fromJson(data);
  }
}
