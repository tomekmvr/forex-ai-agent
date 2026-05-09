# Zdalny Deployment Na Inny Komputer

Ten dokument opisuje zalecany sposob przeniesienia projektu na inny komputer w tej samej sieci lub za routerem z domena.

## Wariant Windows-Only

Jesli docelowy komputer ma Windows i to na nim ma dzialac caly projekt, przyjmij ten uklad jako podstawowy:

1. Windows host:
   - trzyma repo,
   - uruchamia panel admina,
   - opcjonalnie uruchamia lokalny terminal MT5,
   - wystawia HTTPS przez reverse proxy, najlepiej Caddy.

2. Router:
   - przekierowuje tylko porty `80` i `443` do Windows hosta,
   - nie wystawia nic wiecej publicznie.

3. Domena:
   - wskazuje na publiczny adres IP routera,
   - reverse proxy na Windows host obsluguje TLS i przekazuje ruch do panelu na `127.0.0.1:8501`.

Jesli MT5 i panel dzialaja na tym samym Windows host, relay HTTP nie jest potrzebny.

### Szybki setup na Windows

Uzyj skryptu [scripts/windows/install_public_panel.ps1](../scripts/windows/install_public_panel.ps1):

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\windows\install_public_panel.ps1 -Domain panel.twoja-domena.pl -InstallCaddy
```

Ten skrypt:

- przygotuje `.venv`,
- zainstaluje zaleznosci,
- opcjonalnie doinstaluje `MetaTrader5`,
- wygeneruje `Caddyfile`,
- poda gotowe polecenia do uruchomienia panelu i reverse proxy.

### Automatyczna aktualizacja z GitHub na Windows

Uzyj skryptu [scripts/windows/update_from_github.ps1](../scripts/windows/update_from_github.ps1):

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\windows\update_from_github.ps1 -RestartPanel
```

Ten skrypt:

- pobiera zmiany z `origin/main`,
- robi `git pull --ff-only`,
- dogrywa zaleznosci z `requirements.txt`,
- opcjonalnie restartuje panel.

Jesli chcesz, zeby robilo sie to automatycznie, podepnij ten skrypt pod Harmonogram zadan Windows i ustaw trigger np. co 5 minut albo przy logowaniu.

Przyklad recznego odpalenia z innej galezi:

```powershell
.\scripts\windows\update_from_github.ps1 -Branch main -RestartPanel
```

### Autonomiczny runner agenta na Windows

Jesli serwer ma nie tylko hostowac panel, ale tez cyklicznie wykonywac decyzje tradingowe, uzyj:

```powershell
.\.venv\Scripts\python.exe -m src.runtime.agent_runner
```

Runner czyta ustawienia ze zmiennych `FOREX_AGENT_RUNNER_*` w `.env`, np.:

```env
FOREX_AGENT_RUNNER_SOURCE_MODE=broker
FOREX_AGENT_RUNNER_EXECUTION_MODE=paper
FOREX_AGENT_RUNNER_ENABLE_LIVE_EXECUTION=false
FOREX_AGENT_RUNNER_INSTRUMENT=DE30.pro
FOREX_AGENT_RUNNER_GRANULARITY=H1
FOREX_AGENT_RUNNER_PERIODS=120
FOREX_AGENT_RUNNER_ORDER_VOLUME=0.10
FOREX_AGENT_RUNNER_POLL_INTERVAL_SECONDS=300
FOREX_AGENT_RUNNER_RUN_ONCE=false
```

Jesli chcesz wykonywac prawdziwe zlecenia na koncie demo MT5, nie ustawiaj tutaj `paper`.
W tym przypadku poprawny wariant to `broker + live`, bo aplikacja ma wysylac zlecenia do terminala MT5, ale terminal jest zalogowany do rachunku demo.

Przyklad bezpiecznego startu dla MT5 demo:

```env
FOREX_AGENT_BROKER_PROFILE=tms_oanda_mt5
FOREX_AGENT_MT5_LOGIN=twoj_login_demo
FOREX_AGENT_MT5_PASSWORD=twoje_haslo_demo
FOREX_AGENT_MT5_SERVER=twoj_serwer_demo
FOREX_AGENT_MT5_TERMINAL_PATH=C:/Program Files/TMS OANDA MetaTrader 5/terminal64.exe
FOREX_AGENT_RUNNER_SOURCE_MODE=broker
FOREX_AGENT_RUNNER_EXECUTION_MODE=live
FOREX_AGENT_RUNNER_ENABLE_LIVE_EXECUTION=true
FOREX_AGENT_RUNNER_INSTRUMENT=DE30.pro
FOREX_AGENT_RUNNER_GRANULARITY=H1
FOREX_AGENT_RUNNER_PERIODS=120
FOREX_AGENT_RUNNER_ORDER_VOLUME=0.01
FOREX_AGENT_RUNNER_POLL_INTERVAL_SECONDS=300
FOREX_AGENT_RUNNER_RUN_ONCE=false
```

Do instalacji zadania Harmonogramu zadan uzyj:

```powershell
.\scripts\windows\install_agent_runner_task.ps1 -IntervalMinutes 15
```

Wariant startowy przy uruchomieniu systemu:

```powershell
.\scripts\windows\install_agent_runner_task.ps1 -AtStartup
```

### Konfiguracja .env na Windows-only

Jesli MT5 jest na tym samym hoście Windows:

```env
FOREX_AGENT_BROKER_PROFILE=tms_oanda_mt5
FOREX_AGENT_MT5_LOGIN=twoj_login_mt5
FOREX_AGENT_MT5_PASSWORD=twoje_haslo_mt5
FOREX_AGENT_MT5_SERVER=OANDATMS-MT5
FOREX_AGENT_MT5_TERMINAL_PATH=C:/Program Files/MetaTrader 5/terminal64.exe
FOREX_AGENT_REQUEST_TIMEOUT_SECONDS=30
FOREX_AGENT_VERIFY_SSL=true
OPENAI_API_KEY=twoj_nowy_klucz_openai
FOREX_AGENT_OPENAI_MODEL=gpt-4.1-mini
```

Jesli chcesz tylko panel demo bez MT5, wystarczy pominac pola MT5 i uruchomic panel.

### Reverse proxy na Windows

Uzyj przykladu z [deploy/caddy/Caddyfile.example](../deploy/caddy/Caddyfile.example).

Najprostsza konfiguracja:

```caddy
panel.twoja-domena.pl {
    reverse_proxy 127.0.0.1:8501
}
```

### Router i domena dla Windows-only

1. Rekord `A` domeny wskazuje na publiczne IP routera.
2. Router przekierowuje:
   - `80 -> IP_WINDOWS:80`
   - `443 -> IP_WINDOWS:443`
3. Panel dziala lokalnie na `127.0.0.1:8501` i nie musi byc wystawiany bezposrednio.

### Gdy MT5 jest na innym komputerze

Jesli MT5 pozostaje na osobnym Windows host, wtedy wracasz do architektury relay opisanej nizej.

## Zalecana architektura

Najbezpieczniejszy uklad dla tego projektu jest taki:

1. Linux host:
   - trzyma repo,
   - uruchamia panel admina,
   - wystawia HTTPS przez reverse proxy,
   - nie wystawia MT5 relay publicznie.

2. Windows host z MT5:
   - uruchamia terminal MetaTrader 5,
   - uruchamia MT5 relay,
   - udostepnia relay tylko do Linux hosta albo tylko w LAN.

3. Router:
   - przekierowuje port 80 i 443 tylko do Linux hosta,
   - nie przekierowuje portu relay `8765` do internetu.

4. Domena:
   - wskazuje na publiczny adres IP routera,
   - reverse proxy na Linux host obsluguje TLS i przekazuje ruch do panelu na `127.0.0.1:8501`.

## Czego nie robic

- Nie wystawiaj Streamlit bezposrednio na internet bez reverse proxy.
- Nie wystawiaj MT5 relay bezposrednio na internet.
- Nie zostawiaj relay bez tokenu.
- Nie kopiuj `.venv` miedzy komputerami. Przenos tylko kod i odtwarzaj srodowisko na nowym hoście.

## Migracja Projektu Na Drugi Komputer

Na nowym Linux host:

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip nginx
mkdir -p ~/apps
cd ~/apps
cp -r /sciezka/zrodlowa/forex-ai-agent ./forex-ai-agent
cd forex-ai-agent
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Jesli chcesz zautomatyzowac prawie caly Linux host jednym krokiem, uzyj:

```bash
sudo bash scripts/linux/install_public_panel.sh --domain twoja-domena.pl --project-dir /home/TWOJ_USER/apps/forex-ai-agent --user TWOJ_USER
```

Ten skrypt:

- zbuduje `.venv`,
- zainstaluje zaleznosci,
- wygeneruje service systemd,
- wygeneruje config Nginx,
- uruchomi panel lokalnie za reverse proxy.

Nadal recznie zostaja tylko:

- ustawienie DNS domeny,
- przekierowanie `80/443` na routerze,
- wystawienie certyfikatu TLS.

Jesli chcesz uruchamiac tylko panel demo, wystarczy skonfigurowac minimum i odpalic:

```bash
.venv/bin/python -m src.admin.run_linux_demo
```

Jesli panel ma laczyc sie do MT5 relay na Windows:

```env
FOREX_AGENT_BROKER_PROFILE=tms_oanda_mt5
FOREX_AGENT_MT5_RELAY_URL=http://IP_WINDOWS_LAN:8765
FOREX_AGENT_MT5_RELAY_TOKEN=twoj_wspolny_token
FOREX_AGENT_REQUEST_TIMEOUT_SECONDS=30
FOREX_AGENT_VERIFY_SSL=true
OPENAI_API_KEY=twoj_nowy_klucz_openai
FOREX_AGENT_OPENAI_MODEL=gpt-4.1-mini
```

## Reverse Proxy Z Nginx

Uzyj przykladu z [deploy/nginx/forex-ai-agent.conf.example](../deploy/nginx/forex-ai-agent.conf.example).

Albo pozwol skryptowi [scripts/linux/install_public_panel.sh](../scripts/linux/install_public_panel.sh) wygenerowac config automatycznie.

Zakladany przeplyw:

- publiczny ruch HTTPS trafia na `example.com`,
- Nginx terminates TLS,
- Nginx proxy pass do `http://127.0.0.1:8501`.

## Systemd Service

Uzyj przykladu z [deploy/systemd/forex-ai-agent-panel.service.example](../deploy/systemd/forex-ai-agent-panel.service.example).

Albo pozwol skryptowi [scripts/linux/install_public_panel.sh](../scripts/linux/install_public_panel.sh) wygenerowac service automatycznie.

Po dostosowaniu sciezek:

```bash
sudo cp deploy/systemd/forex-ai-agent-panel.service.example /etc/systemd/system/forex-ai-agent-panel.service
sudo systemctl daemon-reload
sudo systemctl enable --now forex-ai-agent-panel.service
sudo systemctl status forex-ai-agent-panel.service
```

## Domena I Router

Masz dwa warianty:

1. Publiczna domena z DDNS:
   - kupujesz domenę albo używasz DDNS,
   - rekord `A` wskazuje na publiczny IP routera,
   - router przekierowuje `80` i `443` do Linux hosta,
   - certyfikat robisz przez Let's Encrypt.

2. Domena tylko lokalna:
   - ustawiasz lokalny DNS w routerze albo wpisy w `hosts`,
   - domena wskazuje na IP Linux hosta w LAN,
   - nie wystawiasz tego do internetu.

## Dostep Dla Mnie Do Tego Komputera

Nie moge samodzielnie polaczyc sie do innego komputera poza biezacym srodowiskiem.
Moge jednak pomagac dalej na dwa sposoby:

1. Otworzysz repo z tego nowego komputera w VS Code i wtedy bede pracowal w tamtym workspace.
2. Skonfigurujesz zdalny VS Code SSH albo tunnel i otworzysz ten host jako biezace srodowisko robocze.

## Zalecany finalny uklad

1. Linux host z domena i panelem pod HTTPS.
2. Windows host z MT5 relay tylko w LAN.
3. Router forwarduje tylko `80/443` do Linux hosta.
4. Relay `8765` pozostaje niewystawiony publicznie.