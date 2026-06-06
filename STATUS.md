# Raport audytu: Aplikacja Android – ostrzeżenia o fotoradarach

> Audyt przeprowadzony: 6 czerwca 2026

---

## ✅ Wyniki audytu — podsumowanie

| Obszar | Status | Szczegóły |
|--------|--------|-----------|
| Struktura projektu | ✅ Kompletna | `speed-camera-app/` ze wszystkimi modułami |
| `AndroidManifest.xml` | ✅ Poprawny | Uprawnienia, Activity, Service, namespace |
| `build.gradle.kts` | ✅ Poprawny | AGP 8.3.2, compileSdk 34, minSdk 26 |
| `settings.gradle.kts` | ✅ Poprawny | Repozytoria, include(":app") |
| `gradle/libs.versions.toml` | ✅ Poprawny | Katalog wersji zależności |
| Gradle Wrapper | ✅ Dodano | `gradlew`, `gradlew.bat`, `gradle-wrapper.jar` |
| Kod Kotlin | ✅ Kompiluje | Brak błędów kompilacji |
| Zależności | ✅ Naprawiono | Usunięto nieużywane (car.app, play-services, gson) |
| Uprawnienia | ✅ Kompletne | Lokalizacja, ForegroundService, Powiadomienia, INTERNET |
| Plik APK | ✅ Działa | `releases/FotoradaryPL-v1.0.1.apk` (758 KB) |
| CI/CD Workflow | ✅ Dodano | `.github/workflows/build-apk.yml` |

---

## 📋 Zidentyfikowane problemy i naprawy

### Naprawione w tym PR

| Problem | Zmiana |
|---------|--------|
| `speed-camera-app/` nieobecny na `main` | ✅ Dodano kod aplikacji do brancha |
| Brakujące pliki Gradle Wrapper (`gradlew`, `gradle-wrapper.jar`) | ✅ Dodano |
| Nieużywane zależności wymagające Google Maven: `androidx.car.app`, `play-services-location`, `gson`, `lifecycle-service`, `constraintlayout`, `viewBinding` | ✅ Usunięto z `build.gradle.kts` |
| Brakujące uprawnienie `INTERNET` (potrzebne dla CANARD API) | ✅ Dodano do `AndroidManifest.xml` |
| Brakujący workflow CI/CD na `main` | ✅ Dodano `.github/workflows/build-apk.yml` |

### Znane ograniczenia (poza zakresem MVP)

| Element | Status |
|---------|--------|
| Android Auto ekran | 🔄 Przyszła wersja (wymaga Car App Library) |
| Synchronizacja z CANARD API | 🔄 Przyszła wersja |
| Filtrowanie po kierunku jazdy | 🔄 Przyszła wersja |
| `package` atrybut w Manifeście | ℹ️ Deprecated w AGP, ale wymagany przez `build_apk.sh` |

---

## 📦 Struktura projektu (po audycie)

```
speed-camera-app/
├── gradlew                          ✅ Gradle Wrapper (Unix)
├── gradlew.bat                      ✅ Gradle Wrapper (Windows)
├── build.gradle.kts                 ✅ Root build file
├── settings.gradle.kts              ✅ Project settings
├── build_apk.sh                     ✅ Manual build script (bez Gradle)
├── gradle/
│   ├── libs.versions.toml           ✅ Version catalog
│   └── wrapper/
│       ├── gradle-wrapper.jar       ✅ Wrapper bootstrap jar
│       └── gradle-wrapper.properties ✅ Gradle 8.6
├── releases/
│   └── FotoradaryPL-v1.0.1.apk     ✅ Skompilowany APK (758 KB)
└── app/
    ├── build.gradle.kts             ✅ App module (minSdk 26, targetSdk 34)
    ├── proguard-rules.pro           ✅
    └── src/main/
        ├── AndroidManifest.xml      ✅ Uprawnienia + Activity + Service
        ├── assets/speed_cameras.json ✅ 15 fotoradarów PL
        ├── kotlin/pl/fotoradar/speedcamera/
        │   ├── data/SpeedCameraPoint.kt      ✅
        │   ├── data/SpeedCameraRepository.kt ✅ (używa org.json, bez Gson)
        │   ├── engine/AlertEngine.kt         ✅ TTS, progi 1000/500/200m
        │   ├── service/LocationMonitoringService.kt ✅ ForegroundService
        │   └── ui/MainActivity.kt            ✅ Uprawnienia + UI
        └── res/                     ✅ Layouty, ikony, wartości
```

---

## 🔐 Uprawnienia (AndroidManifest.xml)

| Uprawnienie | Cel | Status |
|-------------|-----|--------|
| `ACCESS_FINE_LOCATION` | Dokładna lokalizacja GPS | ✅ |
| `ACCESS_COARSE_LOCATION` | Lokalizacja sieciowa | ✅ |
| `ACCESS_BACKGROUND_LOCATION` | Monitoring przy zgaszonym ekranie | ✅ |
| `FOREGROUND_SERVICE` | Usługa w tle | ✅ |
| `FOREGROUND_SERVICE_LOCATION` | Typ usługi: lokalizacja | ✅ |
| `POST_NOTIFICATIONS` | Powiadomienie statusu (Android 13+) | ✅ |
| `WAKE_LOCK` | Zapobiega uśpieniu CPU | ✅ |
| `INTERNET` | Przyszłe pobieranie danych z CANARD | ✅ |

---

## 🔨 Jak zbudować APK

### Metoda 1: Skrypt `build_apk.sh` (zalecana, bez internetu)
```bash
cd speed-camera-app
bash build_apk.sh
# → releases/FotoradaryPL-v1.0.1.apk
```
**Wymagania:** Android SDK (build-tools 34.0.0, platform android-34), kotlinc

### Metoda 2: Gradle (standardowa)
```bash
cd speed-camera-app
./gradlew assembleRelease
# → app/build/outputs/apk/release/app-release.apk
```
**Wymagania:** JDK 17, Android SDK, dostęp do Maven Central

---

## 📲 Instalacja na telefonie

1. Pobierz `speed-camera-app/releases/FotoradaryPL-v1.0.1.apk`
2. **Ustawienia → Bezpieczeństwo → Zainstaluj nieznane aplikacje** — zezwól
3. Zainstaluj APK i uruchom **Fotoradary PL**
4. Przyznaj uprawnienia do lokalizacji
5. Na Androidzie 10+ ustaw lokalizację na **„Zezwalaj zawsze"** dla monitoringu w tle
6. Naciśnij **▶ Rozpocznij monitoring**

---

## 🔜 Następne kroki do oficjalnego wydania

1. **Scalenie tego PR** do `main`
2. **Opublikowanie GitHub Release** — utwórz tag `v1.0.1`:
   ```bash
   git tag v1.0.1
   git push origin v1.0.1
   ```
   Workflow CI automatycznie zbuduje i opublikuje APK w sekcji Releases.
3. **Oficjalny link:**  
   `https://github.com/tomekmvr/forex-ai-agent/releases/latest`
