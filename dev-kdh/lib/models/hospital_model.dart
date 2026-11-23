class HospitalModel {
  final int id;
  final String? hpid;
  final String? patientId;
  final String name;
  final String department;
  final String address;
  final String distance;
  final double distanceKm;
  final String eta;
  final int suitabilityScore;
  final double rawScore;
  final String statusTag;
  final bool isFirstPriority;
  final Map<String, String> bedStatus;
  final String phone;
  final double lat;
  final double lng;
  final bool erStatus;
  final bool orStatus;
  final String type;

  const HospitalModel({
    required this.id,
    this.hpid,
    this.patientId,
    required this.name,
    required this.department,
    required this.address,
    required this.distance,
    this.distanceKm = 0.0,
    required this.eta,
    required this.suitabilityScore,
    this.rawScore = 0.0,
    required this.statusTag,
    required this.isFirstPriority,
    required this.bedStatus,
    required this.phone,
    required this.lat,
    required this.lng,
    this.erStatus = true,
    this.orStatus = true,
    this.type = '종합병원',
  });

  /// /amb/emergency/call API 응답 아이템 파싱 팩토리
  factory HospitalModel.fromApiJson(
    Map<String, dynamic> json, {
    double? resolvedLat,
    double? resolvedLng,
    bool isFirstPriority = false,
  }) {
    final double rawScore = (json['score'] is num)
        ? (json['score'] as num).toDouble()
        : 0.0;
    final int scoreInt = rawScore.round();

    final double dist = (json['distance'] is num)
        ? (json['distance'] as num).toDouble()
        : 0.0;
    final String distStr = dist > 0 ? '${dist.toStringAsFixed(2)}km' : '1.2km';

    // 평균 구급차 주행 속도(약 40km/h) 기준 예상 소요 시간 계산
    final int etaMinutes = (dist * 2.2).clamp(2.0, 45.0).round();
    final String etaStr = '$etaMinutes분';

    final String name = json['name']?.toString() ?? '응급의료기관';
    final String addr = (json['address'] ?? json['addr'] ?? '').toString();
    final String phone = (json['number'] ?? '02-2001-2001').toString();
    final String type = (json['type'] ?? '종합병원').toString();
    final bool isEr = json['is_er'] == true;

    final int id = json['hospitalid'] is int
        ? json['hospitalid']
        : (json['hpid'] != null ? json['hpid'].hashCode.abs() % 100000 : 101);

    return HospitalModel(
      id: id,
      hpid: json['hpid']?.toString(),
      patientId: json['patientid']?.toString(),
      name: name,
      department: type,
      address: addr,
      distance: distStr,
      distanceKm: dist,
      eta: etaStr,
      suitabilityScore: scoreInt,
      rawScore: rawScore,
      statusTag: isFirstPriority
          ? '최우선 추천 ($scoreInt%)'
          : '수용 적합 ($scoreInt%)',
      isFirstPriority: isFirstPriority,
      bedStatus: {
        '응급실 가용 상태': isEr ? '가용 (입원 가능)' : '포화',
        '외상의과 팀': '즉시 대기',
        '긴급 CT/Angio': '룸 배정 가능',
      },
      phone: phone,
      lat: resolvedLat ?? 37.5684,
      lng: resolvedLng ?? 126.9678,
      erStatus: isEr,
      orStatus: true,
      type: type,
    );
  }

  static List<HospitalModel> getMockHospitals() {
    return [
      const HospitalModel(
        id: 101,
        hpid: 'A1100006',
        name: '강북삼성병원',
        department: '종합병원',
        address: '서울특별시 종로구 새문안로 29 (평동)',
        distance: '0.91km',
        distanceKm: 0.91,
        eta: '3분 20초',
        suitabilityScore: 96,
        rawScore: 95.8,
        statusTag: '원거리 사전 수용 통보 가능',
        isFirstPriority: true,
        bedStatus: {
          '응급소생실': '2석 가용',
          '외상의과 팀': '즉시 대기',
          '긴급 CT/Angio': '룸 배정 가능',
        },
        phone: '02-2001-2001',
        lat: 37.5684,
        lng: 126.9678,
        erStatus: true,
        orStatus: true,
        type: '종합병원',
      ),
      const HospitalModel(
        id: 102,
        hpid: 'A1100001',
        name: '서울대학교병원 권역응급의료센터',
        department: '권역외상센터',
        address: '서울특별시 종로구 대학로 101 (연건동)',
        distance: '2.80km',
        distanceKm: 2.8,
        eta: '5분 40초',
        suitabilityScore: 92,
        rawScore: 92.4,
        statusTag: '수용 적합 (92%)',
        isFirstPriority: false,
        bedStatus: {
          '외상중환자실 수용 상태': '가용 (입원 가능)',
          '구급차 대기 병목': '0건 (원활)',
        },
        phone: '02-2072-2474',
        lat: 37.5796,
        lng: 127.0000,
        erStatus: true,
        orStatus: true,
        type: '상급종합병원',
      ),
      const HospitalModel(
        id: 103,
        hpid: 'A1100010',
        name: '국립중앙의료원 권역외상센터',
        department: '권역외상센터',
        address: '서울특별시 중구 을지로 245',
        distance: '3.60km',
        distanceKm: 3.6,
        eta: '8분',
        suitabilityScore: 89,
        rawScore: 88.9,
        statusTag: '수용 양호 (89%)',
        isFirstPriority: false,
        bedStatus: {
          '외상중환자실 수용 상태': '가용 (입원 가능)',
          '구급차 대기 병목': '0건 (원활)',
        },
        phone: '02-2260-7114',
        lat: 37.5670,
        lng: 127.0055,
        erStatus: true,
        orStatus: true,
        type: '종합병원',
      ),
    ];
  }
}
