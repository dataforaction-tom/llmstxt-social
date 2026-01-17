#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${1:-}"

if [[ -z "${DOMAIN}" ]]; then
  echo "Usage: ./deploy/scripts/setup-vm.sh yourdomain.com"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker..."
  sudo apt update && sudo apt upgrade -y
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
  sudo apt install -y docker-compose-plugin
fi

if ! command -v caddy >/dev/null 2>&1; then
  echo "Installing Caddy..."
  sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
  sudo apt update && sudo apt install -y caddy
fi

echo "Syncing repo to /opt/llmstxt-social..."
sudo mkdir -p /opt/llmstxt-social
sudo rsync -a --delete ./ /opt/llmstxt-social/

if [[ ! -f "/opt/llmstxt-social/.env" && -f "/opt/llmstxt-social/.env.production.example" ]]; then
  echo "Creating .env from .env.production.example"
  sudo cp /opt/llmstxt-social/.env.production.example /opt/llmstxt-social/.env
  sudo chown "$USER":"$USER" /opt/llmstxt-social/.env
  echo "Edit /opt/llmstxt-social/.env before starting the stack."
fi

echo "Configuring Caddy..."
sudo cp /opt/llmstxt-social/deploy/caddy/Caddyfile /etc/caddy/Caddyfile
sudo sed -i "s/yourdomain.com/${DOMAIN}/" /etc/caddy/Caddyfile
sudo systemctl reload caddy

echo "Installing systemd unit..."
sudo cp /opt/llmstxt-social/deploy/systemd/llmstxt.service /etc/systemd/system/llmstxt.service
sudo systemctl daemon-reload
sudo systemctl enable llmstxt.service
sudo systemctl start llmstxt.service

echo "Done. If Docker was just installed, re-login for group changes."
