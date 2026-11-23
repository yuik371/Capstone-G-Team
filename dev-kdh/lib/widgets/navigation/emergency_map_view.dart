import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:provider/provider.dart';
import '../../config/app_theme.dart';
import '../../models/hospital_model.dart';
import '../../providers/ems_provider.dart';
import 'navigation_hud.dart';

class EmergencyMapView extends StatelessWidget {
  const EmergencyMapView({super.key});

  @override
  Widget build(BuildContext context) {
    final ems = context.watch<EmsProvider>();
    final nav = ems.navigation;
    final selectedHosp = ems.selectedHospital;
    final isNavActive = ems.isNavigationActive;

    // 네비 실행 전에는 추천 병원 3곳 모두 지도에 마커로 표시, 실행 후에는 목적지 병원 중심 표시
    final List<HospitalModel> displayHospitals = isNavActive
        ? [selectedHosp]
        : ems.hospitals.take(3).toList();

    // 지도 중심 좌표 (구급차와 선택 병원의 중간 지점)
    final hospLocation = LatLng(selectedHosp.lat, selectedHosp.lng);
    final centerLat = (nav.currentAmbulanceLocation.latitude + hospLocation.latitude) / 2;
    final centerLng = (nav.currentAmbulanceLocation.longitude + hospLocation.longitude) / 2;

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(14),
        child: Stack(
          children: [
            // OpenStreetMap Interactive Map Layer
            FlutterMap(
              options: MapOptions(
                initialCenter: LatLng(centerLat, centerLng),
                initialZoom: isNavActive ? 13.8 : 13.0,
                minZoom: 10.0,
                maxZoom: 18.0,
              ),
              children: [
                // OpenStreetMap Tile Layer
                TileLayer(
                  urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  userAgentPackageName: 'com.erlink.ems',
                ),

                // [네비가 시작되었을 때만 도로망 Polyline 렌더링]
                if (isNavActive && nav.routeWaypoints.isNotEmpty)
                  PolylineLayer(
                    polylines: [
                      // Outer glow polyline
                      Polyline(
                        points: nav.routeWaypoints,
                        strokeWidth: 8.0,
                        color: const Color(0xFF991B1B).withValues(alpha: 0.3),
                      ),
                      // Inner solid polyline
                      Polyline(
                        points: nav.routeWaypoints,
                        strokeWidth: 4.5,
                        color: const Color(0xFF8B1515),
                      ),
                    ],
                  ),

                // Markers Layer: Ambulance Pin + 추천 병원 3곳 마커
                MarkerLayer(
                  markers: [
                    // 1. 추천 병원 마커들 (네비 전 3곳 모두 표시, 포인트별 병원명/순위/적합도 표시)
                    for (int i = 0; i < displayHospitals.length; i++)
                      _buildHospitalMarker(context, ems, displayHospitals[i], i, isNavActive),

                    // 2. Real-Time Moving Ambulance Marker
                    Marker(
                      point: nav.currentAmbulanceLocation,
                      width: 48,
                      height: 48,
                      child: Container(
                        decoration: BoxDecoration(
                          color: const Color(0xFF1E3A8A),
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white, width: 2.5),
                          boxShadow: [
                            BoxShadow(
                              color: const Color(0xFF1E3A8A).withValues(alpha: 0.45),
                              blurRadius: 10,
                              spreadRadius: 2,
                            ),
                          ],
                        ),
                        child: const Center(
                          child: Icon(
                            Icons.navigation,
                            color: Colors.white,
                            size: 24,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),

            // Top Floating Route / Status Pill
            Positioned(
              top: 12,
              left: 14,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.95),
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: const [
                    BoxShadow(color: Colors.black12, blurRadius: 4),
                  ],
                ),
                child: Row(
                  children: [
                    Icon(
                      isNavActive ? Icons.route : Icons.map_outlined,
                      color: const Color(0xFF991B1B),
                      size: 14,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      isNavActive
                          ? '${selectedHosp.name} 최단 이송 경로 안내 중 (${selectedHosp.distance})'
                          : '추천 병원 3곳 위치 표시 중 (안내 시작 버튼을 누르면 네비 가동)',
                      style: const TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w800,
                        color: Color(0xFF1F2937),
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // Bottom Navigation HUD (네비 실행 중일 때만 HUD 표시, 실행 전엔 안내 시작 유도 바)
            Positioned(
              left: 12,
              right: 12,
              bottom: 12,
              child: isNavActive
                  ? const NavigationHud()
                  : _buildPreNavigationPrompt(context, ems, selectedHosp),
            ),
          ],
        ),
      ),
    );
  }

  /// [요구사항]: 네비 실행 전 병원 3곳의 위치와 각 포인트가 어디 병원인지 명확하게 표시하는 마커
  Marker _buildHospitalMarker(
    BuildContext context,
    EmsProvider ems,
    HospitalModel hospital,
    int index,
    bool isNavActive,
  ) {
    final isSelected = (ems.selectedHospital.name == hospital.name);

    Color color;
    String rankLabel;
    if (index == 0 || hospital.name == ems.hospitals.firstOrNull?.name) {
      color = const Color(0xFF991B1B);
      rankLabel = '1순위';
    } else if (index == 1) {
      color = const Color(0xFF0284C7);
      rankLabel = '2순위';
    } else {
      color = const Color(0xFF4B5563);
      rankLabel = '3순위';
    }

    return Marker(
      point: LatLng(hospital.lat, hospital.lng),
      width: 120,
      height: 64,
      child: GestureDetector(
        onTap: () => ems.selectHospital(hospital),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // 병원명 & 적합도 라벨 태그
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
              decoration: BoxDecoration(
                color: isSelected ? const Color(0xFF991B1B) : Colors.white,
                borderRadius: BorderRadius.circular(6),
                border: Border.all(
                  color: isSelected ? Colors.white : color,
                  width: 1.5,
                ),
                boxShadow: const [
                  BoxShadow(color: Colors.black26, blurRadius: 4, offset: Offset(0, 2)),
                ],
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                    decoration: BoxDecoration(
                      color: isSelected ? Colors.white : color,
                      borderRadius: BorderRadius.circular(3),
                    ),
                    child: Text(
                      rankLabel,
                      style: TextStyle(
                        fontSize: 8,
                        fontWeight: FontWeight.w900,
                        color: isSelected ? const Color(0xFF991B1B) : Colors.white,
                      ),
                    ),
                  ),
                  const SizedBox(width: 4),
                  Flexible(
                    child: Text(
                      hospital.name,
                      style: TextStyle(
                        fontSize: 9,
                        fontWeight: FontWeight.w800,
                        color: isSelected ? Colors.white : const Color(0xFF111827),
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 2),

            // 마커 아이콘
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: isSelected ? const Color(0xFF991B1B) : color,
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white, width: 2.5),
                boxShadow: const [
                  BoxShadow(color: Colors.black38, blurRadius: 6, offset: Offset(0, 2)),
                ],
              ),
              child: const Center(
                child: Icon(Icons.local_hospital, color: Colors.white, size: 18),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// 네비 시작 전 하단에 노출되는 "경로 안내 시작" 안내 바
  Widget _buildPreNavigationPrompt(
    BuildContext context,
    EmsProvider ems,
    HospitalModel selectedHosp,
  ) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.98),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFE5E7EB)),
        boxShadow: const [
          BoxShadow(color: Colors.black12, blurRadius: 8, offset: Offset(0, 3)),
        ],
      ),
      child: Row(
        children: [
          const Icon(Icons.info_outline, color: Color(0xFF991B1B), size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  '선택된 목적지: ${selectedHosp.name}',
                  style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w900, color: Color(0xFF111827)),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                Text(
                  '거리 ${selectedHosp.distance} · 예상 ETA ${selectedHosp.eta} (사이드바에서 병원 선택 가능)',
                  style: const TextStyle(fontSize: 10, color: Color(0xFF6B7280)),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF991B1B),
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: () => ems.startNavigation(),
            icon: const Icon(Icons.navigation, size: 16),
            label: const Text(
              '네비 안내 시작',
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w900),
            ),
          ),
        ],
      ),
    );
  }
}
