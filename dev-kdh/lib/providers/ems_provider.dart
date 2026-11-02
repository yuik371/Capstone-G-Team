import 'dart:async';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:latlong2/latlong.dart';
import '../models/hospital_model.dart';
import '../models/patient_model.dart';
import '../models/navigation_model.dart';
import '../services/api_service.dart';

enum EmsView {
  dashboard, // 119 EMS 구급차 이송 시작 대시보드
  splitNavigation, // 119 EMS 환자치료 및 이송 내비게이션 스플릿 스크린
}

class EmsProvider extends ChangeNotifier {
  EmsView _currentView = EmsView.dashboard;
  int _selectedSidebarIndex = 0; // 0: 원격모니터, 1: 응급GIS, 2: 지침/약물, 3: ePCR

  late List<HospitalModel> _hospitals;
  late HospitalModel _selectedHospital;
  late PatientModel _patient;
  late NavigationModel _navigation;

  Timer? _tickerTimer;
  String _currentTimeString = '14:28:19 KST';
  int _goldenTimeSeconds = 18 * 60 + 24; // 18분 24초
  int _etaSeconds = 5 * 60 + 42; // 05분 42초
  double _routeProgress = 0.08; // 0.0 to 1.0 along the waypoints
  bool _isTransferActive = false;

  EmsProvider() {
    _hospitals = HospitalModel.getMockHospitals();
    _selectedHospital = _hospitals.first;
    _patient = PatientModel.createInitialMock();
    _navigation = NavigationModel.createInitialMock();
    _loadInitialHospitals();
    _startLiveTicker();
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
  // [API 연동 1: 추천 병원 목록 조회]
  // ===========================================================================
  Future<void> _loadInitialHospitals() async {
    final list = await ApiService.getRecommendedHospitals(
      lat: 37.5665,
      lng: 126.9780,
    );
    if (list.isNotEmpty) {
      _hospitals = list;
      _selectedHospital = list.first;
      notifyListeners();
    }
  }

  void _startLiveTicker() {
    _tickerTimer?.cancel();
    _tickerTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      final now = DateTime.now();
      _currentTimeString = '${DateFormat('HH:mm:ss').format(now)} KST';

      if (_goldenTimeSeconds > 0) {
        _goldenTimeSeconds--;
      }

      if (_isTransferActive && _etaSeconds > 0) {
        _etaSeconds--;
        // Animate ambulance moving slightly along waypoints
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

    // =========================================================================
    // [API 연동 2: POST /amb/location]
    // 구급차의 실시간 GPS 위치를 백엔드로 전송하여 병원 웹 대시보드 지도에 실시간 반영
    // =========================================================================
    ApiService.updateAmbulanceLocation(
      ambId: 'AMB-704',
      lat: currentLat,
      lng: currentLng,
      speedKmH: speed,
    );
  }

  void setSidebarIndex(int index) {
    _selectedSidebarIndex = index;
    if (index == 0) {
      _currentView = EmsView.dashboard;
    } else if (index == 1) {
      _currentView = EmsView.splitNavigation;
    }
    notifyListeners();
  }

  // ===========================================================================
  // [API 연동 3: POST /patient/request (이송 시작 & 1순위 서울대병원 수용 의뢰)]
  // ===========================================================================
  void startEmergencyTransport() {
    _isTransferActive = true;
    _currentView = EmsView.splitNavigation;
    _selectedSidebarIndex = 1; // Highlight 응급 GIS 및 병원 수용

    ApiService.sendPatientTransferRequest(
      hospital: _selectedHospital,
      patient: _patient,
      ambId: 'AMB-704',
    );

    notifyListeners();
  }

  // ===========================================================================
  // [API 연동 4: POST /patient/request (특정 병원 수용 요청 및 프리노티 발송)]
  // ===========================================================================
  void requestHospital(HospitalModel hospital) {
    _selectedHospital = hospital;
    _isTransferActive = true;
    _currentView = EmsView.splitNavigation;
    _selectedSidebarIndex = 1;

    ApiService.sendPatientTransferRequest(
      hospital: hospital,
      patient: _patient,
      ambId: 'AMB-704',
    );

    notifyListeners();
  }

  void setAvpu(String scale) {
    _patient = _patient.copyWith(avpu: scale);
    notifyListeners();
  }

  // ===========================================================================
  // [API 연동 5: POST /patient/photos (환부 사진 실시간 전송)]
  // ===========================================================================
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

  @override
  void dispose() {
    _tickerTimer?.cancel();
    super.dispose();
  }
}
