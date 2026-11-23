import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:er_link_ems/main.dart';
import 'package:er_link_ems/providers/ems_provider.dart';

void main() {
  testWidgets('119 EMS Tactical App auth & tablet smoke test', (WidgetTester tester) async {
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

    // 1. Initial Login Screen Verification
    expect(find.text('대원 로그인 (AUTH LOGIN)'), findsOneWidget);
    expect(find.text('신규 대원 계정 등록 (회원가입)'), findsOneWidget);

    // 2. Navigate to Register Screen
    await tester.tap(find.text('신규 대원 계정 등록 (회원가입)'));
    await tester.pump(const Duration(milliseconds: 200));

    expect(find.text('회원가입 (AUTH REGISTER)'), findsOneWidget);
    expect(find.text('소속 역할 (ROLE)'), findsOneWidget);
    expect(find.text('119 구급대원'), findsOneWidget);

    // 3. Return to Login Screen
    await tester.tap(find.text('이미 계정이 있으신가요? 로그인하기'));
    await tester.pump(const Duration(milliseconds: 200));
    expect(find.text('대원 로그인 (AUTH LOGIN)'), findsOneWidget);

    // 4. Bypass Login with Quick Demo Mode
    await tester.tap(find.text('오프라인 / 데모 모드로 바로 시작'));
    await tester.pump(const Duration(milliseconds: 200));

    // 5. Verify Main Dashboard
    expect(find.text('119 TACTICAL EMS'), findsOneWidget);
    expect(find.text('응급 환자 이송 시작'), findsOneWidget);
    expect(find.text('서울대학교병원 권역응급의료센터'), findsOneWidget);

    // 6. Test transition from Dashboard to Split Navigation screen
    await tester.tap(find.text('응급 환자 이송 시작'));
    await tester.pump(const Duration(milliseconds: 200));

    // 7. Verify Split Navigation elements
    expect(find.text('의식 수준 척도 (AVPU SCALE)'), findsOneWidget);
    expect(find.text('서울대학교병원 권역외상센터'), findsOneWidget);
    expect(find.text('스마트 긴급신호(Green Wave) 가동: 3개 교'), findsOneWidget);
  });
}
