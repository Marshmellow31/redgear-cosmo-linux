#!/bin/sh
set -e
D=$(dirname "$(readlink -f "$0")")
install -Dm755 "$D/bin/cosmo-panel" ~/.local/bin/cosmo-panel
install -Dm755 "$D/bin/cosmo-daemon" ~/.local/bin/cosmo-daemon
install -Dm644 "$D/lib/cosmolib.py" ~/.local/share/redgear-cosmo/lib/cosmolib.py
install -Dm644 "$D/share/redgear-cosmo.desktop" ~/.local/share/applications/redgear-cosmo.desktop
install -Dm644 "$D/share/redgear-cosmo.service" ~/.config/systemd/user/redgear-cosmo.service
systemctl --user daemon-reload
sudo install -Dm644 "$D/share/99-redgear-cosmo.rules" /etc/udev/rules.d/99-redgear-cosmo.rules
sudo udevadm control --reload && sudo udevadm trigger -s usb
echo "Installed. Replug the headset to test."
