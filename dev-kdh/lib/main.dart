import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'config/app_theme.dart';
import 'providers/ems_provider.dart';
import 'screens/ems_shell_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
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
    return MaterialApp(
      title: 'ER-Link 119 TACTICAL EMS',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.theme,
      home: const EmsShellScreen(),
    );
  }
}
