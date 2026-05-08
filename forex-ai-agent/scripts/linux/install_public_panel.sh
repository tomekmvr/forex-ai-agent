#!/usr/bin/env bash

set -euo pipefail

DOMAIN=""
PROJECT_DIR="${PROJECT_DIR:-$HOME/apps/forex-ai-agent}"
SERVICE_USER="${SUDO_USER:-${USER}}"
SERVICE_GROUP=""
PANEL_PORT="8501"
INSTALL_PACKAGES="0"
ENABLE_SERVICE="1"

usage() {
  cat <<'EOF'
Usage:
  sudo bash scripts/linux/install_public_panel.sh --domain example.com [options]

Options:
  --domain DOMAIN           Public domain for the panel
  --project-dir PATH        Project path on the target Linux host
  --user USER               Linux user that should run the panel service
  --group GROUP             Linux group for the panel service (defaults to USER)
  --panel-port PORT         Internal panel port, default 8501
  --install-packages        Install python3-venv and nginx with apt
  --skip-service-enable     Render configs without enabling systemd service

What this script does:
  1. Ensures project venv and dependencies exist
  2. Renders a systemd service for the panel
  3. Renders an nginx site config for the domain
  4. Enables nginx config and optionally starts the panel service

What this script does NOT do:
  - Does not configure your router
  - Does not update DNS at your registrar
  - Does not request a Let's Encrypt certificate automatically
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      DOMAIN="$2"
      shift 2
      ;;
    --project-dir)
      PROJECT_DIR="$2"
      shift 2
      ;;
    --user)
      SERVICE_USER="$2"
      shift 2
      ;;
    --group)
      SERVICE_GROUP="$2"
      shift 2
      ;;
    --panel-port)
      PANEL_PORT="$2"
      shift 2
      ;;
    --install-packages)
      INSTALL_PACKAGES="1"
      shift
      ;;
    --skip-service-enable)
      ENABLE_SERVICE="0"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$DOMAIN" ]]; then
  echo "Missing required --domain" >&2
  usage >&2
  exit 1
fi

if [[ -z "$SERVICE_GROUP" ]]; then
  SERVICE_GROUP="$SERVICE_USER"
fi

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "Project directory does not exist: $PROJECT_DIR" >&2
  exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this script with sudo/root." >&2
  exit 1
fi

if [[ "$INSTALL_PACKAGES" == "1" ]]; then
  apt update
  apt install -y python3 python3-venv python3-pip nginx
fi

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  echo "Linux user does not exist: $SERVICE_USER" >&2
  exit 1
fi

if [[ ! -f "$PROJECT_DIR/.env" ]]; then
  cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
  chown "$SERVICE_USER:$SERVICE_GROUP" "$PROJECT_DIR/.env"
fi

sudo -u "$SERVICE_USER" bash -lc "cd '$PROJECT_DIR' && python3 -m venv .venv && . .venv/bin/activate && python -m pip install --upgrade pip && python -m pip install -r requirements.txt"

SERVICE_PATH="/etc/systemd/system/forex-ai-agent-panel.service"
cat > "$SERVICE_PATH" <<EOF
[Unit]
Description=Forex AI Agent Admin Panel
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$PROJECT_DIR
Environment=ADMIN_PANEL_HOST=127.0.0.1
Environment=ADMIN_PANEL_PORT=$PANEL_PORT
ExecStart=$PROJECT_DIR/.venv/bin/python -m src.admin.run_http
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

NGINX_PATH="/etc/nginx/sites-available/forex-ai-agent.conf"
cat > "$NGINX_PATH" <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        proxy_pass http://127.0.0.1:$PANEL_PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600;
        proxy_send_timeout 3600;
    }
}
EOF

ln -sfn "$NGINX_PATH" /etc/nginx/sites-enabled/forex-ai-agent.conf
rm -f /etc/nginx/sites-enabled/default

systemctl daemon-reload
if [[ "$ENABLE_SERVICE" == "1" ]]; then
  systemctl enable --now forex-ai-agent-panel.service
fi

nginx -t
systemctl reload nginx

echo
echo "Linux host configuration complete."
echo "Domain: $DOMAIN"
echo "Project: $PROJECT_DIR"
echo "Systemd: $SERVICE_PATH"
echo "Nginx: $NGINX_PATH"
echo
echo "Next external steps you still must do manually:"
echo "1. Point DNS for $DOMAIN to your router public IP."
echo "2. Forward router ports 80 and 443 to this Linux host."
echo "3. Install TLS certificate, e.g. certbot --nginx -d $DOMAIN"
echo "4. If using MT5 relay, keep port 8765 private and only reachable in LAN."