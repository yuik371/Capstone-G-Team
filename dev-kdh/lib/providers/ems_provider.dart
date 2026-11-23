import 'dart:async';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:latlong2/latlong.dart';
import '../models/hospital_model.dart';
import '../models/patient_model.dart';
import '../models/navigation_model.dart';
import '../services/api_service.dart';

enum EmsView {
  dashboard, // 119 EMS 응급 이송 콜 (환자 정보 입력 및 긴급 콜 발송)
  splitNavigation, // 119 EMS 추천 병원 3곳 및 네비게이션 지도 화면
}

class EmsProvider extends ChangeNotifier {
  EmsView _currentView = EmsView.dashboard;
  int _selectedSidebarIndex = 0; // 0: 응급 이송 콜, 1: GIS/환자모니터, 2: 지침/약물, 3: ePCR

  bool _isAuthenticated = false;
  String _userId = '김민우 반장';
  String _userRole = 'ems';

  late List<HospitalModel> _hospitals;
  late HospitalModel _selectedHospital;
  late PatientModel _patient;
  late NavigationModel _navigation;

  Timer? _tickerTimer;
  String _currentTimeString = '14:28:19 KST';
  int _goldenTimeSeconds = 18 * 60 + 24; // 18분 24초
  int _etaSeconds = 5 * 60 + 42; // 05분 42초
  double _routeProgress = 0.08; // 0.0 to 1.0 along the waypoints
  bool _isTransferActive = false; // 긴급 콜 발송 후 추천 병원/네비 화면 진입 여부
  bool _isNavigationActive = false; // 실제 경로 안내 시작 여부 (안내 시작 버튼을 눌러야 활성화)

  EmsProvider() {
    _hospitals = HospitalModel.getMockHospitals();
    _selectedHospital = _hospitals.first;
    _patient = PatientModel.createInitialMock();
    _navigation = NavigationModel.createInitialMock();
    _startLiveTicker();
  }

  bool get isAuthenticated => _isAuthenticated;
  String get userId => _userId;
  String get userRole => _userRole;

  void loginUser(String userid, {String role = 'ems'}) {
    _isAuthenticated = true;
    _userId = userid;
    _userRole = role;
    notifyListeners();
  }

  void logoutUser() {
    _isAuthenticated = false;
    _isTransferActive = false;
    _isNavigationActive = false;
    _currentView = EmsView.dashboard;
    _selectedSidebarIndex = 0;
    ApiService.logout();
    notifyListeners();
  }

  EmsView get currentView => _currentView;
  int get selectedSidebarIndex => _selectedSidebarIndex;
  List<HospitalModel> get hospitals => _hospitals;
  HospitalModel get selectedHospital => _selectedHospital;
  PatientModel get patient => _patient;
  NavigationModel get navigation => _navigation;
  String get currentTimeString => _currentTimeString;
  int get goldenTimeSeconds => _goldenTimeSeconds;
  int get etaSeconds => _etaSeconds;
  bool get isTransferActive => _isTransferActive;
  bool get isNavigationActive => _isNavigationActive;

  String get formattedGoldenTime {
    final m = (_goldenTimeSeconds ~/ 60).toString().padLeft(2, '0');
    final s = (_goldenTimeSeconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  String get formattedEta {
    final m = (_etaSeconds ~/ 60).toString().padLeft(2, '0');
    final s = (_etaSeconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  // ===========================================================================
  // [환자 정보 동적 업데이트 (구급차 기기 연동 및 직접 입력)]
  // ===========================================================================
  void updatePatient({
    String? name,
    int? age,
    String? gender,
    String? ktasLevel,
    String? symptom,
    int? systolicBp,
    int? diastolicBp,
    int? heartRate,
    int? spo2,
    double? bodyTemp,
    int? respRate,
  }) {
    _patient = _patient.copyWith(
      name: name,
      age: age,
      gender: gender,
      ktasLevel: ktasLevel,
      symptom: symptom,
      systolicBp: systolicBp,
      diastolicBp: diastolicBp,
      heartRate: heartRate,
      spo2: spo2,
      bodyTemp: bodyTemp,
      respRate: respRate,
    );
    notifyListeners();
  }

  // ===========================================================================
  // [API 연동 1: POST /amb/emergency/call 구급 콜 및 추천 병원 목록 조회]
  // ===========================================================================
  bool _isLoadingHospitals = false;
  bool get isLoadingHospitals => _isLoadingHospitals;

  /// [핵심 워크플로우 1]: 긴급 콜 버튼 터치 시 호출 -> 병원 추천 리스트(3곳) 반영 후 네비 대기 화면으로 전환
  Future<void> sendEmergencyCallAndNavigate() async {
    _isLoadingHospitals = true;
    notifyListeners();

    try {
      final List<HospitalModel> list = await ApiService.sendEmergencyCall(
        name: _patient.name,
        age: _patient.age.toString(),
        symptom: _patient.symptom,
        lat: _navigation.currentAmbulanceLocation.latitude,
        lon: _navigation.currentAmbulanceLocation.longitude,
      );

      if (list.isNotEmpty) {
        _hospitals = list;
        _selectedHospital = list.first;
      }
    } catch (e) {
      debugPrint('[EMS PROVIDER] sendEmergencyCallAndNavigate 오류: $e');
    } finally {
      _isLoadingHospitals = false;
    }

    _isTransferActive = true;
    _isNavigationActive = false; // [요구사항]: 네비는 안내 시작 버튼을 눌러야 시작됨!
    _currentView = EmsView.splitNavigation;
    _selectedSidebarIndex = 0;

    // 네비 시작 전에는 지도에 병원 3곳의 마커만 표시하기 위해 경로선은 비워둠
    _navigation = _navigation.copyWith(
      destinationHospitalLocation: LatLng(_selectedHospital.lat, _selectedHospital.lng),
      routeWaypoints: [],
      nextTurnInstruction: '병원 선택 후 "네비 안내 시작" 버튼을 터치하십시오.',
    );

    notifyListeners();
  }

  /// [핵심 워크플로우 2]: 1순위 또는 선택 병원의 "네비 안내 시작" 버튼 터치 시 실제 경로 안내 가동
  Future<void> startNavigation({HospitalModel? hospital}) async {
    if (hospital != null) {
      _selectedHospital = hospital;
    }
    _isNavigationActive = true;
    await _updateRouteForSelectedHospital();

    // 수용 요청 통보
    ApiService.sendPatientTransferRequest(
      hospital: _selectedHospital,
      patient: _patient,
      ambId: 'AMB-704',
    );

    notifyListeners();
  }

  /// [핵심 워크플로우 3]: 사이드 추천 병원 선택 시 해당 병원으로 네비 경로 변경
  Future<void> selectHospital(HospitalModel hospital) async {
    _selectedHospital = hospital;

    if (_isNavigationActive) {
      // 이미 네비 안내가 켜져 있는 상태라면 바로 새 병원 도로망 최단 경로로 갱신
      await _updateRouteForSelectedHospital();
      ApiService.sendPatientTransferRequest(
        hospital: hospital,
        patient: _patient,
        ambId: 'AMB-704',
      );
    } else {
      // 네비 시작 전이면 목적지 위치만 맞춤
      _navigation = _navigation.copyWith(
        destinationHospitalLocation: LatLng(hospital.lat, hospital.lng),
        nextTurnInstruction: '${hospital.name} 선택됨 ("네비 안내 시작"을 눌러 출발)',
      );
    }

    notifyListeners();
  }

  /// 선택된 병원의 위치에 맞춰 OSRM 최단 경로 및 네비게이션 정보를 갱신합니다.
  Future<void> _updateRouteForSelectedHospital() async {
    final hospLocation = LatLng(_selectedHospital.lat, _selectedHospital.lng);
    final List<LatLng> route = await ApiService.fetchDrivingRoute(
      origin: _navigation.currentAmbulanceLocation,
      destination: hospLocation,
    );

    _routeProgress = 0.05;
    final distKm = _selectedHospital.distance;
    final etaText = _selectedHospital.eta;

    _navigation = NavigationModel(
      nextTurnInstruction: '250m 앞 직진 후 ${_selectedHospital.name} 방면 진입',
      greenWaveStatus: '스마트 긴급신호(Green Wave) 가동: 경로 연동 완료',
      currentSpeedKmH: 64,
      etaText: etaText,
      etaRemainingSeconds: _etaSeconds,
      remainingDistanceKm: distKm,
      roadName: _selectedHospital.address,
      coordinatesText: '구급차 위치 (${_navigation.currentAmbulanceLocation.latitude.toStringAsFixed(4)}, ${_navigation.currentAmbulanceLocation.longitude.toStringAsFixed(4)})',
      currentAmbulanceLocation: _navigation.currentAmbulanceLocation,
      destinationHospitalLocation: hospLocation,
      routeWaypoints: route,
    );
    notifyListeners();
  }

  void _startLiveTicker() {
    _tickerTimer?.cancel();
    _tickerTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      final now = DateTime.now();
      _currentTimeString = '${DateFormat('HH:mm:ss').format(now)} KST';

      if (_goldenTimeSeconds > 0) {
        _goldenTimeSeconds--;
      }

      // 실제 네비게이션이 활성화되어 있을 때만 주행 이동 시뮬레이션
      if (_isTransferActive && _isNavigationActive && _etaSeconds > 0) {
        _etaSeconds--;
        _routeProgress += 0.003;
        if (_routeProgress > 0.95) _routeProgress = 0.95;
        _updateSimulatedLocation();
      }

      notifyListeners();
    });
  }

  void _updateSimulatedLocation() {
    final waypoints = _navigation.routeWaypoints;
    if (waypoints.length < 2) return;

    final totalSegments = waypoints.length - 1;
    final scaledPos = _routeProgress * totalSegments;
    final index = scaledPos.floor().clamp(0, totalSegments - 1);
    final t = scaledPos - index;

    final p1 = waypoints[index];
    final p2 = waypoints[index + 1];

    final currentLat = p1.latitude + (p2.latitude - p1.latitude) * t;
    final currentLng = p1.longitude + (p2.longitude - p1.longitude) * t;

    final remainingKm = (2.8 * (1.0 - _routeProgress)).toStringAsFixed(1);
    final speed = 64 + (DateTime.now().second % 7);

    _navigation = NavigationModel(
      nextTurnInstruction: _navigation.nextTurnInstruction,
      greenWaveStatus: _navigation.greenWaveStatus,
      currentSpeedKmH: speed,
      etaText: formattedEta,
      etaRemainingSeconds: _etaSeconds,
      remainingDistanceKm: '$remainingKm km',
      roadName: _navigation.roadName,
      coordinatesText: '청계천로 고가 (${currentLat.toStringAsFixed(4)}, ${currentLng.toStringAsFixed(4)})',
      currentAmbulanceLocation: LatLng(currentLat, currentLng),
      destinationHospitalLocation: _navigation.destinationHospitalLocation,
      routeWaypoints: waypoints,
    );
  }

  // ===========================================================================
  // [사이드바 탭 선택]
  // 0: 응급 이송 콜 (미이송 시 콜 접수 화면, 콜 발송 후엔 병원선택/네비 화면)
  // 1: 응급 GIS 및 환자 모니터 (네비 제외된 실시간 환자 생체/처치/센서 모니터)
  // 2: 응급처치 지침 및 약물
  // 3: ePCR 구급활동일지
  // ===========================================================================
  void setSidebarIndex(int index) {
    _selectedSidebarIndex = index;
    notifyListeners();
  }

  /// 다른 탭에 있을 때 우측 하단 동그란 플로팅 버튼을 눌러 이송/네비게이션 화면으로 복귀
  void returnToTransportView() {
    _selectedSidebarIndex = 0;
    _currentView = EmsView.splitNavigation;
    notifyListeners();
  }

  void startEmergencyTransport() {
    sendEmergencyCallAndNavigate();
  }

  void requestHospital(HospitalModel hospital) {
    startNavigation(hospital: hospital);
  }

  void setAvpu(String scale) {
    _patient = _patient.copyWith(avpu: scale);
    notifyListeners();
  }

  void addClinicalPhoto(String title, String time) {
    final updatedList = List<ClinicalPhotoItem>.from(_patient.clinicalPhotos)
      ..add(ClinicalPhotoItem(
        title: title,
        time: time,
        badge: 'NEW',
      ));
    _patient = _patient.copyWith(clinicalPhotos: updatedList);

    ApiService.uploadTraumaPhoto(
      patientId: _patient.id,
      title: title,
    );

    notifyListeners();
  }

  // ===========================================================================
  // [API 연동 6: POST /patient/handover (병원 도착 및 환자 인계서 전송)]
  // ===========================================================================
  void completeHandover() {
    ApiService.completeHandoverProtocol(
      patientId: _patient.id,
      hospitalId: _selectedHospital.id,
      ambId: 'AMB-704',
    );
  }

  // ===========================================================================
  // [핵심 워크플로우 4: 출동 임무 종료]
  // 이송 및 인계 완료 후 상태 초기화 -> 첫 대시보드(응급 이송 콜 대기)로 복귀
  // ===========================================================================
  void endMission() {
    completeHandover();
    _isTransferActive = false;
    _isNavigationActive = false;
    _currentView = EmsView.dashboard;
    _selectedSidebarIndex = 0;
    _goldenTimeSeconds = 18 * 60 + 24;
    _etaSeconds = 5 * 60 + 42;
    _routeProgress = 0.08;
    _patient = PatientModel.createInitialMock();
    _navigation = NavigationModel.createInitialMock();
    notifyListeners();
  }

  @override
  void dispose() {
    _tickerTimer?.cancel();
    super.dispose();
  }
}
