import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/ems_provider.dart';

class NavigationHud extends StatelessWidget {
  const NavigationHud({super.key});

  @override
  Widget build(BuildContext context) {
    final ems = context.watch<EmsProvider>();
    final nav = ems.navigation;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.12),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: Row(
        children: [
          // 1. ETA
          Expanded(
            flex: 3,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  '도착 예정 (ETA)',
                  style: TextStyle(
                    fontSize: 8,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF6B7280),
                  ),
                ),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.baseline,
                    textBaseline: TextBaseline.alphabetic,
                    children: [
                      Text(
                        nav.etaText,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w900,
                          color: Color(0xFF991B1B),
                          letterSpacing: -0.5,
                        ),
                      ),
                      const SizedBox(width: 3),
                      const Text(
                        '분:초',
                        style: TextStyle(
                          fontSize: 9,
                          fontWeight: FontWeight.w600,
                          color: Color(0xFF6B7280),
                        ),
                      ),
                    ],
                  ),
                ),
                const Text(
                  '정체 없음 (최적)',
                  style: TextStyle(
                    fontSize: 9,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF059669),
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),

          Container(width: 1, height: 30, color: const Color(0xFFE5E7EB)),
          const SizedBox(width: 8),

          // 2. Remaining Distance
          Expanded(
            flex: 3,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  '잔여 거리',
                  style: TextStyle(
                    fontSize: 8,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF6B7280),
                  ),
                ),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.baseline,
                    textBaseline: TextBaseline.alphabetic,
                    children: [
                      Text(
                        nav.remainingDistanceKm.replaceAll(' km', ''),
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w900,
                          color: Color(0xFF111827),
                          letterSpacing: -0.5,
                        ),
                      ),
                      const SizedBox(width: 3),
                      const Text(
                        'km',
                        style: TextStyle(
                          fontSize: 9,
                          fontWeight: FontWeight.w600,
                          color: Color(0xFF6B7280),
                        ),
                      ),
                    ],
                  ),
                ),
                Text(
                  nav.roadName,
                  style: const TextStyle(
                    fontSize: 9,
                    fontWeight: FontWeight.w500,
                    color: Color(0xFF4B5563),
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),

          Container(width: 1, height: 30, color: const Color(0xFFE5E7EB)),
          const SizedBox(width: 8),

          // 3. Current Location Coordinates
          Expanded(
            flex: 4,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  '현재 위치',
                  style: TextStyle(
                    fontSize: 8,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF6B7280),
                  ),
                ),
                const Text(
                  '청계천로 고가',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF111827),
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                Text(
                  '${nav.currentAmbulanceLocation.latitude.toStringAsFixed(4)}, ${nav.currentAmbulanceLocation.longitude.toStringAsFixed(4)}',
                  style: const TextStyle(
                    fontSize: 9,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF0284C7),
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),

          // 4. Divert Route Button
          OutlinedButton.icon(
            style: OutlinedButton.styleFrom(
              foregroundColor: const Color(0xFF4B5563),
              backgroundColor: const Color(0xFFF9FAFB),
              side: const BorderSide(color: Color(0xFFE5E7EB)),
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
            ),
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('실시간 교통 반영: 을지로 방면 우회 보조 경로 분석 완료'),
                  backgroundColor: Color(0xFF1F2937),
                ),
              );
            },
            icon: const Icon(Icons.alt_route, size: 14),
            label: const Text('우회', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700)),
          ),
        ],
      ),
    );
  }
}
