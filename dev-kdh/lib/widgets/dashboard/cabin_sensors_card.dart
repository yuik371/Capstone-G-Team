import 'package:flutter/material.dart';
import '../../config/app_theme.dart';

class CabinSensorsCard extends StatelessWidget {
  const CabinSensorsCard({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header Row
          const Row(
            children: [
              Text(
                'CABIN SENSORS & LINK',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w900,
                  color: Color(0xFF1F2937),
                  letterSpacing: 0.2,
                ),
              ),
              Spacer(),
              Icon(Icons.sensors, color: Color(0xFF059669), size: 16),
              SizedBox(width: 4),
              Text(
                'ALL SYNCED',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                  color: Color(0xFF059669),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // 3 Sensor Blocks
          Row(
            children: [
              // Sensor 1: LP15 Defibrillator
              Expanded(
                child: _buildSensorItem(
                  icon: Icons.monitor_heart_outlined,
                  title: 'LP15 제세동기',
                  statusText: 'BT 연동됨',
                  statusColor: const Color(0xFF991B1B),
                  isDotGreen: true,
                ),
              ),
              const SizedBox(width: 10),

              // Sensor 2: Transport Ventilator
              Expanded(
                child: _buildSensorItem(
                  icon: Icons.air,
                  title: '이동식 인공호흡기',
                  statusText: '대기 중 (OK)',
                  statusColor: const Color(0xFF059669),
                  isDotGreen: true,
                ),
              ),
              const SizedBox(width: 10),

              // Sensor 3: Main Oxygen Tank
              Expanded(
                child: _buildSensorItem(
                  icon: Icons.propane_tank_outlined,
                  title: '주산소 탱크',
                  statusText: '14.8 MPa',
                  statusColor: const Color(0xFF4B5563),
                  valueBadge: '98%',
                  badgeColor: const Color(0xFF991B1B),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSensorItem({
    required IconData icon,
    required String title,
    required String statusText,
    required Color statusColor,
    bool isDotGreen = false,
    String? valueBadge,
    Color? badgeColor,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFFF9FAFB),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 18, color: const Color(0xFF4B5563)),
              const Spacer(),
              if (valueBadge != null)
                Text(
                  valueBadge,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w900,
                    color: badgeColor ?? const Color(0xFF1F2937),
                  ),
                )
              else if (isDotGreen)
                Container(
                  width: 6,
                  height: 6,
                  decoration: const BoxDecoration(
                    color: Color(0xFF059669),
                    shape: BoxShape.circle,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            title,
            style: const TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: Color(0xFF6B7280),
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 2),
          Text(
            statusText,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w800,
              color: statusColor,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}
