import 'dart:math';
import 'package:flutter/material.dart';
import '../../config/app_theme.dart';

class LiveEcgMonitor extends StatefulWidget {
  const LiveEcgMonitor({super.key});

  @override
  State<LiveEcgMonitor> createState() => _LiveEcgMonitorState();
}

class _LiveEcgMonitorState extends State<LiveEcgMonitor>
    with SingleTickerProviderStateMixin {
  late AnimationController _animController;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2500),
    )..repeat();
  }

  @override
  void dispose() {
    _animController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header Row
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Row(
              children: [
                const Icon(Icons.favorite_outline, color: Color(0xFF991B1B), size: 16),
                const SizedBox(width: 6),
                const Text(
                  '실시간 심전도 모니터 (Lead II - 25mm/s, 10mm/mV)',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF1F2937),
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFEE2E2),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: const Text(
                    'ST-Elevation (+2.1mm)',
                    style: TextStyle(
                      fontSize: 9,
                      fontWeight: FontWeight.w800,
                      color: Color(0xFF991B1B),
                    ),
                  ),
                ),
                const SizedBox(width: 6),
                const Text(
                  'LP-15 자동 송신 중',
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w500,
                    color: Color(0xFF6B7280),
                  ),
                ),
                const SizedBox(width: 14),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: const Color(0xFFECFDF5),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.circle, color: Color(0xFF059669), size: 6),
                      SizedBox(width: 4),
                      Text(
                        '심실조기수축(PVC) 감지안됨',
                        style: TextStyle(
                          fontSize: 9,
                          fontWeight: FontWeight.w700,
                          color: Color(0xFF059669),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),

          // ECG Animated Canvas
          Container(
            height: 80,
            width: double.infinity,
            decoration: BoxDecoration(
              color: const Color(0xFFFFF9F9), // Subtle pink medical paper grid
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xFFFFE4E6)),
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: AnimatedBuilder(
                animation: _animController,
                builder: (context, child) {
                  return CustomPaint(
                    painter: _EcgWavePainter(progress: _animController.value),
                    size: const Size(double.infinity, 80),
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _EcgWavePainter extends CustomPainter {
  final double progress;

  _EcgWavePainter({required this.progress});

  @override
  void paint(Canvas canvas, Size size) {
    // 1. Draw subtle clinical grid
    final gridPaint = Paint()
      ..color = const Color(0xFFFFD1D5)
      ..strokeWidth = 0.5;

    const gridSpacing = 10.0;
    for (double x = 0; x < size.width; x += gridSpacing) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), gridPaint);
    }
    for (double y = 0; y < size.height; y += gridSpacing) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    // 2. Draw ST-Elevation ECG waveform
    final ecgPaint = Paint()
      ..color = const Color(0xFF8B1515)
      ..strokeWidth = 2.2
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;

    final path = Path();
    final baselineY = size.height * 0.58;
    const waveLength = 140.0; // Length of one heartbeat cycle in pixels

    final offset = progress * waveLength;

    bool firstPoint = true;
    for (double x = 0; x <= size.width; x += 1.5) {
      final t = (x + offset) % waveLength;
      final y = _getEcgSample(t, waveLength, baselineY);

      if (firstPoint) {
        path.moveTo(x, y);
        firstPoint = false;
      } else {
        path.lineTo(x, y);
      }
    }

    canvas.drawPath(path, ecgPaint);
  }

  double _getEcgSample(double t, double waveLength, double base) {
    // Normalize t to 0..1 within heartbeat cycle
    final norm = t / waveLength;

    if (norm < 0.15) {
      // Flat baseline before P
      return base;
    } else if (norm < 0.22) {
      // P wave (slight bump)
      final pNorm = (norm - 0.15) / 0.07;
      return base - sin(pNorm * pi) * 6.0;
    } else if (norm < 0.28) {
      // PR interval flat
      return base;
    } else if (norm < 0.31) {
      // Q dip
      return base + 5.0;
    } else if (norm < 0.36) {
      // R peak (tall spike)
      final rNorm = (norm - 0.31) / 0.05;
      if (rNorm < 0.5) {
        return base + 5.0 - (rNorm * 2) * 44.0;
      } else {
        return (base - 39.0) + ((rNorm - 0.5) * 2) * 50.0;
      }
    } else if (norm < 0.40) {
      // S wave dip
      return base + 11.0;
    } else if (norm < 0.58) {
      // ST-Elevation (+2.1mm): instead of returning to baseline, stays elevated!
      final stNorm = (norm - 0.40) / 0.18;
      final stElevatedBase = base - 7.5; // elevated ST segment
      return stElevatedBase - sin(stNorm * pi) * 8.0; // T wave merged with ST elevation
    } else {
      // Return to baseline
      return base;
    }
  }

  @override
  bool shouldRepaint(covariant _EcgWavePainter oldDelegate) {
    return oldDelegate.progress != progress;
  }
}
