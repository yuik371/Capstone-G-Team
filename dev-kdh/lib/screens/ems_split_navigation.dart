import 'package:flutter/material.dart';
import '../widgets/treatment/patient_summary_bar.dart';
import '../widgets/navigation/recommended_hospitals_sidebar.dart';
import '../widgets/navigation/hospital_destination_card.dart';
import '../widgets/navigation/green_wave_banner.dart';
import '../widgets/navigation/emergency_map_view.dart';
import '../widgets/navigation/navigation_bottom_bar.dart';

class EmsSplitNavigation extends StatelessWidget {
  const EmsSplitNavigation({super.key});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 1. 상단 환자 정보 요약 바
          const PatientSummaryBar(),
          const SizedBox(height: 12),

          // 2. 메인 스플릿 영역: 좌측 (사이드 추천 병원 3곳 & 직통 전화) & 우측 (네비게이션 지도 & 인계)
          Expanded(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // 좌측 사이드: 추천 병원 3곳 카드 + 1순위 즉시 안내 버튼 + 가시성 좋은 통화 버튼
                const SizedBox(
                  width: 360,
                  child: RecommendedHospitalsSidebar(),
                ),
                const SizedBox(width: 14),

                // 우측 메인: 목적지 병원 헤더 + 긴급 신호 배너 + 지도 경로 + 하단 인계/종료 바
                Expanded(
                  child: Column(
                    children: const [
                      // 선택 확정된 병원 목적지 카드
                      HospitalDestinationCard(),
                      SizedBox(height: 10),

                      // Green Wave & 긴급 우선통행 경로 배너
                      GreenWaveBanner(),
                      SizedBox(height: 10),

                      // OpenStreetMap 대화형 지도 (OSRM 최단 도로망 Polyline 및 실시간 구급차 위치)
                      Expanded(
                        child: EmergencyMapView(),
                      ),
                      SizedBox(height: 10),

                      // 하단 지도의사 처방 및 병원 도착/환자 인계서 전송 (출동 임무 종료) 바
                      NavigationBottomBar(),
                    ],
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
