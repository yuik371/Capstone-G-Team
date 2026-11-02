class ClinicalPhotoItem {
  final String title;
  final String time;
  final String? badge;
  final String? imageUrl;
  final bool isSample;

  const ClinicalPhotoItem({
    required this.title,
    required this.time,
    this.badge,
    this.imageUrl,
    this.isSample = true,
  });
}

class PatientModel {
  final String id;
  final String name;
  final int age;
  final String gender;
  final String ktasLevel;
  final String avpu; // 'A', 'V', 'P', 'U'

  // Vitals
  final int systolicBp;
  final int diastolicBp;
  final int mapBp;
  final int heartRate;
  final int rrIntervalMs;
  final int spo2;
  final double bodyTemp;
  final int respRate;

  // Status notes
  final String acceptanceHospital;
  final String acceptanceBed;
  final int goldenTimeSeconds; // Remaining golden time (e.g. 1104s = 18m 24s)
  final List<ClinicalPhotoItem> clinicalPhotos;

  const PatientModel({
    required this.id,
    required this.name,
    required this.age,
    required this.gender,
    required this.ktasLevel,
    required this.avpu,
    required this.systolicBp,
    required this.diastolicBp,
    required this.mapBp,
    required this.heartRate,
    required this.rrIntervalMs,
    required this.spo2,
    required this.bodyTemp,
    required this.respRate,
    required this.acceptanceHospital,
    required this.acceptanceBed,
    required this.goldenTimeSeconds,
    required this.clinicalPhotos,
  });

  PatientModel copyWith({
    String? avpu,
    int? systolicBp,
    int? diastolicBp,
    int? mapBp,
    int? heartRate,
    int? spo2,
    double? bodyTemp,
    int? respRate,
    int? goldenTimeSeconds,
    List<ClinicalPhotoItem>? clinicalPhotos,
  }) {
    return PatientModel(
      id: id,
      name: name,
      age: age,
      gender: gender,
      ktasLevel: ktasLevel,
      avpu: avpu ?? this.avpu,
      systolicBp: systolicBp ?? this.systolicBp,
      diastolicBp: diastolicBp ?? this.diastolicBp,
      mapBp: mapBp ?? this.mapBp,
      heartRate: heartRate ?? this.heartRate,
      rrIntervalMs: rrIntervalMs,
      spo2: spo2 ?? this.spo2,
      bodyTemp: bodyTemp ?? this.bodyTemp,
      respRate: respRate ?? this.respRate,
      acceptanceHospital: acceptanceHospital,
      acceptanceBed: acceptanceBed,
      goldenTimeSeconds: goldenTimeSeconds ?? this.goldenTimeSeconds,
      clinicalPhotos: clinicalPhotos ?? this.clinicalPhotos,
    );
  }

  static PatientModel createInitialMock() {
    return const PatientModel(
      id: 'PT-2024-8841',
      name: '김영수',
      age: 62,
      gender: '남',
      ktasLevel: 'PRE-KTAS LEVEL 1 (중증외상·심혈관)',
      avpu: 'V', // Verbal (언어응답)
      systolicBp: 85,
      diastolicBp: 55,
      mapBp: 65,
      heartRate: 118,
      rrIntervalMs: 508,
      spo2: 92,
      bodyTemp: 36.1,
      respRate: 24,
      acceptanceHospital: '서울대병원 ER',
      acceptanceBed: '외상소생 1베이 확정 수용',
      goldenTimeSeconds: 18 * 60 + 24, // 18분 24초
      clinicalPhotos: [
        ClinicalPhotoItem(
          title: '흉부 둔상 부위 (05:32)',
          time: '05:32',
          badge: null,
        ),
        ClinicalPhotoItem(
          title: '12유도 심전도 전송',
          time: '05:34',
          badge: '12-LEAD',
        ),
      ],
    );
  }
}
