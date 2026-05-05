#!/usr/bin/env bash
# Install Axon Remote bridge as a systemd service on a Raspberry Pi or any Linux box.
# Run as root (sudo).
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Please run as root: sudo $0"
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_DIR}/.venv"
ENV_FILE="${PROJECT_DIR}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Missing ${ENV_FILE}. Copy .env.example to .env and fill it in first."
    exit 1
fi

if [[ ! -d "${VENV_DIR}" ]]; then
    python3 -m venv "${VENV_DIR}"
    "${VENV_DIR}/bin/pip" install --upgrade pip
    "${VENV_DIR}/bin/pip" install -r "${PROJECT_DIR}/requirements.txt"
fi

UNIT_PATH="/etc/systemd/system/axon-bridge.service"
cat > "${UNIT_PATH}" <<UNIT
[Unit]
Description=Axon Remote — Wake-on-LAN bridge
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/python ${PROJECT_DIR}/bridge.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
User=$(logname 2>/dev/null || echo pi)

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable axon-bridge.service
systemctl restart axon-bridge.service

echo
echo "Installed and started axon-bridge.service."
echo "Tail logs:  journalctl -u axon-bridge.service -f"
