import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:provider/provider.dart';
import '../../config/app_theme.dart';
import '../../providers/ems_provider.dart';
import 'navigation_hud.dart';

class EmergencyMapView extends StatelessWidget {
  const EmergencyMapView({super.key});

  @override
  Widget build(BuildContext context) {
    final ems = context.watch<EmsProvider>();
    final nav = ems.navigation;

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
                initialCenter: const LatLng(37.5730, 126.9890), // Central Seoul (Jongno / SNUH)
                initialZoom: 13.8,
                minZoom: 11.0,
                maxZoom: 18.0,
              ),
              children: [
                // OpenStreetMap Tile Layer
                TileLayer(
                  urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  userAgentPackageName: 'com.erlink.ems',
                ),

                // Critical Route Polyline (Cheonggyecheon -> SNUH)
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

                // Markers Layer: Ambulance & Destination Hospital
                MarkerLayer(
                  markers: [
                    // 1. SNUH Destination Hospital Marker
                    Marker(
                      point: nav.destinationHospitalLocation,
                      width: 44,
                      height: 44,
                      child: Container(
                        decoration: BoxDecoration(
                          color: const Color(0xFF991B1B),
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white, width: 2.5),
                          boxShadow: const [
                            BoxShadow(
                              color: Colors.black38,
                              blurRadius: 6,
                              offset: Offset(0, 3),
                            ),
                          ],
                        ),
                        child: const Center(
                          child: Icon(Icons.local_hospital, color: Colors.white, size: 24),
                        ),
                      ),
                    ),

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

            // Top Floating Route Pill
            Positioned(
              top: 12,
              left: 14,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.95),
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: const [
                    BoxShadow(color: Colors.black12, blurRadius: 4),
                  ],
                ),
                child: const Row(
                  children: [
                    Icon(Icons.route, color: Color(0xFF991B1B), size: 14),
                    SizedBox(width: 6),
                    Text(
                      '긴급 우선통행 경로 확정 (Green Corridor)',
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w800,
                        color: Color(0xFF1F2937),
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // Bottom Navigation HUD Overlay
            const Positioned(
              left: 12,
              right: 12,
              bottom: 12,
              child: NavigationHud(),
            ),
          ],
        ),
      ),
    );
  }
}
