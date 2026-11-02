import 'package:flutter/material.dart';
import '../widgets/dashboard/live_dispatch_card.dart';
import '../widgets/dashboard/cabin_sensors_card.dart';
import '../widgets/dashboard/emergency_dispatch_banner.dart';
import '../widgets/dashboard/hospital_selection_cards.dart';
import '../widgets/dashboard/dashboard_footer_bar.dart';

class EmsStartDashboard extends StatelessWidget {
  const EmsStartDashboard({super.key});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: const [
          // Top Row: LIVE DISPATCH FEED (Left 7) & CABIN SENSORS (Right 5)
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                flex: 7,
                child: LiveDispatchCard(),
              ),
              SizedBox(width: 14),
              Expanded(
                flex: 5,
                child: CabinSensorsCard(),
              ),
            ],
          ),
          SizedBox(height: 16),

          // Critical Action: ONE-TOUCH CRITICAL DISPATCH Banner
          EmergencyDispatchBanner(),
          SizedBox(height: 16),

          // Hospital Candidates: 1st Priority SNUH & 2nd Priority NMC
          HospitalSelectionCards(),
          SizedBox(height: 16),

          // Bottom Bar: Rapid Clinical Entry, PTT Hotline, GCS Assessment, ECG Monitor
          DashboardFooterBar(),
        ],
      ),
    );
  }
}
