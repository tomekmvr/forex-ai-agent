# Status projektu: Aplikacja Android – ostrzeżenia o fotoradarach

> Stan na: 31 maja 2026

---

## ✅ Co zostało zrobione

### Kod aplikacji
Pełna aplikacja Android MVP jest gotowa i znajduje się w otwartym PR-ze #3
([Add speed-camera warning Android MVP with compiled APK](https://github.com/tomekmvr/forex-ai-agent/pull/3)).

Zaimplementowane elementy:
- `LocationMonitoringService` – usługa lokalizacji w tle (GPS + sieć, co 3 s/5 m)
- `AlertEngine` – progi ostrzeżeń 1000 m / 500 m / 200 m, TTS po polsku, cooldown 15 s
- `SpeedCameraRepository` – parser pliku JSON z 15 przykładowymi fotoradarami (Warszawa, Kraków, Wrocław, Gdańsk, Poznań, autostrady A1/A2/S8)
- `MainActivity` – uprawnienia, start/stop, przycisk testowy
- Adapter danych CANARD z fallbackiem lokalnym (PR #2)
- Workflow CI/CD (`.github/workflows/build-apk.yml`) uruchamiany tagiem `v*`

### Gotowy plik APK
Skompilowany i podpisany APK jest **już dostępny do pobrania bezpośrednio z brancha PR #3**:

```
https://github.com/tomekmvr/forex-ai-agent/raw/copilot/generate-apk-for-speed-camera-warning/speed-camera-app/releases/FotoradaryPL-v1.0.0.apk
```

**Rozmiar:** 758 KB  
**Podpis:** debug key, weryfikacja v1/v2/v3  
**Wymagania:** Android 8.0+ (API 26)

---

## ⚠️ Co jeszcze nie zostało ukończone

| Element | Status |
|---|---|
| PR #1 (kod aplikacji + Android Auto) | Otwarty draft – **nie scalony** |
| PR #2 (adapter CANARD) | Otwarty draft – **nie scalony** |
| PR #3 (kod + skompilowany APK) | Otwarty draft – **nie scalony** |
| GitHub Release z APK | ❌ Nie opublikowano |

Żaden z PR-ów nie został jeszcze scalony do gałęzi `main`.
Sekcja **Releases** w repozytorium jest pusta – APK nie został opublikowany jako oficjalne wydanie.

---

## 📲 Jak pobrać APK teraz (bez czekania)

Pobierz APK bezpośrednio z brancha PR #3:

1. Kliknij link:  
   **[➜ Pobierz FotoradaryPL-v1.0.0.apk](https://github.com/tomekmvr/forex-ai-agent/raw/copilot/generate-apk-for-speed-camera-warning/speed-camera-app/releases/FotoradaryPL-v1.0.0.apk)**

2. Prześlij plik na telefon (kabel USB, Google Drive, e-mail itp.).

3. Na telefonie włącz instalację z nieznanych źródeł:  
   **Ustawienia → Bezpieczeństwo → Zainstaluj nieznane aplikacje**

4. Zainstaluj APK i uruchom **FotoradaryPL**.

5. Przyznaj uprawnienia do lokalizacji i powiadomień.

6. Naciśnij **„Rozpocznij monitorowanie"**.

---

## 🔜 Następne kroki do oficjalnego wydania

1. **Scalenie PR-ów** – zatwierdź i scal PR #1, #2 i #3 do `main`  
   (możesz to zrobić na stronie GitHub w zakładce Pull Requests)

2. **Opublikowanie GitHub Release** – po scaleniu utwórz tag `v1.0.0`:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
   Workflow CI automatycznie zbuduje i opublikuje APK w sekcji Releases.

3. **Oficjalny link** pojawi się pod adresem:  
   `https://github.com/tomekmvr/forex-ai-agent/releases/latest`

---

## Ograniczenia MVP

- Statyczna baza 15 fotoradarów (brak automatycznej synchronizacji z CANARD)
- Brak filtrowania po kierunku jazdy
- Ekran Android Auto wymaga biblioteki Car App Library (zablokowana przez środowisko bez Google Maven)
- Wymagana zgoda użytkownika na "nieznane źródła" podczas instalacji
