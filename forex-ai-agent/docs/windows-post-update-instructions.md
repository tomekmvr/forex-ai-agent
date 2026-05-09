# Windows Post-Update Instructions

Ten dokument opisuje, co trzeba zrobic na komputerze Windows po aktualizacji projektu z GitHub, jesli ten host ma dalej poprawnie uruchamiac panel, MT5 demo i runner agenta.

## Gdy aktualizacja zakonczyla sie poprawnie

Jesli uruchomiles:

```powershell
.\scripts\windows\update_from_github.ps1 -RestartPanel
```

to wykonaj po kolei:

1. Sprawdz, czy terminal MT5 jest uruchomiony i zalogowany na wlasciwe konto demo.
2. Sprawdz, czy plik `.env` nadal zawiera kompletne dane MT5 i OpenAI.
3. Zweryfikuj polaczenie z MT5:

```powershell
.\.venv\Scripts\python.exe -m src.execution.check_mt5_connection
```

4. Jesli panel nie zostal zrestartowany automatycznie, uruchom go recznie:

```powershell
.\.venv\Scripts\python.exe -m src.admin.run_http
```

5. Jesli runner nie jest odpalany przez Harmonogram zadan, uruchom testowo jeden reczny start:

```powershell
.\.venv\Scripts\python.exe -m src.runtime.agent_runner
```

6. Jesli runner dziala przez Harmonogram zadan, sprawdz log:

```text
logs/agent_runner.log
```

## Co ma byc prawda po aktualizacji

Po aktualizacji host powinien spelniac wszystkie warunki:

- panel otwiera sie na `http://127.0.0.1:8501`,
- `check_mt5_connection` nie zwraca bledu logowania ani bledu modulu `MetaTrader5`,
- runner nie konczy sie bledem fail-fast,
- OpenAI supervisor jest aktywny, jesli runner pracuje w `live`,
- log runnera pokazuje kolejne cykle albo swiezy reczny start.

## Najczestsze przyczyny problemow po aktualizacji

- MT5 nie jest uruchomiony albo konto demo nie jest zalogowane,
- `.env` zostal nadpisany albo jest niepelny,
- wirtualne srodowisko nie ma `MetaTrader5`,
- brakuje `OPENAI_API_KEY`,
- runner w `live` zostal uruchomiony bez `FOREX_AGENT_AI_DECISION_MODE=supervisor`.

## Minimalna komenda kontrolna po aktualizacji

Jesli chcesz wykonac tylko jedno szybkie sprawdzenie, uruchom:

```powershell
.\.venv\Scripts\python.exe -m src.execution.check_mt5_connection
```

Jesli to przechodzi, nastepny krok to panel albo runner, zaleznie od tego, czy host ma tylko pokazywac stan, czy tez wykonywac decyzje.