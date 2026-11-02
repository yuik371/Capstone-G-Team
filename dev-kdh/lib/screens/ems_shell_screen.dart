import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../config/app_theme.dart';
import '../providers/ems_provider.dart';
import '../widgets/common/ems_header.dart';
import '../widgets/common/ems_sidebar.dart';
import 'ems_start_dashboard.dart';
import 'ems_split_navigation.dart';

class EmsShellScreen extends StatelessWidget {
  const EmsShellScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final ems = context.watch<EmsProvider>();

    return Scaffold(
      backgroundColor: AppTheme.background,
      body: SafeArea(
        child: Column(
          children: [
            // Top Global Navigation Header (119 TACTICAL EMS, 5G, RTK GPS, PTT)
            const EmsHeader(),

            // Main Body: Left Sidebar + Active View Content
            Expanded(
              child: Row(
                children: [
                  // Left Navigation Sidebar
                  const EmsSidebar(),

                  // Content Area
                  Expanded(
                    child: _buildCurrentContent(ems),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCurrentContent(EmsProvider ems) {
    if (ems.selectedSidebarIndex == 2) {
      return _buildGuidelinePlaceholder();
    } else if (ems.selectedSidebarIndex == 3) {
      return _buildEpcrPlaceholder(ems);
    }

    switch (ems.currentView) {
      case EmsView.dashboard:
        return const EmsStartDashboard();
      case EmsView.splitNavigation:
        return const EmsSplitNavigation();
    }
  }

  Widget _buildGuidelinePlaceholder() {
    return Center(
      child: Container(
        margin: const EdgeInsets.all(24),
        padding: const EdgeInsets.all(32),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppTheme.cardBorder),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.medical_services_outlined, size: 54, color: Color(0xFF991B1B)),
            const SizedBox(height: 16),
            const Text(
              '119 특수구급대 중증외상 / 심혈관 표준 응급처치 지침',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 10),
            const Text(
              '• 외상 소생 수액 요법 (Warm Normal Saline / Permissive Hypotension MAP 65 유지)\n'
              '• ST분절 상승 심근경색(STEMI) 프로토콜: 12유도 심전도 즉시 전송 및 헤파린/아스피린 지도의사 구두처방\n'
              '• 기도폐쇄 우려 시 비디오 후두경 삽관 준비 및 호기말이산화탄소(EtCO2) 모니터링',
              style: TextStyle(fontSize: 14, height: 1.8, color: Color(0xFF4B5563)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEpcrPlaceholder(EmsProvider ems) {
    return Center(
      child: Container(
        margin: const EdgeInsets.all(24),
        padding: const EdgeInsets.all(32),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppTheme.cardBorder),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.assignment_outlined, size: 36, color: Color(0xFF991B1B)),
                SizedBox(width: 12),
                Text(
                  'ePCR 구급활동일지 (실시간 자동 기록 중)',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
                ),
              ],
            ),
            const Divider(height: 28),
            Text(
              '• 환자명: ${ems.patient.name} (${ems.patient.gender}, ${ems.patient.age}세) | ID: ${ems.patient.id}\n'
              '• 출동대: 종로 704호 특수구급대 (김민우 1급 응급구조사 외 2인)\n'
              '• 수용병원: 서울대학교병원 권역외상센터 (확정)\n'
              '• 생체징후 기록: NIBP ${ems.patient.systolicBp}/${ems.patient.diastolicBp} mmHg, PR ${ems.patient.heartRate} BPM, SpO2 ${ems.patient.spo2}%\n'
              '• ECG 판독: Sinus Tachycardia with ST-Elevation (+2.1mm) 자동 전송 완료',
              style: const TextStyle(fontSize: 14, height: 1.8, color: Color(0xFF374151)),
            ),
          ],
        ),
      ),
    );
  }
}
