import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'providers/app_provider.dart';
import 'screens/main_screen.dart';
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
      title: 'My Expense Tracker',
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
          return const MainScreen();
        },
      ),
    );
  }
}
