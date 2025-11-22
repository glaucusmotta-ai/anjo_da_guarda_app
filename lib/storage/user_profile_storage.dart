// lib/storage/user_profile_storage.dart

import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/user_profile.dart';

class UserProfileStorage {
  static const _keyProfile = 'user_profile_region_v1';

  Future<UserProfile> loadProfile() async {
    final prefs = await SharedPreferences.getInstance();
    final jsonStr = prefs.getString(_keyProfile);

    if (jsonStr == null || jsonStr.isEmpty) {
      return UserProfile.empty();
    }

    try {
      final map = json.decode(jsonStr) as Map<String, dynamic>;
      return UserProfile.fromJson(map);
    } catch (_) {
      // Se der erro no parse, volta vazio pra não quebrar o app
      return UserProfile.empty();
    }
  }

  Future<void> saveProfile(UserProfile profile) async {
    final prefs = await SharedPreferences.getInstance();
    final jsonStr = json.encode(profile.toJson());
    await prefs.setString(_keyProfile, jsonStr);
  }
}
