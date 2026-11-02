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

  static NavigationModel createInitialMock() {
    // Route from Cheonggyecheon to Seoul National University Hospital (Daehak-ro)
    final waypoints = [
      const LatLng(37.5665, 126.9780), // Cheonggyecheon start
      const LatLng(37.5680, 126.9830), // Jongno 2-ga
      const LatLng(37.5704, 126.9920), // Jongno 3-ga
      const LatLng(37.5735, 126.9980), // Jongno 5-ga
      const LatLng(37.5765, 126.9995), // Ihwa-dong crossroads
      const LatLng(37.5796, 127.0000), // SNUH Emergency Center
    ];

    return NavigationModel(
      nextTurnInstruction: '250m 앞 청계2가 사거리 좌회전',
      greenWaveStatus: '스마트 긴급신호(Green Wave) 가동: 3개 교',
      currentSpeedKmH: 68,
      etaText: '05:42',
      etaRemainingSeconds: 5 * 60 + 42,
      remainingDistanceKm: '2.8 km',
      roadName: '대학로 진입로',
      coordinatesText: '청계천로 고가 (37.5665, 126.9780)',
      currentAmbulanceLocation: const LatLng(37.5665, 126.9780),
      destinationHospitalLocation: const LatLng(37.5796, 127.0000),
      routeWaypoints: waypoints,
    );
  }
}
