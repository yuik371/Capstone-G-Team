import 'package:flutter/material.dart';
import '../widgets/dashboard/patient_dispatch_entry_card.dart';

/// [응급 이송 콜 탭]
/// 오로지 응급 이송 콜(환자 정보 입력 및 amb/emergency/call 발송)에 관한 기능만 집중된 화면
class EmsStartDashboard extends StatelessWidget {
  const EmsStartDashboard({super.key});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 1000),
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 헤더 안내 바
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF991B1B), Color(0xFF7F1D1D)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(14),
                  boxShadow: const [
                    BoxShadow(color: Colors.black12, blurRadius: 6, offset: Offset(0, 3)),
                  ],
                ),
                child: const Row(
                  children: [
                    CircleAvatar(
                      radius: 24,
                      backgroundColor: Colors.white24,
                      child: Icon(Icons.emergency, color: Colors.white, size: 28),
                    ),
                    SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '119 EMS 응급 이송 콜 관제',
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.w900,
                              color: Colors.white,
                              letterSpacing: -0.3,
                            ),
                          ),
                          SizedBox(height: 3),
                          Text(
                            '구급차 생체 모니터 연동 데이터를 확인하고 긴급 콜을 발송하여 AI 최적 응급의료센터를 추천받습니다.',
                            style: TextStyle(fontSize: 11, color: Colors.white70),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 18),

              // [오로지 응급 이송 콜에 관한 핵심 기능]: 환자 정보 입력 폼 및 긴급 콜 발송 카드
              const PatientDispatchEntryCard(),
            ],
          ),
        ),
      ),
    );
  }
}
