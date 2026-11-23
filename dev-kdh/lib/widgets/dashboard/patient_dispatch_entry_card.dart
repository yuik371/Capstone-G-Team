import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/app_theme.dart';
import '../../providers/ems_provider.dart';

class PatientDispatchEntryCard extends StatefulWidget {
  const PatientDispatchEntryCard({super.key});

  @override
  State<PatientDispatchEntryCard> createState() => _PatientDispatchEntryCardState();
}

class _PatientDispatchEntryCardState extends State<PatientDispatchEntryCard> {
  late TextEditingController _nameController;
  late TextEditingController _ageController;
  late TextEditingController _symptomController;
  String _selectedGender = '남';
  String _selectedKtas = 'KTAS 1급 (최중증·소생)';

  final List<String> _quickSymptoms = [
    '흉부 둔상 및 호흡 곤란 (KTAS 1급)',
    '심정지 (Cardiac Arrest / CPR)',
    '뇌졸중 의심 (FAST 양성)',
    '급성 흉통 (STEMI 의심)',
    '중증 복부 둔상 및 내부 출혈',
  ];

  @override
  void initState() {
    super.initState();
    final patient = context.read<EmsProvider>().patient;
    _nameController = TextEditingController(text: patient.name);
    _ageController = TextEditingController(text: patient.age.toString());
    _symptomController = TextEditingController(text: patient.symptom);
    _selectedGender = patient.gender;
  }

  @override
  void dispose() {
    _nameController.dispose();
    _ageController.dispose();
    _symptomController.dispose();
    super.dispose();
  }

  void _syncPatientData(EmsProvider ems) {
    ems.updatePatient(
      name: _nameController.text.trim().isNotEmpty ? _nameController.text.trim() : '무명 환자',
      age: int.tryParse(_ageController.text.trim()) ?? 60,
      gender: _selectedGender,
      ktasLevel: _selectedKtas,
      symptom: _symptomController.text.trim().isNotEmpty
          ? _symptomController.text.trim()
          : '흉부 둔상 및 호흡 곤란',
    );
  }

  @override
  Widget build(BuildContext context) {
    final ems = context.watch<EmsProvider>();
    final patient = ems.patient;

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.cardBorder),
        boxShadow: const [
          BoxShadow(
            color: Colors.black12,
            blurRadius: 10,
            offset: Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 상단 상태 타이틀 바
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFFFEF2F2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.assignment_ind_outlined, color: Color(0xFF991B1B), size: 22),
              ),
              const SizedBox(width: 12),
              const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '이송 환자 기본 정보 및 긴급 콜 요청',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w900,
                      color: Color(0xFF111827),
                    ),
                  ),
                  Text(
                    '구급차 생체 모니터 기기 연동 완료 (데이터 자동 반영됨)',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w500,
                      color: Color(0xFF059669),
                    ),
                  ),
                ],
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFFECFDF5),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: const Color(0xFFA7F3D0)),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.wifi_tethering, color: Color(0xFF059669), size: 14),
                    SizedBox(width: 6),
                    Text(
                      '구급 장비 실시간 수신 중',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF059669),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // 환자 정보 입력 폼 (이름, 나이, 성별, KTAS)
          Row(
            children: [
              // 1. 환자명
              Expanded(
                flex: 3,
                child: TextField(
                  controller: _nameController,
                  decoration: const InputDecoration(
                    labelText: '환자 이름',
                    prefixIcon: Icon(Icons.person_outline, size: 20),
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  ),
                  onChanged: (_) => _syncPatientData(ems),
                ),
              ),
              const SizedBox(width: 12),

              // 2. 나이
              Expanded(
                flex: 2,
                child: TextField(
                  controller: _ageController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: '나이 (세)',
                    prefixIcon: Icon(Icons.cake_outlined, size: 20),
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  ),
                  onChanged: (_) => _syncPatientData(ems),
                ),
              ),
              const SizedBox(width: 12),

              // 3. 성별 선택
              Expanded(
                flex: 2,
                child: Row(
                  children: [
                    Expanded(
                      child: ChoiceChip(
                        label: const Text('남성'),
                        selected: _selectedGender == '남',
                        onSelected: (val) {
                          setState(() => _selectedGender = '남');
                          _syncPatientData(ems);
                        },
                      ),
                    ),
                    const SizedBox(width: 4),
                    Expanded(
                      child: ChoiceChip(
                        label: const Text('여성'),
                        selected: _selectedGender == '여',
                        onSelected: (val) {
                          setState(() => _selectedGender = '여');
                          _syncPatientData(ems);
                        },
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),

              // 4. KTAS 중증도 등급
              Expanded(
                flex: 4,
                child: DropdownButtonFormField<String>(
                  initialValue: _selectedKtas,
                  decoration: const InputDecoration(
                    labelText: '중증도 (PRE-KTAS)',
                    prefixIcon: Icon(Icons.warning_amber_rounded, color: Color(0xFF991B1B), size: 20),
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 10),
                  ),
                  items: const [
                    DropdownMenuItem(value: 'KTAS 1급 (최중증·소생)', child: Text('KTAS 1급 (소생/심정지)')),
                    DropdownMenuItem(value: 'KTAS 2급 (중증·응급)', child: Text('KTAS 2급 (중증외상/뇌혈관)')),
                    DropdownMenuItem(value: 'KTAS 3급 (응급)', child: Text('KTAS 3급 (응급질환)')),
                    DropdownMenuItem(value: 'KTAS 4급 (준응급)', child: Text('KTAS 4급 (준응급)')),
                  ],
                  onChanged: (val) {
                    if (val != null) {
                      setState(() => _selectedKtas = val);
                      _syncPatientData(ems);
                    }
                  },
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),

          // 주증상 직접 입력 & 빠른 선택 칩
          TextField(
            controller: _symptomController,
            decoration: const InputDecoration(
              labelText: '주증상 및 현장 상황 (Symptom & On-Scene Findings)',
              prefixIcon: Icon(Icons.medical_information_outlined, size: 20),
              border: OutlineInputBorder(),
              contentPadding: EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            ),
            onChanged: (_) => _syncPatientData(ems),
          ),
          const SizedBox(height: 8),

          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: _quickSymptoms.map((s) {
              final isSelected = _symptomController.text == s;
              return ActionChip(
                label: Text(
                  s,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: isSelected ? FontWeight.w800 : FontWeight.w500,
                    color: isSelected ? const Color(0xFF991B1B) : const Color(0xFF374151),
                  ),
                ),
                backgroundColor: isSelected ? const Color(0xFFFEE2E2) : const Color(0xFFF3F4F6),
                side: BorderSide(color: isSelected ? const Color(0xFFF87171) : Colors.transparent),
                onPressed: () {
                  setState(() => _symptomController.text = s);
                  _syncPatientData(ems);
                },
              );
            }).toList(),
          ),
          const SizedBox(height: 16),

          // 연동된 생체 징후 바 (Telemetry Quick Status)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: const Color(0xFFF9FAFB),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0xFFE5E7EB)),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildVitalItem('혈압 (NIBP)', '${patient.systolicBp}/${patient.diastolicBp}', 'mmHg', Colors.red.shade700),
                _buildVitalItem('맥박 (PR)', '${patient.heartRate}', 'BPM', Colors.blue.shade700),
                _buildVitalItem('산소포화도 (SpO2)', '${patient.spo2}', '%', Colors.teal.shade700),
                _buildVitalItem('체온 (BT)', '${patient.bodyTemp}', '℃', Colors.deepOrange.shade700),
                _buildVitalItem('의식 (AVPU)', patient.avpu, 'Scale', Colors.purple.shade700),
              ],
            ),
          ),
          const SizedBox(height: 20),

          // ===================================================================
          // [핵심 버튼]: 긴급 콜 버튼 (amb/emergency/call 호출 및 추천 병원 리스트 반영)
          // ===================================================================
          SizedBox(
            width: double.infinity,
            height: 60,
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF991B1B),
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                elevation: 4,
                shadowColor: const Color(0xFF991B1B).withValues(alpha: 0.5),
              ),
              onPressed: ems.isLoadingHospitals
                  ? null
                  : () async {
                      _syncPatientData(ems);
                      await ems.sendEmergencyCallAndNavigate();
                    },
              child: ems.isLoadingHospitals
                  ? const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        SizedBox(
                          width: 24,
                          height: 24,
                          child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2.5),
                        ),
                        SizedBox(width: 14),
                        Text(
                          'AI 최적 병원 분석 및 실시간 병상 조회 중...',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                      ],
                    )
                  : const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.local_fire_department, size: 28, color: Colors.amber),
                        SizedBox(width: 10),
                        Text(
                          '🚨 긴급 콜 발송 및 AI 병원 추천 조회 (/amb/emergency/call)',
                          style: TextStyle(
                            fontSize: 17,
                            fontWeight: FontWeight.w900,
                            letterSpacing: -0.2,
                          ),
                        ),
                        SizedBox(width: 8),
                        Icon(Icons.arrow_forward_rounded, size: 24),
                      ],
                    ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildVitalItem(String label, String value, String unit, Color color) {
    return Column(
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: Color(0xFF6B7280)),
        ),
        const SizedBox(height: 2),
        RichText(
          text: TextSpan(
            text: value,
            style: TextStyle(fontSize: 14, fontWeight: FontWeight.w900, color: color),
            children: [
              TextSpan(
                text: ' $unit',
                style: const TextStyle(fontSize: 9, fontWeight: FontWeight.normal, color: Color(0xFF9CA3AF)),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
