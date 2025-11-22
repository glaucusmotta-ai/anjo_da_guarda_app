// lib/models/user_profile.dart

class UserProfile {
  final String displayName; // reservado se quisermos usar o nome depois
  final String cep;
  final String city;
  final String uf;

  const UserProfile({
    this.displayName = '',
    this.cep = '',
    this.city = '',
    this.uf = '',
  });

  /// Usado pelo storage quando ainda não há nada salvo
  factory UserProfile.empty() => const UserProfile();

  UserProfile copyWith({
    String? displayName,
    String? cep,
    String? city,
    String? uf,
  }) {
    return UserProfile(
      displayName: displayName ?? this.displayName,
      cep: cep ?? this.cep,
      city: city ?? this.city,
      uf: uf ?? this.uf,
    );
  }

  Map<String, dynamic> toJson() => {
        'displayName': displayName,
        'cep': cep,
        'city': city,
        'uf': uf,
      };

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      displayName: (json['displayName'] ?? '') as String,
      cep: (json['cep'] ?? '') as String,
      city: (json['city'] ?? '') as String,
      uf: (json['uf'] ?? '') as String,
    );
  }
}
