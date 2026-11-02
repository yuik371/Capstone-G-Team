import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/app_theme.dart';
import '../../providers/ems_provider.dart';

class PatientSummaryBar extends StatelessWidget {
  const PatientSummaryBar({super.key});

  @override
  Widget build(BuildContext context) {
    final ems = context.watch<EmsProvider>();
    final patient = ems.patient;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      child: FittedBox(
        fit: BoxFit.scaleDown,
        alignment: Alignment.centerLeft,
        child: Row(
          children: [
            // PRE-KTAS LEVEL 1 Badge
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: const Color(0xFF8B1515),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Row(
                children: [
                  const Icon(Icons.crisis_alert, color: Colors.white, size: 14),
                  const SizedBox(width: 6),
                  Text(
                    patient.ktasLevel,
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),

            // Patient Name & ID
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
              decoration: BoxDecoration(
                color: const Color(0xFFF3F4F6),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Row(
                children: [
                  const Text(
                    '이송 대상: ',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF6B7280),
                    ),
                  ),
                  Text(
                    '${patient.name} (${patient.gender}, ${patient.age}세)',
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w900,
                      color: Color(0xFF1F2937),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'ID: ${patient.id}',
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF9CA3AF),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 24),

            // Hospital Acceptance Confirmation Pill
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
              decoration: BoxDecoration(
                color: const Color(0xFFECFDF5),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: const Color(0xFFA7F3D0)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.circle, color: Color(0xFF059669), size: 8),
                  const SizedBox(width: 6),
                  Text(
                    '${patient.acceptanceHospital} ${patient.acceptanceBed}',
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w800,
                      color: Color(0xFF065F46),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 10),

            // Golden Time Countdown
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
              decoration: BoxDecoration(
                color: const Color(0xFFFEF2F2),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: const Color(0xFFFECACA)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.timer_outlined, color: Color(0xFF991B1B), size: 14),
                  const SizedBox(width: 6),
                  Text(
                    '골든타임 카운트 ${ems.formattedGoldenTime}',
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w800,
                      color: Color(0xFF991B1B),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
