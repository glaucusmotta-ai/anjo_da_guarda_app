import 'package:flutter/material.dart';
import '../theme/anjo_theme.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  bool isServiceActive = true;     // depois ligamos no serviço real
  bool isHibernationOn = false;    // depois ligamos no AudioService

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AnjoTheme.bg,
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFF050A1A), Color(0xFF0A1430)],
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
          ),
        ),
        child: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.start,
                children: [
                  const SizedBox(height: 16),
                  const Text(
                    'ANJO DA GUARDA',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 26,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 1.5,
                    ),
                  ),
                  const SizedBox(height: 24),

                  // CARD PRINCIPAL
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(24),
                      gradient: const LinearGradient(
                        colors: [
                          Color(0x3300FFFF),
                          Color(0x330066FF),
                        ],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      border: Border.all(
                        color: AnjoTheme.neonBlue,
                        width: 1.5,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: AnjoTheme.neonBlue.withOpacity(0.4),
                          blurRadius: 20,
                          spreadRadius: -5,
                          offset: const Offset(0, 8),
                        ),
                      ],
                    ),
                    child: Column(
                      children: [
                        // botões Iniciar / Parar
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                          children: [
                            _NeonButton(
                              label: 'Iniciar serviço',
                              color: AnjoTheme.neonGreen,
                              onTap: () {
                                setState(() => isServiceActive = true);
                                // TODO: startService() de verdade aqui
                              },
                            ),
                            _NeonButton(
                              label: 'Parar serviço',
                              color: AnjoTheme.neonRed,
                              onTap: () {
                                setState(() => isServiceActive = false);
                                // TODO: stopService() de verdade aqui
                              },
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),

                        // Estado do serviço
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text(
                              'Estado do serviço:',
                              style: TextStyle(
                                color: Colors.white70,
                                fontSize: 14,
                              ),
                            ),
                            Text(
                              isServiceActive ? 'ATIVO' : 'INATIVO',
                              style: TextStyle(
                                color: isServiceActive
                                    ? AnjoTheme.neonGreen
                                    : Colors.grey,
                                fontWeight: FontWeight.bold,
                                fontSize: 14,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),

                        // Toggle de hibernação
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text(
                              'Modo hibernação',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 14,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                            GestureDetector(
                              onTap: () {
                                setState(() {
                                  isHibernationOn = !isHibernationOn;
                                });
                                // TODO: ligar/desligar AudioService aqui
                              },
                              child: _OnOffPill(isOn: isHibernationOn),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 24),

                  // CARD EXPLICATIVO
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AnjoTheme.cardBlue.withOpacity(0.8),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: AnjoTheme.neonBlue.withOpacity(0.6),
                        width: 1,
                      ),
                    ),
                    child: const Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Quando hibernação está ON:',
                          style: TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.bold,
                            fontSize: 14,
                          ),
                        ),
                        SizedBox(height: 8),
                        Text(
                          '• SOS por voz (palavra-chave) PAUSADO\n'
                          '• PIN de coação continua funcionando\n'
                          '• Tile rápido continua funcionando',
                          style: TextStyle(
                            color: Colors.white70,
                            fontSize: 13,
                            height: 1.4,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// botão com borda/brilho neon
class _NeonButton extends StatelessWidget {
  final String label;
  final Color color;
  final VoidCallback onTap;

  const _NeonButton({
    required this.label,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          height: 44,
          margin: const EdgeInsets.symmetric(horizontal: 4),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(30),
            border: Border.all(color: color, width: 1.5),
            boxShadow: [
              BoxShadow(
                color: color.withOpacity(0.4),
                blurRadius: 16,
                spreadRadius: -4,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          alignment: Alignment.center,
          child: Text(
            label,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.w600,
              fontSize: 13,
            ),
          ),
        ),
      ),
    );
  }
}

// pill ON/OFF parecido com o print
class _OnOffPill extends StatelessWidget {
  final bool isOn;

  const _OnOffPill({required this.isOn});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 80,
      height: 30,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        color: Colors.black.withOpacity(0.4),
        border: Border.all(color: Colors.white24),
      ),
      child: Stack(
        children: [
          // texto OFF
          Align(
            alignment: Alignment.centerRight,
            child: Padding(
              padding: const EdgeInsets.only(right: 10),
              child: Text(
                'OFF',
                style: TextStyle(
                  color: isOn ? Colors.white54 : Colors.white,
                  fontSize: 11,
                ),
              ),
            ),
          ),
          // texto ON
          Align(
            alignment: Alignment.centerLeft,
            child: Padding(
              padding: const EdgeInsets.only(left: 10),
              child: Text(
                'ON',
                style: TextStyle(
                  color: isOn ? Colors.white : Colors.white54,
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
          // bolinha
          AnimatedAlign(
            duration: const Duration(milliseconds: 200),
            curve: Curves.easeOut,
            alignment:
                isOn ? Alignment.centerLeft : Alignment.centerRight,
            child: Container(
              width: 26,
              height: 26,
              margin: const EdgeInsets.symmetric(horizontal: 2),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isOn
                    ? AnjoTheme.neonOrange
                    : Colors.grey.shade500,
                boxShadow: [
                  BoxShadow(
                    color: (isOn
                            ? AnjoTheme.neonOrange
                            : Colors.grey)
                        .withOpacity(0.6),
                    blurRadius: 12,
                    spreadRadius: -2,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
