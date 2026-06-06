# 🚗 Fotoradary PL — Speed Camera Warning App

Aplikacja na Androida ostrzegająca o fotoradarach stacjonarnych w Polsce, z obsługą Android Auto.

## Pobieranie APK

### ⬇️ Najnowsza wersja

**[FotoradaryPL-v1.0.1.apk](releases/FotoradaryPL-v1.0.1.apk)** — poprawiony APK zgodny z nowszymi telefonami, w tym Xiaomi 15T.

> Lub pobierz z zakładki [Releases](https://github.com/tomekmvr/forex-ai-agent/releases) po scaleniu PR.

---

## Funkcje

| Funkcja | Status |
|---------|--------|
| 📍 Monitoring GPS (ForegroundService) | ✅ MVP |
| ⚠️ Alert głosowy: 1000m / 500m / 200m | ✅ MVP |
| 🗺️ Lokalna baza fotoradarów (15 lokalizacji PL) | ✅ MVP |
| 🔔 Powiadomienie z najbliższym fotoradarem | ✅ MVP |
| 🚘 Ekran Android Auto | 🔄 Przyszła wersja |
| 🌐 Synchronizacja z CANARD / backendem | 🔄 Przyszła wersja |
| 🧭 Filtrowanie po kierunku jazdy | 🔄 Przyszła wersja |

---

## Wymagania

- **Android**: 8.0 (API 26) lub nowszy
- **Uprawnienia**:
  - `ACCESS_FINE_LOCATION` — dokładna lokalizacja GPS
  - `ACCESS_BACKGROUND_LOCATION` — monitoring po zgaszeniu ekranu / w tle (Android 10+)
  - `FOREGROUND_SERVICE_LOCATION` — monitoring w tle
  - `POST_NOTIFICATIONS` — powiadomienie statusu (Android 13+)

---

## Instalacja

1. **Pobierz APK** z linku powyżej
2. Na telefonie: **Ustawienia → Bezpieczeństwo → Instaluj nieznane aplikacje** → zezwól przeglądarce/menedżerowi plików
3. Otwórz pobrany plik APK i kliknij **Zainstaluj**
4. Przyznaj uprawnienia do lokalizacji i powiadomień
5. Na Androidzie 16 ustaw dla aplikacji lokalizację **„Zezwalaj zawsze”**, inaczej monitoring w tle nie uruchomi się poprawnie

---

## Pierwsze uruchomienie

1. Otwórz **Fotoradary PL**
2. Kliknij **▶ Rozpocznij monitoring**
3. Zatwierdź żądania uprawnień
4. Aplikacja działa w tle — w pasku pojawi się powiadomienie "Monitoring aktywny"
5. Zbliżając się do fotoradaru usłyszysz komunikat głosowy

---

## Baza danych fotoradarów

MVP zawiera 15 przykładowych lokalizacji:

| Miasto | Lokalizacja | Limit |
|--------|-------------|-------|
| Warszawa | ul. Marszałkowska | 50 km/h |
| Warszawa | Al. Jerozolimskie | 70 km/h |
| Warszawa | ul. Wolska | 50 km/h |
| Warszawa | ul. Puławska | 60 km/h |
| Warszawa | ul. Targowa | 50 km/h |
| Kraków | ul. Floriańska | 50 km/h |
| Kraków | Al. Mickiewicza | 70 km/h |
| Wrocław | ul. Świdnicka | 50 km/h |
| Gdańsk | ul. Długa | 50 km/h |
| Poznań | ul. Półwiejska | 50 km/h |
| Łódź | ul. Piotrkowska | 60 km/h |
| Katowice | ul. Mariacka | 50 km/h |
| A1 | km 234 (kierunek N) | 140 km/h |
| A2 | km 312 (kierunek E) | 140 km/h |
| S8 | km 176 | 120 km/h |

---

## Architektura projektu

```
speed-camera-app/
├── app/src/main/
│   ├── kotlin/pl/fotoradar/speedcamera/
│   │   ├── ui/MainActivity.kt          # Ekran główny
│   │   ├── service/LocationMonitoringService.kt  # ForegroundService GPS
│   │   ├── engine/AlertEngine.kt       # Logika ostrzegania + TTS
│   │   └── data/
│   │       ├── SpeedCameraPoint.kt     # Model danych
│   │       └── SpeedCameraRepository.kt # Dostęp do bazy
│   ├── assets/speed_cameras.json       # Baza fotoradarów
│   └── res/
│       ├── layout/activity_main.xml
│       └── values/{strings,colors,themes}.xml
└── releases/
    └── FotoradaryPL-v1.0.1.apk        # Skompilowany APK
```

---

## Budowanie ze źródeł

```bash
# Wymagania: Android SDK, JDK 17, kotlinc
cd speed-camera-app
bash build_apk.sh
```

Lub przez GitHub Actions (automatyczne po tagu `v*`):

```bash
git tag v1.0.1
git push origin v1.0.1
# → workflow buduje i publikuje release automatycznie
```

---

## Ograniczenia MVP

- Baza fotoradarów jest statyczna (15 lokalizacji testowych)
- Brak filtrowania po kierunku jazdy (ostrzeżenia dla wszystkich kierunków)
- Brak synchronizacji z CANARD lub innym backendem
- APK podpisany kluczem debug — wymaga włączenia "Instaluj nieznane aplikacje"
- Android Auto UI wymaga dodatkowej integracji z Car App Library

---

## Uwaga prawna

Aplikacja służy do informowania o lokalizacjach stacjonarnych urządzeń pomiarowych. Zawsze przestrzegaj przepisów ruchu drogowego obowiązujących w danym kraju.
