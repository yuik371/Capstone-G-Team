import 'package:flutter/material.dart';
import '../../config/app_theme.dart';

class EmsHeader extends StatelessWidget {
  const EmsHeader({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 72,
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(
          bottom: BorderSide(color: AppTheme.cardBorder, width: 1),
        ),
      ),
      child: FittedBox(
        fit: BoxFit.scaleDown,
        alignment: Alignment.centerLeft,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            // 119 TACTICAL EMS Logo & Unit Info
            _buildUnitIdentity(),
            const SizedBox(width: 16),

            // Code Red Emergency Status Badge
            _buildCodeRedBadge(),

            const SizedBox(width: 32),

            // Telemetry Pills: 5G, RTK GPS, PTT Hotline, Profile
            _buildTelemetryPills(context),
          ],
        ),
      ),
    );
  }

  Widget _buildUnitIdentity() {
    return Row(
      children: [
        // Star of Life Red Circle Icon
        Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: AppTheme.primaryRed.withValues(alpha: 0.08),
            shape: BoxShape.circle,
            border: Border.all(color: AppTheme.primaryRed.withValues(alpha: 0.3), width: 1.5),
          ),
          child: const Center(
            child: Icon(
              Icons.emergency,
              color: AppTheme.primaryRed,
              size: 26,
            ),
          ),
        ),
        const SizedBox(width: 12),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Row(
              children: [
                const Text(
                  '119 TACTICAL EMS',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w900,
                    color: Color(0xFF1F2937),
                    letterSpacing: -0.2,
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryRed,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: const Text(
                    'AMB-704',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                      letterSpacing: 0.5,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 2),
            const Text(
              '종로 704호 특수구급대 | JONGNO ADVANCED LIFE SUPPORT',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w500,
                color: Color(0xFF6B7280),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildCodeRedBadge() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
      decoration: BoxDecoration(
        color: const Color(0xFF991B1B),
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF991B1B).withValues(alpha: 0.25),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: const Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.crisis_alert,
            color: Colors.white,
            size: 16,
          ),
          SizedBox(width: 8),
          Text(
            '긴급 출동 및 이송 중 (CODE RED)',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w800,
              color: Colors.white,
              letterSpacing: -0.2,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTelemetryPills(BuildContext context) {
    return Row(
      children: [
        // 5G Tactical
        _buildPillItem(
          icon: Icons.wifi_tethering,
          iconColor: const Color(0xFF991B1B),
          labelTop: '5G TACTICAL',
          labelBottom: '4ms ONLINE',
          bottomColor: const Color(0xFF991B1B),
        ),
        const SizedBox(width: 12),

        // RTK GPS
        _buildPillItem(
          icon: Icons.satellite_alt,
          iconColor: const Color(0xFF0284C7),
          labelTop: 'RTK GPS',
          labelBottom: 'LOCKED (0.02m)',
          bottomColor: const Color(0xFF0284C7),
        ),
        const SizedBox(width: 12),

        // PTT Hotline
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: const Color(0xFFE5E7EB)),
          ),
          child: const Row(
            children: [
              Icon(Icons.headset_mic_outlined, color: AppTheme.primaryRed, size: 18),
              SizedBox(width: 8),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    'EMERGENCY DIRECT PTT',
                    style: TextStyle(
                      fontSize: 9,
                      fontWeight: FontWeight.w700,
                      color: Color(0xFF9CA3AF),
                    ),
                  ),
                  Text(
                    '지도의사 직통 연결',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: Color(0xFF1F2937),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(width: 14),

        // Officer Profile
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
          decoration: BoxDecoration(
            color: const Color(0xFFF9FAFB),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: const Color(0xFFE5E7EB)),
          ),
          child: const Row(
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    '김민우 반장',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                      color: Color(0xFF1F2937),
                    ),
                  ),
                  Text(
                    '1급 응급구조사 (EMT-P)',
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w500,
                      color: Color(0xFF6B7280),
                    ),
                  ),
                ],
              ),
              SizedBox(width: 10),
              CircleAvatar(
                radius: 16,
                backgroundColor: Color(0xFFFEE2E2),
                child: Icon(Icons.person, color: AppTheme.primaryRed, size: 18),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildPillItem({
    required IconData icon,
    required Color iconColor,
    required String labelTop,
    required String labelBottom,
    required Color bottomColor,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: Row(
        children: [
          Icon(icon, color: iconColor, size: 18),
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                labelTop,
                style: const TextStyle(
                  fontSize: 9,
                  fontWeight: FontWeight.w700,
                  color: Color(0xFF9CA3AF),
                ),
              ),
              Text(
                labelBottom,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                  color: bottomColor,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
