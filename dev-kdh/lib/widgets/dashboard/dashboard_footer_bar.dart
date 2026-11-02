import 'package:flutter/material.dart';
import '../../config/app_theme.dart';

class DashboardFooterBar extends StatelessWidget {
  const DashboardFooterBar({super.key});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 1. Rapid Clinical Entry
            Expanded(
              flex: 3,
              child: _buildFooterCard(
                child: const Row(
                  children: [
                    Icon(Icons.edit_note_rounded, color: Color(0xFF991B1B), size: 24),
                    SizedBox(width: 8),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            'RAPID CLINICAL ENTRY',
                            style: TextStyle(
                              fontSize: 9,
                              fontWeight: FontWeight.w700,
                              color: Color(0xFF9CA3AF),
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          Text(
                            '구급활동일지 즉시 열기',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w800,
                              color: Color(0xFF1F2937),
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                    Icon(Icons.chevron_right, color: Color(0xFF9CA3AF), size: 18),
                  ],
                ),
              ),
            ),
            const SizedBox(width: 10),

            // 2. Direct 1-Touch PTT
            Expanded(
              flex: 3,
              child: _buildFooterCard(
                child: Row(
                  children: [
                    Container(
                      width: 30,
                      height: 30,
                      decoration: const BoxDecoration(
                        color: Color(0xFF991B1B),
                        shape: BoxShape.circle,
                      ),
                      child: const Center(
                        child: Icon(Icons.headset_mic, color: Colors.white, size: 15),
                      ),
                    ),
                    const SizedBox(width: 8),
                    const Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            'DIRECT 1-TOUCH PTT',
                            style: TextStyle(
                              fontSize: 9,
                              fontWeight: FontWeight.w700,
                              color: Color(0xFF9CA3AF),
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          Text(
                            '지도의사 직통 핫라인',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w800,
                              color: Color(0xFF1F2937),
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                      decoration: BoxDecoration(
                        color: const Color(0xFFECFDF5),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.circle, color: Color(0xFF059669), size: 6),
                          SizedBox(width: 3),
                          Text(
                            '대기중',
                            style: TextStyle(
                              fontSize: 9,
                              fontWeight: FontWeight.w700,
                              color: Color(0xFF059669),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(width: 10),

            // 3. GCS Assessment & ECG
            Expanded(
              flex: 4,
              child: _buildFooterCard(
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        border: Border.all(color: const Color(0xFFFECACA)),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: const Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            'GCS',
                            style: TextStyle(fontSize: 8, fontWeight: FontWeight.w700, color: Color(0xFF9CA3AF)),
                          ),
                          Text(
                            '8T',
                            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w900, color: Color(0xFF991B1B)),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Text(
                            '환자 초기 중증도 평가',
                            style: TextStyle(fontSize: 8, fontWeight: FontWeight.w600, color: Color(0xFF6B7280)),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          Wrap(
                            crossAxisAlignment: WrapCrossAlignment.center,
                            spacing: 4,
                            children: [
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                                decoration: BoxDecoration(
                                  color: const Color(0xFF991B1B),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: const Text(
                                  'RED / 중증',
                                  style: TextStyle(fontSize: 8, fontWeight: FontWeight.w800, color: Colors.white),
                                ),
                              ),
                              const Text(
                                '기도확보 준비',
                                style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: Color(0xFF1F2937)),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 4),
                    const Icon(Icons.favorite_outline, color: Color(0xFF991B1B), size: 14),
                    const SizedBox(width: 4),
                    const Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          '심전도',
                          style: TextStyle(fontSize: 8, fontWeight: FontWeight.w600, color: Color(0xFF6B7280)),
                        ),
                        Text(
                          '118 BPM',
                          style: TextStyle(fontSize: 11, fontWeight: FontWeight.w900, color: Color(0xFF991B1B)),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildFooterCard({required Widget child}) {
    return Container(
      constraints: const BoxConstraints(minHeight: 56),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      alignment: Alignment.center,
      child: child,
    );
  }
}
