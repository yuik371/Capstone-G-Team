import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/app_theme.dart';
import '../../providers/ems_provider.dart';

class ClinicalPhotosWidget extends StatelessWidget {
  const ClinicalPhotosWidget({super.key});

  @override
  Widget build(BuildContext context) {
    final ems = context.watch<EmsProvider>();
    final photos = ems.patient.clinicalPhotos;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header Row
          const Row(
            children: [
              Icon(Icons.photo_camera_outlined, color: Color(0xFF4B5563), size: 16),
              SizedBox(width: 8),
              Text(
                '임상 사진 및 응급의료센터 동기화',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w800,
                  color: Color(0xFF1F2937),
                ),
              ),
              Spacer(),
              Icon(Icons.cloud_done_outlined, color: Color(0xFF059669), size: 16),
              SizedBox(width: 4),
              Text(
                '응급실 모니터 실시간 공유 완료',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                  color: Color(0xFF059669),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),

          // Photos Row
          Row(
            children: [
              // Photo 1: Blunt Chest Trauma (Simulated Medical View)
              Expanded(
                child: _buildPhotoThumbnail(
                  context: context,
                  title: photos.isNotEmpty ? photos[0].title : '흉부 둔상 부위 (05:32)',
                  badge: null,
                  customPreview: _buildChestInjuryMock(),
                ),
              ),
              const SizedBox(width: 10),

              // Photo 2: 12-Lead ECG Strip
              Expanded(
                child: _buildPhotoThumbnail(
                  context: context,
                  title: photos.length > 1 ? photos[1].title : '12유도 심전도 전송',
                  badge: '12-LEAD',
                  customPreview: _build12LeadEcgMock(),
                ),
              ),
              const SizedBox(width: 10),

              // Action Card: + 환부 추가 촬영 (Camera Action)
              Expanded(
                child: _buildAddPhotoCard(context, ems),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPhotoThumbnail({
    required BuildContext context,
    required String title,
    String? badge,
    required Widget customPreview,
  }) {
    return Container(
      height: 90,
      decoration: BoxDecoration(
        color: const Color(0xFF111827),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF374151)),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(10),
        child: Stack(
          children: [
            // Preview background
            Positioned.fill(child: customPreview),

            // Top Badge if any
            if (badge != null)
              Positioned(
                top: 6,
                right: 6,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                  decoration: BoxDecoration(
                    color: const Color(0xFF991B1B),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    badge,
                    style: const TextStyle(
                      fontSize: 8,
                      fontWeight: FontWeight.w900,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),

            // Bottom Title Bar
            Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                color: Colors.black.withValues(alpha: 0.75),
                child: Text(
                  title,
                  style: const TextStyle(
                    fontSize: 9,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildChestInjuryMock() {
    return Container(
      color: const Color(0xFF2E2620),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.healing, color: Colors.amber.shade200, size: 28),
            const SizedBox(height: 2),
            const Text(
              'CHEST DRESSING',
              style: TextStyle(
                fontSize: 8,
                fontWeight: FontWeight.w700,
                color: Colors.white70,
                letterSpacing: 0.5,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _build12LeadEcgMock() {
    return Container(
      color: const Color(0xFF0F172A),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.show_chart, color: Color(0xFF38BDF8), size: 28),
            const SizedBox(height: 2),
            Text(
              '12-LEAD TELEMETRY',
              style: TextStyle(
                fontSize: 8,
                fontWeight: FontWeight.w700,
                color: Colors.cyan.shade200,
                letterSpacing: 0.5,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAddPhotoCard(BuildContext context, EmsProvider ems) {
    return InkWell(
      onTap: () => _showAddPhotoDialog(context, ems),
      borderRadius: BorderRadius.circular(10),
      child: Container(
        height: 90,
        decoration: BoxDecoration(
          color: const Color(0xFFF9FAFB),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: const Color(0xFFD1D5DB),
            style: BorderStyle.solid,
            width: 1.2,
          ),
        ),
        child: const Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.add_a_photo_outlined, color: Color(0xFF991B1B), size: 22),
            SizedBox(height: 4),
            Text(
              '환부 추가 촬영',
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w800,
                color: Color(0xFF1F2937),
              ),
            ),
            SizedBox(height: 2),
            Text(
              '+ AUTO ER SYNC',
              style: TextStyle(
                fontSize: 8,
                fontWeight: FontWeight.w700,
                color: Color(0xFF9CA3AF),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showAddPhotoDialog(BuildContext context, EmsProvider ems) {
    final titleController = TextEditingController(text: '우측 하지 열상 부위');

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        title: const Row(
          children: [
            Icon(Icons.camera_alt, color: Color(0xFF991B1B), size: 22),
            SizedBox(width: 8),
            Text(
              '환부 사진 촬영 및 ER 전송',
              style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              '촬영 부위 설명 및 메모:',
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF4B5563)),
            ),
            const SizedBox(height: 6),
            TextField(
              controller: titleController,
              decoration: InputDecoration(
                filled: true,
                fillColor: const Color(0xFFF9FAFB),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              ),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFFEF2F2),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Row(
                children: [
                  Icon(Icons.cloud_upload_outlined, color: Color(0xFF991B1B), size: 18),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '촬영 즉시 서울대병원 외상센터 EMR 및 모니터로 암호화 자동 전송됩니다.',
                      style: TextStyle(fontSize: 11, color: Color(0xFF991B1B), height: 1.3),
                    ),
                  ),
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
              backgroundColor: const Color(0xFF991B1B),
              foregroundColor: Colors.white,
            ),
            onPressed: () {
              final text = titleController.text.trim();
              if (text.isNotEmpty) {
                ems.addClinicalPhoto('$text (추가)', '05:38');
              }
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('환부 사진이 서울대병원 응급실로 실시간 전송되었습니다.'),
                  backgroundColor: Color(0xFF059669),
                ),
              );
            },
            child: const Text('촬영 및 전송'),
          ),
        ],
      ),
    );
  }
}
