import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:er_link_ems/main.dart';
import 'package:er_link_ems/providers/ems_provider.dart';

void main() {
  testWidgets('119 EMS Tactical App tablet smoke test', (WidgetTester tester) async {
    // Set viewport size to 1280x800 (standard EMS vehicle tablet resolution)
    tester.view.physicalSize = const Size(1280, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() => tester.view.resetPhysicalSize());

    // Build our app and trigger a frame.
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => EmsProvider()),
        ],
        child: const ErLinkEmsApp(),
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));

    // Initial Dashboard Verification
    expect(find.text('119 TACTICAL EMS'), findsOneWidget);
    expect(find.text('응급 환자 이송 시작'), findsOneWidget);
    expect(find.text('서울대학교병원 권역응급의료센터'), findsOneWidget);

    // Test transition from Dashboard to Split Navigation screen
    await tester.tap(find.text('응급 환자 이송 시작'));
    await tester.pump(const Duration(milliseconds: 100));

    // Verify Split Navigation elements
    expect(find.text('의식 수준 척도 (AVPU SCALE)'), findsOneWidget);
    expect(find.text('서울대학교병원 권역외상센터'), findsOneWidget);
    expect(find.text('스마트 긴급신호(Green Wave) 가동: 3개 교'), findsOneWidget);
  });
}
