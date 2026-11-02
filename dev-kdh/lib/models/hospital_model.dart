class HospitalModel {
  final int id;
  final String name;
  final String department;
  final String address;
  final String distance;
  final String eta;
  final int suitabilityScore;
  final String statusTag;
  final bool isFirstPriority;
  final Map<String, String> bedStatus;
  final String phone;
  final double lat;
  final double lng;
  final bool erStatus;
  final bool orStatus;

  const HospitalModel({
    required this.id,
    required this.name,
    required this.department,
    required this.address,
    required this.distance,
    required this.eta,
    required this.suitabilityScore,
    required this.statusTag,
    required this.isFirstPriority,
    required this.bedStatus,
    required this.phone,
    required this.lat,
    required this.lng,
    this.erStatus = true,
    this.orStatus = true,
  });

  static List<HospitalModel> getMockHospitals() {
    return [
      const HospitalModel(
        id: 101,
        name: '서울대학교병원 권역응급의료센터',
        department: '권역외상센터',
        address: '서울특별시 종로구 대학로 101 (연건동)',
        distance: '2.8km',
        eta: '5분 40초',
        suitabilityScore: 98,
        statusTag: '원거리 사전 수용 통보 가능',
        isFirstPriority: true,
        bedStatus: {
          '응급소생실': '2석 가용',
          '외상의과 팀': '즉시 대기',
          '긴급 CT/Angio': '룸 배정 가능',
        },
        phone: '02-2072-2474',
        lat: 37.5796,
        lng: 127.0000,
        erStatus: true,
        orStatus: true,
      ),
      const HospitalModel(
        id: 102,
        name: '국립중앙의료원 권역외상센터',
        department: '권역외상센터',
        address: '서울특별시 중구 을지로 245',
        distance: '3.6km',
        eta: '8분',
        suitabilityScore: 89,
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
      ),
    ];
  }
}
