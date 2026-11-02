import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/app_theme.dart';
import '../../providers/ems_provider.dart';

class VitalQuadGrid extends StatelessWidget {
  const VitalQuadGrid({super.key});

  @override
  Widget build(BuildContext context) {
    final ems = context.watch<EmsProvider>();
    final patient = ems.patient;

    return Column(
      children: [
        // Top Row: Blood Pressure (NIBP) & Pulse Rate (PR)
        Row(
          children: [
            Expanded(
              child: _buildVitalCard(
                icon: Icons.favorite_border,
                iconColor: const Color(0xFF991B1B),
                title: '혈압 NIBP',
                alertBadge: '저혈압 CRITICAL',
                badgeBg: const Color(0xFFFEE2E2),
                badgeTextColor: const Color(0xFF991B1B),
                mainValue: '${patient.systolicBp}/${patient.diastolicBp}',
                unit: 'mmHg',
                valueColor: const Color(0xFF991B1B),
                subLeft: 'MAP: ${patient.mapBp} mmHg',
                subRight: '↓ 기준 미달',
                subRightColor: const Color(0xFF991B1B),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _buildVitalCard(
                icon: Icons.monitor_heart_outlined,
                iconColor: const Color(0xFF991B1B),
                title: '맥박수 PR',
                alertBadge: '빈맥 ALERT',
                badgeBg: const Color(0xFFFEE2E2),
                badgeTextColor: const Color(0xFF991B1B),
                mainValue: '${patient.heartRate}',
                unit: 'BPM',
                valueColor: const Color(0xFF991B1B),
                subLeft: 'R-R: ${patient.rrIntervalMs}ms',
                subRight: '↗ 동성빈맥',
                subRightColor: const Color(0xFF991B1B),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),

        // Bottom Row: SpO2 & Body Temp / Resp Rate
        Row(
          children: [
            Expanded(
              child: _buildVitalCard(
                icon: Icons.air,
                iconColor: const Color(0xFF0284C7),
                title: '산소포화도 SPO2',
                alertBadge: '산소 투여 중 (15L/m)',
                badgeBg: const Color(0xFFE0F2FE),
                badgeTextColor: const Color(0xFF0284C7),
                mainValue: '${patient.spo2}',
                unit: '%',
                valueColor: const Color(0xFF0284C7),
                subLeft: 'NRB 마스크 착용',
                subRight: 'PI: 4.8',
                subRightColor: const Color(0xFF0284C7),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _buildVitalCard(
                icon: Icons.thermostat_outlined,
                iconColor: const Color(0xFF059669),
                title: '체온 / 호흡수',
                alertBadge: '정상 범위',
                badgeBg: const Color(0xFFD1FAE5),
                badgeTextColor: const Color(0xFF059669),
                mainValue: '${patient.bodyTemp} °C   ${patient.respRate}',
                unit: 'RR',
                valueColor: const Color(0xFF059669),
                subLeft: '고막 체온계 연동',
                subRight: '체온 보온포 적용',
                subRightColor: const Color(0xFF059669),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildVitalCard({
    required IconData icon,
    required Color iconColor,
    required String title,
    required String alertBadge,
    required Color badgeBg,
    required Color badgeTextColor,
    required String mainValue,
    required String unit,
    required Color valueColor,
    required String subLeft,
    required String subRight,
    required Color subRightColor,
  }) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header: Icon + Title + Alert Badge
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Row(
              children: [
                Icon(icon, color: iconColor, size: 16),
                const SizedBox(width: 6),
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF4B5563),
                  ),
                ),
                const SizedBox(width: 10),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: badgeBg,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    alertBadge,
                    style: TextStyle(
                      fontSize: 9,
                      fontWeight: FontWeight.w800,
                      color: badgeTextColor,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 6),

          // Main Measurement Value
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(
                  mainValue,
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w900,
                    color: valueColor,
                    letterSpacing: -0.5,
                  ),
                ),
                const SizedBox(width: 6),
                Text(
                  unit,
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF6B7280),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 6),

          // Sub Notes
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Row(
              children: [
                Text(
                  subLeft,
                  style: const TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w500,
                    color: Color(0xFF6B7280),
                  ),
                ),
                const SizedBox(width: 10),
                Text(
                  subRight,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    color: subRightColor,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
