import 'package:flutter/material.dart';
import 'audio_service_controller.dart'; // mantém o seu controller

void main() => runApp(const MyApp());

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Anjo da Guarda',
      theme: ThemeData(
        useMaterial3: true,
        colorSchemeSeed: Colors.deepPurple,
      ),
      home: const HomePage(),
    );
  }
}

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Anjo da Guarda')),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ElevatedButton(
              onPressed: () async {
                try {
                  await AudioCtl.start();
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Serviço iniciado')),
                  );
                } catch (e) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Falha ao iniciar: $e')),
                  );
                }
              },
              child: const Text('Iniciar serviço'),
            ),
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: () async {
                try {
                  await AudioCtl.stop();
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Serviço parado')),
                  );
                } catch (e) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Falha ao parar: $e')),
                  );
                }
              },
              child: const Text('Parar serviço'),
            ),
          ],
        ),
      ),
    );
  }
}
