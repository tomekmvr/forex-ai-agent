# Admin Panel

Panel admina jest lokalnym dashboardem Streamlit dla bieżącego stanu silnika Forex AI Agent.
Obsługuje tryb demo oraz tryb brokerski oparty o adapter nad warstwą execution.
Tryb brokerski działa obecnie dla OANDA v20 oraz TMS OANDA MT5.

## Uruchomienie

1. Utwórz i aktywuj środowisko wirtualne.
2. Zainstaluj zależności z requirements.txt.
3. Uruchom panel poleceniem:

```bash
streamlit run src/admin/app.py
```

Na Linux lub WSL możesz uruchomic od razu bezpieczny wariant demo:

```bash
python -m src.admin.run_linux_demo
```

Ten launcher wymusza `source_mode=demo` i `execution_mode=paper`, wiec panel dziala lokalnie nawet wtedy, gdy w `.env` masz profil MT5 bez relay.

## Dostęp przez HTTP

Panel jest teraz skonfigurowany do nasłuchu HTTP na `0.0.0.0:8501`.

Najprostszy start:

```bash
python -m src.admin.run_http
```

Domyślne adresy wejścia:

- lokalnie: `http://127.0.0.1:8501`
- z innego urządzenia w tej samej sieci: `http://IP_TWOJEGO_KOMPUTERA:8501`

Możesz też zmienić host i port zmiennymi środowiskowymi:

```bash
ADMIN_PANEL_HOST=0.0.0.0 ADMIN_PANEL_PORT=8601 python -m src.admin.run_http
```

## MT5 relay dla Linux lub WSL

Jeśli panel działa na Linux lub WSL, a terminal MT5 działa na Windows, użyj relay HTTP.

Układ jest prosty:

- Windows uruchamia lokalny terminal MT5 i proces relay,
- Linux lub WSL uruchamia panel admina i łączy się z relay po HTTP,
- agent nie potrzebuje wtedy lokalnego pakietu `MetaTrader5` po stronie Linux.

### Konfiguracja na Windows

W pliku `.env` na Windows ustaw zwykłe dane MT5:

```env
FOREX_AGENT_BROKER_PROFILE=tms_oanda_mt5
FOREX_AGENT_MT5_LOGIN=62398938
FOREX_AGENT_MT5_PASSWORD=twoje_haslo_mt5
FOREX_AGENT_MT5_SERVER=OANDATMS-MT5
FOREX_AGENT_MT5_TERMINAL_PATH=C:/Program Files/TMS OANDA MetaTrader 5/terminal64.exe
FOREX_AGENT_MT5_RELAY_TOKEN=twoj_wspolny_token
FOREX_AGENT_MT5_RELAY_BIND_HOST=127.0.0.1
FOREX_AGENT_MT5_RELAY_BIND_PORT=8765
```

Jeśli relay ma być dostępny z innego komputera w LAN, ustaw jawnie `FOREX_AGENT_MT5_RELAY_BIND_HOST=0.0.0.0` i otwórz port tylko w zaufanej sieci.

Start relay na Windows:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\windows\setup_mt5.ps1 -StartRelay
```

Albo ręcznie:

```powershell
.\.venv\Scripts\python.exe -m src.execution.mt5_relay
```

### Konfiguracja na Linux lub WSL

W pliku `.env` po stronie panelu ustaw relay zamiast lokalnego MT5:

```env
FOREX_AGENT_BROKER_PROFILE=tms_oanda_mt5
FOREX_AGENT_MT5_RELAY_URL=http://IP_WINDOWS:8765
FOREX_AGENT_MT5_RELAY_TOKEN=twoj_wspolny_token
FOREX_AGENT_REQUEST_TIMEOUT_SECONDS=30
FOREX_AGENT_VERIFY_SSL=true
```

Przy tej konfiguracji lokalne pola `FOREX_AGENT_MT5_LOGIN`, `FOREX_AGENT_MT5_PASSWORD`, `FOREX_AGENT_MT5_SERVER` i `FOREX_AGENT_MT5_TERMINAL_PATH` nie są wymagane po stronie Linux lub WSL.

Test połączenia z relay:

```bash
python -m src.execution.check_mt5_connection
```

Start panelu po stronie Linux lub WSL:

```bash
python -m src.admin.run_http
```

## Dokładne komendy uruchomienia na Windows

PowerShell:

```powershell
cd C:\sciezka\do\forex-ai-agent
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install MetaTrader5
python -m src.execution.check_mt5_connection
python -m streamlit run src/admin/app.py
python -m src.admin.run_http
```

Jednolinijkowiec PowerShell z repo:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\windows\setup_mt5.ps1 -StartPanel
```

Wariant bez startu panelu:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\windows\setup_mt5.ps1
```

Wariant relay:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\windows\setup_mt5.ps1 -StartRelay
```

CMD:

```bat
cd C:\sciezka\do\forex-ai-agent
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install MetaTrader5
python -m src.execution.check_mt5_connection
python -m streamlit run src/admin/app.py
python -m src.admin.run_http
```

## Szybka konfiguracja .env dla TMS OANDA MT5

W lokalnym pliku `.env` ustaw:

```env
FOREX_AGENT_BROKER_PROFILE=tms_oanda_mt5
FOREX_AGENT_MT5_LOGIN=62398938
FOREX_AGENT_MT5_PASSWORD=twoje_haslo_mt5
FOREX_AGENT_MT5_SERVER=OANDATMS-MT5
FOREX_AGENT_MT5_TERMINAL_PATH=C:/Program Files/TMS OANDA MetaTrader 5/terminal64.exe
FOREX_AGENT_REQUEST_TIMEOUT_SECONDS=30
FOREX_AGENT_VERIFY_SSL=true
```

Następnie uruchom test połączenia:

```bash
python -m src.execution.check_mt5_connection
```

## Co pokazuje panel

- sygnał końcowy orchestratora,
- confidence i weighted score,
- rozbicie decyzji na sub-agentów,
- źródło danych i status adaptera,
- snapshot rachunku brokerskiego,
- otwarte pozycje i PnL,
- historia transakcji MT5,
- stan kill switch i drawdown bufor,
- formularz ręcznego zlecenia MT5 dla symboli brokerskich,
- formularz zamykania otwartych pozycji MT5,
- wynik bramkowania ryzyka,
- sizing pozycji, budżet ryzyka i koszty transakcyjne,
- wejściowe newsy i kalendarz makro.

## Zabezpieczenia live

- panel ma tryb `paper` i `live`,
- w trybie `paper` zlecenia i zamknięcia są symulowane i nic nie jest wysyłane do brokera,
- w trybie `live` trzeba jawnie zaznaczyć potwierdzenie przed wysłaniem zlecenia albo zamknięciem pozycji.

## Tryby danych

- auto: najpierw próbuje adapter brokerski, a przy błędzie spada do demo,
- demo: wymusza dane lokalne bez połączenia z brokerem,
- broker: wymusza próbę pobrania danych z oficjalnego API brokera.

## Presety symboli MT5

Panel pod MT5 podpowiada symbole z rodziny TMS, takie jak `DE30.pro`, `US100.pro`, `GER40.pro`, `XAUUSD`, `EURUSD` i `GBPUSD`.

## Zmienne środowiskowe dla OANDA

- FOREX_AGENT_BROKER_PROFILE=oanda_practice albo oanda_live
- FOREX_AGENT_API_KEY=...
- FOREX_AGENT_ACCOUNT_ID=...
- FOREX_AGENT_REQUEST_TIMEOUT_SECONDS=30
- FOREX_AGENT_VERIFY_SSL=true

## Zmienne środowiskowe dla TMS OANDA MT5

- FOREX_AGENT_BROKER_PROFILE=tms_oanda_mt5
- FOREX_AGENT_MT5_LOGIN=62398938
- FOREX_AGENT_MT5_PASSWORD=...
- FOREX_AGENT_MT5_SERVER=OANDATMS-MT5
- FOREX_AGENT_MT5_TERMINAL_PATH=C:/Program Files/TMS OANDA MetaTrader 5/terminal64.exe
- FOREX_AGENT_MT5_RELAY_URL=http://IP_WINDOWS:8765
- FOREX_AGENT_MT5_RELAY_TOKEN=...

## Wymagania dla MT5

- terminal MetaTrader 5 musi być zainstalowany lokalnie,
- integracja Python działa przez pakiet MetaTrader5 i lokalny terminal,
- typowy scenariusz uruchomienia to Windows z uruchomionym terminalem MT5,
- pakiet MetaTrader5 nie jest dodany do `requirements.txt`, bo nie ma wspieranej dystrybucji dla Linux i WSL,
- relay HTTP pozwala wystawić MT5 z Windows do panelu działającego na Linux lub WSL,
- relay wymaga tokenu `FOREX_AGENT_MT5_RELAY_TOKEN` i domyślnie binduje się tylko do `127.0.0.1`,
- w tym repo adapter MT5 jest opcjonalny i nie zastępuje ścieżki OANDA v20.

## Ograniczenia

- adapter brokerski produkcyjny jest obecnie zaimplementowany dla profili OANDA,
- adapter MT5 wymaga lokalnego terminala i nie będzie działał wyłącznie przez web terminal TMS,
- panel nie podłącza się bezpośrednio do demo WebTrader w przeglądarce,
- poprawna integracja live powinna iść przez oficjalne API brokera, a nie przez automatyzację GUI.

## Deployment Na Inny Komputer

Jesli chcesz przeniesc projekt na inny host, podpiac domene pod router i wystawic panel, zobacz [docs/remote-deployment.md](../docs/remote-deployment.md).
