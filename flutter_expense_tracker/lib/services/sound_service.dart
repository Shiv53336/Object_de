import 'package:audioplayers/audioplayers.dart';

class SoundService {
  SoundService._();
  static final SoundService instance = SoundService._();

  final AudioPlayer _player = AudioPlayer();

  Future<void> playAdd() async {
    await _player.play(AssetSource('sounds/pen-scratch.wav'));
  }

  Future<void> playDelete() async {
    await _player.play(AssetSource('sounds/erase.wav'));
  }
}
