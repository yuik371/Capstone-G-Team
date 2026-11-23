import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/app_theme.dart';
import '../../models/hospital_model.dart';
import '../../providers/ems_provider.dart';

class RecommendedHospitalsSidebar extends StatelessWidget {
  const RecommendedHospitalsSidebar({super.key});

  @override
  Widget build(BuildContext context) {
    final ems = context.watch<EmsProvider>();
    final hospitals = ems.hospitals.take(3).toList();
    if (hospitals.isEmpty) return const SizedBox.shrink();

    final firstHosp = hospitals.first;

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ===================================================================
          // [1순위 병원 네비 안내 바로 시작 버튼]
          // ===================================================================
          SizedBox(
            width: double.infinity,
            height: 48,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF991B1B),
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
                elevation: 2,
              ),
              onPressed: () {
                // [요구사항]: 1순위 네비 안내 시작을 눌러야 실제 네비 가동
                ems.startNavigation(hospital: firstHosp);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text('1순위 추천 병원(${firstHosp.name}) 최단 경로 안내를 시작합니다.'),
                    backgroundColor: const Color(0xFF991B1B),
                    duration: const Duration(seconds: 2),
                  ),
                );
              },
              icon: const Icon(Icons.navigation_rounded, size: 20, color: Colors.amber),
              label: Text(
                '⚡ 1순위 (${firstHosp.name}) 네비 안내 시작',
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w900,
                  letterSpacing: -0.2,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ),
          const SizedBox(height: 12),

          // 헤더 라벨
          const Row(
            children: [
              Icon(Icons.local_hospital_outlined, color: Color(0xFF4B5563), size: 16),
              SizedBox(width: 6),
              Text(
                'AI 수용 적합도 추천 병원 (3곳)',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w800,
                  color: Color(0xFF1F2937),
                ),
              ),
              Spacer(),
              Text(
                '선택 시 경로 변경',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF6B7280),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),

          // 추천 병원 3곳 리스트
          Expanded(
            child: ListView.separated(
              itemCount: hospitals.length,
              separatorBuilder: (_, _) => const SizedBox(height: 10),
              itemBuilder: (context, idx) {
                final h = hospitals[idx];
                final isSelected = (ems.selectedHospital.name == h.name);
                return _buildHospitalCard(context, ems, h, idx, isSelected);
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHospitalCard(
    BuildContext context,
    EmsProvider ems,
    HospitalModel hospital,
    int index,
    bool isSelected,
  ) {
    Color badgeColor;
    String priorityText;
    if (index == 0) {
      priorityText = '1순위 최우선';
      badgeColor = const Color(0xFF991B1B);
    } else if (index == 1) {
      priorityText = '2순위 예비';
      badgeColor = const Color(0xFF0284C7);
    } else {
      priorityText = '3순위 예비';
      badgeColor = const Color(0xFF4B5563);
    }

    return InkWell(
      onTap: () {
        // 병원 카드 터치 시 목적지 및 지도 마커/경로 변경
        ems.selectHospital(hospital);
      },
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: isSelected ? const Color(0xFFFEF2F2) : const Color(0xFFF9FAFB),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? const Color(0xFF991B1B) : const Color(0xFFE5E7EB),
            width: isSelected ? 2.0 : 1.0,
          ),
          boxShadow: isSelected
              ? [
                  BoxShadow(
                    color: const Color(0xFF991B1B).withValues(alpha: 0.12),
                    blurRadius: 8,
                    offset: const Offset(0, 3),
                  ),
                ]
              : null,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 순위 배지 & 적합도 & 선택 상태
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: badgeColor,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    priorityText,
                    style: const TextStyle(
                      fontSize: 9,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                    ),
                  ),
                ),
                const SizedBox(width: 6),
                Text(
                  '적합도 ${hospital.suitabilityScore}%',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    color: badgeColor,
                  ),
                ),
                const Spacer(),
                if (isSelected && ems.isNavigationActive)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: const Color(0xFF991B1B),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Row(
                      children: [
                        Icon(Icons.navigation, color: Colors.white, size: 10),
                        SizedBox(width: 3),
                        Text(
                          '안내 중',
                          style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: Colors.white),
                        ),
                      ],
                    ),
                  )
                else if (isSelected && !ems.isNavigationActive)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: const Color(0xFF374151),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Text(
                      '선택됨',
                      style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: Colors.white),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 6),

            // 병원명
            Text(
              hospital.name,
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w900,
                color: isSelected ? const Color(0xFF991B1B) : const Color(0xFF111827),
                letterSpacing: -0.2,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 2),

            // 주소
            Text(
              hospital.address,
              style: const TextStyle(fontSize: 10, color: Color(0xFF6B7280)),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 6),

            // 거리 및 ETA / 병상 가용 상태
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF3F4F6),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    '거리 ${hospital.distance} · ETA ${hospital.eta}',
                    style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: Color(0xFF374151)),
                  ),
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    hospital.bedStatus['응급실 가용 상태'] ?? '가용',
                    style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: Color(0xFF059669)),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),

            // =================================================================
            // [병원 선택 후 네비 안내 시작 버튼] (네비 시작 전 해당 병원이 선택되었을 때)
            // =================================================================
            if (isSelected && !ems.isNavigationActive)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: SizedBox(
                  width: double.infinity,
                  height: 36,
                  child: ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF991B1B),
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                      padding: const EdgeInsets.symmetric(horizontal: 10),
                      elevation: 0,
                    ),
                    onPressed: () {
                      ems.startNavigation(hospital: hospital);
                    },
                    icon: const Icon(Icons.play_arrow_rounded, size: 18),
                    label: Text(
                      '${hospital.name} 네비 안내 시작',
                      style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w900),
                    ),
                  ),
                ),
              ),

            // =================================================================
            // [가시성 좋은 초록색 통화 버튼]
            // =================================================================
            SizedBox(
              width: double.infinity,
              height: 38,
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF059669), // 시인성 높은 녹색
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  elevation: 1,
                  padding: const EdgeInsets.symmetric(horizontal: 10),
                ),
                onPressed: () => _callHospital(context, hospital),
                icon: const Icon(Icons.phone_in_talk, size: 16),
                label: Text(
                  '📞 직통 전화 (${hospital.phone})',
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w900,
                    letterSpacing: -0.2,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _callHospital(BuildContext context, HospitalModel hospital) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: [
            const Icon(Icons.phone_forwarded, color: Color(0xFF059669), size: 24),
            const SizedBox(width: 8),
            Text(
              '${hospital.name} 직통 핫라인',
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '직통 전화번호: ${hospital.phone}',
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Color(0xFF059669)),
            ),
            const SizedBox(height: 8),
            const Text(
              '응급실 외상의과 수용 협의 및 환자 사전 인계를 위한 다이렉트 통화 연결 채널입니다.',
              style: TextStyle(fontSize: 12, color: Color(0xFF4B5563)),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('닫기'),
          ),
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF059669),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: () {
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('${hospital.name} (${hospital.phone}) 핫라인 통화 연결 시작'),
                  backgroundColor: const Color(0xFF059669),
                ),
              );
            },
            icon: const Icon(Icons.call, size: 16),
            label: const Text('통화 연결'),
          ),
        ],
      ),
    );
  }
}
