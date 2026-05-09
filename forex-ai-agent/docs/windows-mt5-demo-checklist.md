# Windows MT5 Demo Checklist

Ta checklista zaklada, ze docelowy komputer to Windows, terminal MT5 jest na tym samym hoście i chcesz uruchomic panel oraz runner na koncie demo.

## 1. Pobierz aktualny kod

```powershell
cd C:\apps\forex-ai-agent
git pull
```

Repo powinno zawierac zmiany z OpenAI supervisor i runnerem autonomicznym.

## 2. Przygotuj srodowisko Python

Jesli nie masz jeszcze `.venv`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install MetaTrader5
```

Jesli `.venv` juz istnieje:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install MetaTrader5
```

## 3. Ustaw `.env`

W pliku `.env` ustaw minimalnie:

```dotenv
FOREX_AGENT_BROKER_PROFILE=tms_oanda_mt5
FOREX_AGENT_MT5_LOGIN=twoj_login_demo
FOREX_AGENT_MT5_PASSWORD=twoje_haslo_demo
FOREX_AGENT_MT5_SERVER=twoj_serwer_demo
FOREX_AGENT_MT5_TERMINAL_PATH=C:/Program Files/TMS OANDA MetaTrader 5/terminal64.exe
FOREX_AGENT_REQUEST_TIMEOUT_SECONDS=30
FOREX_AGENT_VERIFY_SSL=true

FOREX_AGENT_RUNNER_SOURCE_MODE=broker
FOREX_AGENT_RUNNER_EXECUTION_MODE=live
FOREX_AGENT_RUNNER_ENABLE_LIVE_EXECUTION=true
FOREX_AGENT_RUNNER_INSTRUMENT=DE30.pro
FOREX_AGENT_RUNNER_GRANULARITY=H1
FOREX_AGENT_RUNNER_PERIODS=120
FOREX_AGENT_RUNNER_ORDER_VOLUME=0.01
FOREX_AGENT_RUNNER_POLL_INTERVAL_SECONDS=300
FOREX_AGENT_RUNNER_RUN_ONCE=false

FOREX_AGENT_AI_PROVIDER=openai
OPENAI_API_KEY=twoj_klucz_openai
FOREX_AGENT_OPENAI_MODEL=gpt-4.1-mini
FOREX_AGENT_AI_DECISION_MODE=supervisor
```

Uwagi:
- `live` jest tutaj poprawne, bo zlecenia ida do terminala MT5 zalogowanego na konto demo.
- `paper` oznacza lokalna symulacje bez wysylki do MT5.
- zacznij od `FOREX_AGENT_RUNNER_ORDER_VOLUME=0.01`.

## 4. Sprawdz terminal MT5

Przed uruchomieniem aplikacji upewnij sie, ze:
- MT5 startuje poprawnie,
- konto demo jest zalogowane,
- symbol, na ktorym chcesz pracowac, jest widoczny w Market Watch,
- AutoTrading nie jest zablokowany polityka terminala albo brokera.

## 5. Zweryfikuj polaczenie z MT5

```powershell
.\.venv\Scripts\python.exe -m src.execution.check_mt5_connection
```

Oczekiwany wynik:
- brak bledu logowania,
- odczyt danych konta,
- brak informacji o brakujacym module `MetaTrader5`.

## 6. Uruchom panel recznie

```powershell
.\.venv\Scripts\python.exe -m src.admin.run_http
```

Sprawdz w przegladarce:
- `http://127.0.0.1:8501`

Na panelu potwierdz:
- saldo i equity sa wczytane z MT5,
- pozycje i historia sa widoczne,
- zrodlo danych nie jest fallbackiem demo.

## 7. Uruchom runner recznie

```powershell
.\.venv\Scripts\python.exe -m src.runtime.agent_runner
```

Pierwszy reczny start jest obowiazkowy. Nie zaczynaj od Harmonogramu zadan.

Sprawdz, czy:
- runner nie konczy sie bledem,
- logika pobiera snapshot brokerski,
- OpenAI supervisor nie powoduje wyjatku,
- decyzja koncowa jest drukowana jako JSON.

## 8. Sprawdz logike przed schedulerem

Jesli runner ma decyzje `final_signal=0`, to nie musi byc blad.
Przy aktywnym `FOREX_AGENT_AI_DECISION_MODE=supervisor` OpenAI moze swiadomie zablokowac trade.

To jest poprawne zachowanie, jesli:
- lokalne agenty nie maja mocnego konsensusu,
- OpenAI zwraca neutral,
- OpenAI nie potwierdza kierunku.

## 9. Dopiero teraz dodaj Harmonogram zadan

Cykl co 15 minut:

```powershell
.\scripts\windows\install_agent_runner_task.ps1 -IntervalMinutes 15
```

Albo start przy uruchomieniu systemu:

```powershell
.\scripts\windows\install_agent_runner_task.ps1 -AtStartup
```

## 10. Sprawdz log runnera

Log jest zapisywany do:

```text
logs/agent_runner.log
```

Po instalacji taska sprawdz, czy:
- plik logu powstaje,
- kolejne cykle sa dopisywane,
- nie ma petli bledow logowania MT5,
- nie ma bledow OpenAI ani timeoutow.

## 11. Minimalny warunek uznania wdrozenia za zakonczone

Mozesz uznac wdrozenie MT5 demo za zamkniete dopiero, gdy:
- panel czyta dane z MT5 demo,
- `check_mt5_connection` przechodzi,
- runner startuje recznie bez bledu,
- scheduler uruchamia runnera automatycznie,
- log `logs/agent_runner.log` zawiera kolejne cykle,
- OpenAI supervisor pracuje bez wyjatku,
- system nie wpada w fallback demo, jesli oczekujesz realnego polaczenia z MT5 demo.