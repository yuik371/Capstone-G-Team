import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/app_theme.dart';
import '../../providers/ems_provider.dart';

class AvpuSelector extends StatelessWidget {
  const AvpuSelector({super.key});

  @override
  Widget build(BuildContext context) {
    final ems = context.watch<EmsProvider>();
    final currentAvpu = ems.patient.avpu;

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
              Icon(Icons.psychology_alt_outlined, color: Color(0xFF991B1B), size: 18),
              SizedBox(width: 8),
              Text(
                '의식 수준 척도 (AVPU SCALE)',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w800,
                  color: Color(0xFF1F2937),
                ),
              ),
              Spacer(),
              Text(
                '글러브 터치 패드 적용',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF9CA3AF),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),

          // 4 Big Glove-Friendly Buttons
          Row(
            children: [
              Expanded(
                child: _buildAvpuButton(
                  context: context,
                  code: 'A',
                  title: 'Alert (명료)',
                  isSelected: currentAvpu == 'A',
                  onTap: () => ems.setAvpu('A'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _buildAvpuButton(
                  context: context,
                  code: 'V',
                  title: 'Verbal (언어응답)',
                  isSelected: currentAvpu == 'V',
                  onTap: () => ems.setAvpu('V'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _buildAvpuButton(
                  context: context,
                  code: 'P',
                  title: 'Pain (통증반응)',
                  isSelected: currentAvpu == 'P',
                  onTap: () => ems.setAvpu('P'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _buildAvpuButton(
                  context: context,
                  code: 'U',
                  title: 'Unresponsive (무반응)',
                  isSelected: currentAvpu == 'U',
                  onTap: () => ems.setAvpu('U'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildAvpuButton({
    required BuildContext context,
    required String code,
    required String title,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: isSelected ? const Color(0xFF8B1515) : const Color(0xFFF9FAFB),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: isSelected ? const Color(0xFF8B1515) : const Color(0xFFE5E7EB),
            width: isSelected ? 1.5 : 1.0,
          ),
          boxShadow: isSelected
              ? [
                  BoxShadow(
                    color: const Color(0xFF8B1515).withValues(alpha: 0.25),
                    blurRadius: 8,
                    offset: const Offset(0, 3),
                  ),
                ]
              : null,
        ),
        child: Column(
          children: [
            Text(
              code,
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w900,
                color: isSelected ? Colors.white : const Color(0xFF374151),
              ),
            ),
            const SizedBox(height: 2),
            Text(
              title,
              style: TextStyle(
                fontSize: 10,
                fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                color: isSelected ? Colors.white.withValues(alpha: 0.9) : const Color(0xFF6B7280),
              ),
              textAlign: TextAlign.center,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }
}
