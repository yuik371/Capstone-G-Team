import 'package:flutter/material.dart';
import '../widgets/treatment/patient_summary_bar.dart';
import '../widgets/treatment/avpu_selector.dart';
import '../widgets/treatment/vital_quad_grid.dart';
import '../widgets/treatment/live_ecg_monitor.dart';
import '../widgets/treatment/clinical_photos_widget.dart';
import '../widgets/navigation/hospital_destination_card.dart';
import '../widgets/navigation/green_wave_banner.dart';
import '../widgets/navigation/emergency_map_view.dart';
import '../widgets/navigation/navigation_bottom_bar.dart';

class EmsSplitNavigation extends StatelessWidget {
  const EmsSplitNavigation({super.key});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 1. Top Patient Summary Bar
          const PatientSummaryBar(),
          const SizedBox(height: 12),

          // 2. Main Split Area: Left (Treatment) & Right (Navigation)
          Expanded(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Left Column: Patient Treatment & Telemetry
                const Expanded(
                  flex: 6,
                  child: SingleChildScrollView(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // AVPU Consciousness Scale
                        AvpuSelector(),
                        SizedBox(height: 10),

                        // 4-Quadrant Vitals Grid (NIBP, PR, SpO2, BT/RR)
                        VitalQuadGrid(),
                        SizedBox(height: 10),

                        // Real-Time Lead II ST-Elevation Animated ECG Monitor
                        LiveEcgMonitor(),
                        SizedBox(height: 10),

                        // Clinical Trauma Photos & 12-Lead ECG Sync
                        ClinicalPhotosWidget(),
                      ],
                    ),
                  ),
                ),
                const SizedBox(width: 14),

                // Right Column: Hospital Confirmed & OpenStreetMap Navigation
                Expanded(
                  flex: 5,
                  child: Column(
                    children: const [
                      // Confirmed Hospital Destination Header Card
                      HospitalDestinationCard(),
                      SizedBox(height: 10),

                      // Green Wave & Turn-by-Turn Instruction Banner
                      GreenWaveBanner(),
                      SizedBox(height: 10),

                      // OpenStreetMap Interactive Map & Real-Time Ambulance Pin
                      Expanded(
                        child: EmergencyMapView(),
                      ),
                      SizedBox(height: 10),

                      // Doctor Direct Order & Handover Protocol Bottom Bar
                      NavigationBottomBar(),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
