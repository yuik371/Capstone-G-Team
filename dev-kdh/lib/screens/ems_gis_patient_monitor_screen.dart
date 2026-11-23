import 'package:flutter/material.dart';
import '../widgets/treatment/patient_summary_bar.dart';
import '../widgets/treatment/avpu_selector.dart';
import '../widgets/treatment/vital_quad_grid.dart';
import '../widgets/treatment/live_ecg_monitor.dart';
import '../widgets/treatment/clinical_photos_widget.dart';
import '../widgets/dashboard/live_dispatch_card.dart';
import '../widgets/dashboard/cabin_sensors_card.dart';
import '../widgets/dashboard/dashboard_footer_bar.dart';

/// [응급 GIS 및 환자 실시간 모니터 탭]
/// 기존 화면 구성에서 네비게이션을 제외하고, 실시간 환자 생체 징후, 처치 현황,
/// 구급차 센서 및 출동 피드를 한눈에 확인할 수 있는 실시간 모니터링 탭
class EmsGisPatientMonitorScreen extends StatelessWidget {
  const EmsGisPatientMonitorScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: const [
          // 1. 상단 환자 인적/바이탈 서머리 바
          PatientSummaryBar(),
          SizedBox(height: 14),

          // 2. 상단 2열: 출동 피드 (좌) & 구급차 환경/센서 모니터 (우) (콜 페이지에서 이전됨)
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                flex: 7,
                child: LiveDispatchCard(),
              ),
              SizedBox(width: 14),
              Expanded(
                flex: 5,
                child: CabinSensorsCard(),
              ),
            ],
          ),
          SizedBox(height: 14),

          // 3. 환자 의식 상태 사정 (AVPU)
          AvpuSelector(),
          SizedBox(height: 14),

          // 4. 4분면 생체 징후 그리드 (NIBP, PR, SpO2, BT/RR)
          VitalQuadGrid(),
          SizedBox(height: 14),

          // 5. 실시간 애니메이션 심전도 모니터 (Lead II ST-Elevation)
          LiveEcgMonitor(),
          SizedBox(height: 14),

          // 6. 임상 외상 사진 및 12-유도 ECG 동기화
          ClinicalPhotosWidget(),
          SizedBox(height: 14),

          // 7. 하단 퀵 액션 바 (신속 임상 입력, PTT 핫라인, GCS 사정)
          DashboardFooterBar(),
        ],
      ),
    );
  }
}
