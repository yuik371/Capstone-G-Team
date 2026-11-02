import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/app_theme.dart';
import '../../providers/ems_provider.dart';

class EmsSidebar extends StatelessWidget {
  const EmsSidebar({super.key});

  @override
  Widget build(BuildContext context) {
    final emsProvider = context.watch<EmsProvider>();
    final selectedIndex = emsProvider.selectedSidebarIndex;

    return Container(
      width: 220,
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(
          right: BorderSide(color: AppTheme.cardBorder, width: 1),
        ),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 16),
      child: Column(
        children: [
          // Nav Item 0: 환자 생체 원격 모니터
          _buildNavItem(
            context: context,
            index: 0,
            icon: Icons.monitor_heart_outlined,
            label: '환자 생체 원격 모니터',
            isSelected: selectedIndex == 0,
            onTap: () => emsProvider.setSidebarIndex(0),
          ),
          const SizedBox(height: 10),

          // Nav Item 1: 응급 GIS 및 병원 수용
          _buildNavItem(
            context: context,
            index: 1,
            icon: Icons.emergency_outlined,
            label: '응급 GIS 및 병원 수용',
            isSelected: selectedIndex == 1,
            onTap: () => emsProvider.setSidebarIndex(1),
          ),
          const SizedBox(height: 10),

          // Nav Item 2: 응급처치 지침 및 약물
          _buildNavItem(
            context: context,
            index: 2,
            icon: Icons.medical_services_outlined,
            label: '응급처치 지침 및 약물',
            isSelected: selectedIndex == 2,
            onTap: () => emsProvider.setSidebarIndex(2),
          ),
          const SizedBox(height: 10),

          // Nav Item 3: ePCR 구급활동일지
          _buildNavItem(
            context: context,
            index: 3,
            icon: Icons.assignment_outlined,
            label: 'ePCR 구급활동일지',
            isSelected: selectedIndex == 3,
            onTap: () => emsProvider.setSidebarIndex(3),
          ),

          const Spacer(),

          // Tablet Battery Status
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: const Color(0xFFF9FAFB),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0xFFE5E7EB)),
            ),
            child: const FittedBox(
              fit: BoxFit.scaleDown,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    '구급 단말기 전원',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF4B5563),
                    ),
                  ),
                  SizedBox(width: 8),
                  Row(
                    children: [
                      Icon(Icons.battery_charging_full, color: Color(0xFF059669), size: 16),
                      SizedBox(width: 4),
                      Text(
                        '98%',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w800,
                          color: Color(0xFF059669),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),

          // CODE BLUE 신속선언 Critical Action Button
          InkWell(
            onTap: () => _showCodeBlueDialog(context),
            borderRadius: BorderRadius.circular(12),
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 14),
              decoration: BoxDecoration(
                color: const Color(0xFF8B1515),
                borderRadius: BorderRadius.circular(12),
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFF8B1515).withValues(alpha: 0.35),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: const FittedBox(
                fit: BoxFit.scaleDown,
                child: Padding(
                  padding: EdgeInsets.symmetric(horizontal: 8),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.warning_amber_rounded, color: Colors.white, size: 20),
                      SizedBox(width: 8),
                      Text(
                        'CODE BLUE 신속선언',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w900,
                          color: Colors.white,
                          letterSpacing: -0.2,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNavItem({
    required BuildContext context,
    required int index,
    required IconData icon,
    required String label,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    // Styling differs slightly: if index 0 is selected (Dashboard mode in Image 1), dark red.
    // If index 1 is selected (Split screen in Image 2), soft pink background.
    final bool isDarkRedSelected = isSelected && index == 0;
    final bool isSoftPinkSelected = isSelected && index != 0;

    Color bgColor = Colors.transparent;
    Color textColor = const Color(0xFF4B5563);
    Color iconColor = const Color(0xFF6B7280);

    if (isDarkRedSelected) {
      bgColor = const Color(0xFF8B1515);
      textColor = Colors.white;
      iconColor = Colors.white;
    } else if (isSoftPinkSelected) {
      bgColor = const Color(0xFFFEE2E2);
      textColor = const Color(0xFF991B1B);
      iconColor = const Color(0xFF991B1B);
    }

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(10),
          border: isSoftPinkSelected
              ? Border.all(color: const Color(0xFFFECACA), width: 1)
              : null,
        ),
        child: Row(
          children: [
            Icon(icon, color: iconColor, size: 20),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                label,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: isSelected ? FontWeight.w800 : FontWeight.w600,
                  color: textColor,
                  letterSpacing: -0.2,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showCodeBlueDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Row(
          children: [
            Icon(Icons.crisis_alert, color: Color(0xFF8B1515), size: 28),
            SizedBox(width: 10),
            Text(
              'CODE BLUE 신속선언',
              style: TextStyle(
                fontWeight: FontWeight.w900,
                color: Color(0xFF8B1515),
              ),
            ),
          ],
        ),
        content: const Text(
          '심정지/호흡정지 등 즉각적인 전문심폐소생술(ACLS) 대응을 위해 지도의사 핫라인 연결 및 수락 병원 외상소생실에 긴급 방송을 송출하시겠습니까?',
          style: TextStyle(fontSize: 14, height: 1.5),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('취소', style: TextStyle(color: Colors.grey)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF8B1515),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: () {
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  backgroundColor: Color(0xFF8B1515),
                  content: Text('CODE BLUE 선언 완료: 병원 응급소생팀 즉시 호출 전송됨'),
                ),
              );
            },
            child: const Text('선언 발령', style: TextStyle(fontWeight: FontWeight.w800)),
          ),
        ],
      ),
    );
  }
}
