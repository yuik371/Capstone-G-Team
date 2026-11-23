import 'package:latlong2/latlong.dart';

class NavigationModel {
  final String nextTurnInstruction;
  final String greenWaveStatus;
  final int currentSpeedKmH;
  final String etaText;
  final int etaRemainingSeconds;
  final String remainingDistanceKm;
  final String roadName;
  final String coordinatesText;
  final LatLng currentAmbulanceLocation;
  final LatLng destinationHospitalLocation;
  final List<LatLng> routeWaypoints;

  const NavigationModel({
    required this.nextTurnInstruction,
    required this.greenWaveStatus,
    required this.currentSpeedKmH,
    required this.etaText,
    required this.etaRemainingSeconds,
    required this.remainingDistanceKm,
    required this.roadName,
    required this.coordinatesText,
    required this.currentAmbulanceLocation,
    required this.destinationHospitalLocation,
    required this.routeWaypoints,
  });

  NavigationModel copyWith({
    String? nextTurnInstruction,
    String? greenWaveStatus,
    int? currentSpeedKmH,
    String? etaText,
    int? etaRemainingSeconds,
    String? remainingDistanceKm,
    String? roadName,
    String? coordinatesText,
    LatLng? currentAmbulanceLocation,
    LatLng? destinationHospitalLocation,
    List<LatLng>? routeWaypoints,
  }) {
    return NavigationModel(
      nextTurnInstruction: nextTurnInstruction ?? this.nextTurnInstruction,
      greenWaveStatus: greenWaveStatus ?? this.greenWaveStatus,
      currentSpeedKmH: currentSpeedKmH ?? this.currentSpeedKmH,
      etaText: etaText ?? this.etaText,
      etaRemainingSeconds: etaRemainingSeconds ?? this.etaRemainingSeconds,
      remainingDistanceKm: remainingDistanceKm ?? this.remainingDistanceKm,
      roadName: roadName ?? this.roadName,
      coordinatesText: coordinatesText ?? this.coordinatesText,
      currentAmbulanceLocation: currentAmbulanceLocation ?? this.currentAmbulanceLocation,
      destinationHospitalLocation: destinationHospitalLocation ?? this.destinationHospitalLocation,
      routeWaypoints: routeWaypoints ?? this.routeWaypoints,
    );
  }

  static NavigationModel createInitialMock() {
    return const NavigationModel(
      nextTurnInstruction: '경로 안내 대기 중 (병원 선택 후 안내 시작)',
      greenWaveStatus: '스마트 긴급신호(Green Wave) 대기',
      currentSpeedKmH: 0,
      etaText: '--:--',
      etaRemainingSeconds: 0,
      remainingDistanceKm: '0.0 km',
      roadName: '출동 대기',
      coordinatesText: '구급차 위치 (37.5665, 126.9780)',
      currentAmbulanceLocation: LatLng(37.5665, 126.9780),
      destinationHospitalLocation: LatLng(37.5684, 126.9678),
      routeWaypoints: [],
    );
  }
}
