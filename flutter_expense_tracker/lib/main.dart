import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'providers/app_provider.dart';
import 'screens/main_screen.dart';
import 'screens/onboarding_screen.dart';
import 'utils/constants.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(
    ChangeNotifierProvider(
      create: (_) => AppProvider(),
      child: const MyApp(),
    ),
  );
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Money Journal',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: kNavy,
          background: kBackground,
          surface: kCard,
        ),
        scaffoldBackgroundColor: kBackground,
        useMaterial3: true,
        fontFamily: 'sans-serif',
      ),
      home: Consumer<AppProvider>(
        builder: (context, provider, _) {
          if (!provider.loaded) {
            return const Scaffold(
              backgroundColor: kBackground,
              body: Center(
                child: CircularProgressIndicator(color: kNavy),
              ),
            );
          }
          return const _StartScreen();
        },
      ),
    );
  }
}

class _StartScreen extends StatefulWidget {
  const _StartScreen();

  @override
  State<_StartScreen> createState() => _StartScreenState();
}

class _StartScreenState extends State<_StartScreen> {
  bool? _onboarded;

  @override
  void initState() {
    super.initState();
    _check();
  }

  Future<void> _check() async {
    final prefs    = await SharedPreferences.getInstance();
    final onboarded = prefs.getBool('et_onboarded') ?? false;
    setState(() => _onboarded = onboarded);
  }

  @override
  Widget build(BuildContext context) {
    if (_onboarded == null) {
      return const Scaffold(
        backgroundColor: kBackground,
        body: Center(child: CircularProgressIndicator(color: kNavy)),
      );
    }
    return _onboarded! ? const MainScreen() : const OnboardingScreen();
  }
}
