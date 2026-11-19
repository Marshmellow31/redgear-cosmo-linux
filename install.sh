#!/bin/sh
set -e
D=$(dirname "$(readlink -f "$0")")
install -Dm755 "$D/bin/cosmo-panel" ~/.local/bin/cosmo-panel
install -Dm755 "$D/bin/cosmo-ctl" ~/.local/bin/cosmo-ctl
install -Dm755 "$D/bin/cosmo-daemon" ~/.local/bin/cosmo-daemon
install -Dm644 "$D/lib/cosmolib.py" ~/.local/share/redgear-cosmo/lib/cosmolib.py
install -Dm644 "$D/share/redgear-cosmo.desktop" ~/.local/share/applications/redgear-cosmo.desktop
install -Dm644 "$D/share/redgear-cosmo.service" ~/.config/systemd/user/redgear-cosmo.service
EXT=~/.local/share/gnome-shell/extensions/redgear-cosmo@local
mkdir -p "$EXT" && cp "$D"/gnome-extension/* "$EXT"/
systemctl --user daemon-reload
sudo install -Dm644 "$D/share/99-redgear-cosmo.rules" /etc/udev/rules.d/99-redgear-cosmo.rules
sudo udevadm control --reload && sudo udevadm trigger -s usb
echo "Installed. Log out and back in once to load the top-bar icon, then:"
echo "  gnome-extensions enable redgear-cosmo@local"
echo "Replug the headset to test."
