import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'sms_addon_keys.dart';
import 'sms_addon_config.dart';

Future<bool> guardEnableSmsAddon({
  required BuildContext context,
  required SharedPreferences prefs,
}) async {
  final entitled = prefs.getBool(SmsAddonKeys.smsAddonEntitled) ?? false;

  if (entitled) return true;

  await showDialog<void>(
    context: context,
    builder: (_) => AlertDialog(
      title: const Text('Serviço SMSAddon'),
      content: const Text(
        'Este recurso é um add-on pago.\nDeseja contratar agora?',
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Agora não'),
        ),
        ElevatedButton(
          onPressed: () async {
            final uri = Uri.parse(SmsAddonConfig.buyUrl);
            await launchUrl(uri, mode: LaunchMode.externalApplication);
            if (context.mounted) Navigator.pop(context);
          },
          child: const Text('Contratar'),
        ),
      ],
    ),
  );

  return false;
}
