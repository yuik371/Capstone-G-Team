import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:provider/provider.dart';
import 'config/app_theme.dart';
import 'providers/ems_provider.dart';
import 'screens/ems_shell_screen.dart';
import 'screens/login_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  try {
    await dotenv.load(fileName: ".env");
    debugPrint("[ENV] .env 로드 완료: BASE_URL=${dotenv.env['BASE_URL']}");
  } catch (e) {
    debugPrint("[ENV] .env 로드 실패 (기본값 사용): $e");
  }

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => EmsProvider()),
      ],
      child: const ErLinkEmsApp(),
    ),
  );
}

class ErLinkEmsApp extends StatelessWidget {
  const ErLinkEmsApp({super.key});

  @override
  Widget build(BuildContext context) {
    final ems = context.watch<EmsProvider>();

    return MaterialApp(
      title: 'ER-Link 119 TACTICAL EMS',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.theme,
      home: ems.isAuthenticated ? const EmsShellScreen() : const LoginScreen(),
    );
  }
}
