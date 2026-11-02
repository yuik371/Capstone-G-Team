import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/ems_provider.dart';

class EmergencyDispatchBanner extends StatefulWidget {
  const EmergencyDispatchBanner({super.key});

  @override
  State<EmergencyDispatchBanner> createState() => _EmergencyDispatchBannerState();
}

class _EmergencyDispatchBannerState extends State<EmergencyDispatchBanner> {
  bool _isPressing = false;

  @override
  Widget build(BuildContext context) {
    final ems = context.watch<EmsProvider>();

    return GestureDetector(
      onTapDown: (_) => setState(() => _isPressing = true),
      onTapUp: (_) {
        setState(() => _isPressing = false);
        ems.startEmergencyTransport();
      },
      onTapCancel: () => setState(() => _isPressing = false),
      child: AnimatedScale(
        scale: _isPressing ? 0.985 : 1.0,
        duration: const Duration(milliseconds: 100),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 18),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [
                Color(0xFF991B1B),
                Color(0xFF881337),
                Color(0xFF7F1D1D),
              ],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF991B1B).withValues(alpha: 0.35),
                blurRadius: 14,
                offset: const Offset(0, 6),
              ),
            ],
            border: Border.all(
              color: Colors.white.withValues(alpha: 0.15),
              width: 1.5,
            ),
          ),
          child: Row(
            children: [
              // Ambulance Icon with Ripple Background
              Container(
                width: 58,
                height: 58,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.15),
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: Colors.white.withValues(alpha: 0.3),
                    width: 2,
                  ),
                ),
                child: const Center(
                  child: Icon(
                    Icons.directions_car_filled,
                    color: Colors.white,
                    size: 32,
                  ),
                ),
              ),
              const SizedBox(width: 20),

              // Title and Description
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: const Text(
                            'ONE-TOUCH CRITICAL DISPATCH',
                            style: TextStyle(
                              fontSize: 9,
                              fontWeight: FontWeight.w900,
                              color: Color(0xFF991B1B),
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'EMERGENCY TRANSPORT START',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            color: Colors.white.withValues(alpha: 0.8),
                            letterSpacing: 0.5,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      '응급 환자 이송 시작',
                      style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.w900,
                        color: Colors.white,
                        letterSpacing: -0.3,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '차량 진동 시 오작동 방지 안전 롱터치(0.5초) 대응 | 즉시 응급실 사전 통보 및 GIS 최단경로 확정',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w400,
                        color: Colors.white.withValues(alpha: 0.85),
                      ),
                    ),
                  ],
                ),
              ),

              // Dashed Line Simulator
              Container(
                margin: const EdgeInsets.symmetric(horizontal: 16),
                width: 1,
                height: 50,
                color: Colors.white.withValues(alpha: 0.2),
              ),

              // Right: AI Recommendation Info & Launch Button
              Row(
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        'AI RECOMMENDED ER',
                        style: TextStyle(
                          fontSize: 9,
                          fontWeight: FontWeight.w800,
                          color: Colors.white.withValues(alpha: 0.75),
                          letterSpacing: 0.5,
                        ),
                      ),
                      const SizedBox(height: 2),
                      const Text(
                        '서울대병원 1순위',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w900,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'ETA 05:40 / 2.8km',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: Colors.white.withValues(alpha: 0.9),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(width: 16),
                  Container(
                    width: 48,
                    height: 48,
                    decoration: const BoxDecoration(
                      color: Colors.white,
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black26,
                          blurRadius: 8,
                          offset: Offset(0, 3),
                        ),
                      ],
                    ),
                    child: const Center(
                      child: Icon(
                        Icons.navigation_rounded,
                        color: Color(0xFF991B1B),
                        size: 26,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
