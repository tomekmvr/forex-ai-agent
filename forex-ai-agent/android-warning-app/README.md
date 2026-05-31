# Android MVP: Speed Camera Warning App

## Build requirements
- Android Studio Iguana+ (or command line with Android SDK)
- Android SDK Platform 34
- JDK 17

## Build and run
```bash
cd android-warning-app
./gradlew :app:assembleDebug
```

Install generated APK from `app/build/outputs/apk/debug/app-debug.apk`.

## MVP features
- Phone UI with Start/Stop monitoring controls.
- Foreground location monitoring via Fused Location Provider.
- Local warning-point data in `app/src/main/assets/speed_camera_points.json`.
- Distance-threshold alert engine (1000m / 500m / 200m) with TextToSpeech output.
- Android Auto integration via Car App Library (`SpeedCamCarAppService`) showing monitoring status and nearest point.

## Scope constraints
- No overlays or modifications to Google Maps.
- Android Auto UI follows template-based Car App approach.
