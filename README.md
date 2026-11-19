<p align="center"><img src="assets/logo.svg" width="128" alt="logo"></p>

# RedGear Cosmo 7.1 for Linux

A tiny control panel and effects engine for the **RedGear Cosmo 7.1** USB headset
(C-Media chip, USB ID `0d8c:0012`) on Linux. It replaces the Windows-only
"RedGear Cosmo" software and starts automatically when you plug the headset in.

## What it is

The Windows package ships a C-Media driver plus an app whose effects (EQ, virtual
speakers, mic filters) are software DSP running on the PC. They are not hardware commands.
Linux already drives the headset with `snd-usb-audio` and `usbhid`, so no kernel
driver is needed. This project rebuilds the app's features on top of ALSA and PipeWire.

| Tab | Features |
|---|---|
| Playback | Volume, mute, bass boost, karaoke (vocal reduction) |
| Equalizer | 10-band EQ with the original Default / HiFi / Movie / Music presets |
| Virtual 7.1 | Headphone surround from 8 virtual speakers, per-speaker distance, speaker test beeps |
| Microphone | Volume, mute, auto gain, boost, noise reduction |

Not included: the licensed Dolby / DTS / Xear modes, echo cancellation, beamforming
and Magic Voice.

## Top bar (GNOME)

A small GNOME Shell extension adds a headphone icon to the top bar while the headset is plugged in.
Its menu has volume, mute, virtual 7.1, karaoke, mic mute, noise reduction, profiles, and a link to the full panel.
`install.sh` installs it. Log out and back in once (Wayland), then run `gnome-extensions enable redgear-cosmo@local`.

All settings are remembered in `~/.config/redgear-cosmo/config.json` and restored on every plug-in.

## How it works

- `cosmo-daemon` runs a private PipeWire filter-chain ("Cosmo FX" sink and "Cosmo Mic"
  source) while the headset is connected, and exits when it is unplugged.
- `cosmo-panel` is a light GTK3 window that edits `~/.config/redgear-cosmo/config.json`
  and signals the daemon to reload.
- A udev rule starts a systemd user service on plug-in.

## Install

Requires PipeWire with WirePlumber, `alsa-utils`, Python 3 with PyGObject (GTK 3).

```bash
git clone https://github.com/Marshmellow31/redgear-cosmo-linux
cd redgear-cosmo-linux
./install.sh   # asks for sudo once, to install the udev rule
```

Replug the headset; the panel opens. Or launch **RedGear Cosmo 7.1** from your app menu.

## Notes

- Tested on Ubuntu with GNOME on Wayland and PipeWire 1.6. Other setups may need tweaks.
- Applying settings reloads the effects graph, so audio may drop for a moment.
- Unofficial and not affiliated with RedGear or C-Media. No vendor files are included.

## License

MIT
