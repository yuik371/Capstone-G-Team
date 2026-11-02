import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/ems_provider.dart';

class NavigationBottomBar extends StatelessWidget {
  const NavigationBottomBar({super.key});

  @override
  Widget build(BuildContext context) {
    final ems = context.watch<EmsProvider>();

    return Row(
      children: [
        // 1. Direct Medical Consultation Order Button
        Container(
          height: 48,
          padding: const EdgeInsets.symmetric(horizontal: 10),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: const Color(0xFFE5E7EB)),
          ),
          child: InkWell(
            onTap: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('지도의사 음성 처방 녹음 및 자동 EMR 기록 채널 개통'),
                  backgroundColor: Color(0xFF1F2937),
                ),
              );
            },
            child: const Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                CircleAvatar(
                  radius: 12,
                  backgroundColor: Color(0xFFF3F4F6),
                  child: Icon(Icons.record_voice_over_outlined, color: Color(0xFF4B5563), size: 14),
                ),
                SizedBox(width: 6),
                Text(
                  '지도의사 처방',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF374151),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(width: 8),

        // 2. Transfer Protocol Critical Handover Button
        Expanded(
          child: InkWell(
            onTap: () => _showHandoverDialog(context, ems),
            borderRadius: BorderRadius.circular(10),
            child: Container(
              height: 48,
              padding: const EdgeInsets.symmetric(horizontal: 14),
              decoration: BoxDecoration(
                color: const Color(0xFF8B1515),
                borderRadius: BorderRadius.circular(10),
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFF8B1515).withValues(alpha: 0.35),
                    blurRadius: 8,
                    offset: const Offset(0, 3),
                  ),
                ],
              ),
              child: const Row(
                children: [
                  Icon(Icons.assignment_turned_in_outlined, color: Colors.white, size: 20),
                  SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          'TRANSFER PROTOCOL',
                          style: TextStyle(
                            fontSize: 8,
                            fontWeight: FontWeight.w800,
                            color: Colors.white70,
                            letterSpacing: 0.5,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        Text(
                          '병원 도착 및 환자 인계서 전송 →',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w900,
                            color: Colors.white,
                            letterSpacing: -0.2,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  void _showHandoverDialog(BuildContext context, EmsProvider ems) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Row(
          children: [
            Icon(Icons.check_circle, color: Color(0xFF059669), size: 28),
            SizedBox(width: 10),
            Text(
              '환자 인계 및 도착 확정',
              style: TextStyle(fontWeight: FontWeight.w900, fontSize: 18),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${ems.patient.name} (${ems.patient.gender}, ${ems.patient.age}세) 환자를 서울대학교병원 권역외상센터 외상의과팀에 최종 인계하시겠습니까?',
              style: const TextStyle(fontSize: 14, height: 1.5),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFF9FAFB),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: const Color(0xFFE5E7EB)),
              ),
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('• 활력징후 및 심전도 데이터 자동 ePCR 기록 완료', style: TextStyle(fontSize: 12)),
                  SizedBox(height: 4),
                  Text('• 12유도 ECG 및 외상 사진 서울대 EMR 연동 완료', style: TextStyle(fontSize: 12)),
                  SizedBox(height: 4),
                  Text('• 구급대 출동 종료 및 복귀 대기 전환', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: Color(0xFF059669))),
                ],
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('취소', style: TextStyle(color: Colors.grey)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF059669),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: () {
              Navigator.pop(ctx);
              // [API 연동 포인트: POST /patient/handover]
              ems.completeHandover();
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('환자 인계서 전송 완료: 종로 704호 구급대 출동 임무 종료'),
                  backgroundColor: Color(0xFF059669),
                ),
              );
            },
            child: const Text('인계 완료 및 전송', style: TextStyle(fontWeight: FontWeight.w800)),
          ),
        ],
      ),
    );
  }
}
