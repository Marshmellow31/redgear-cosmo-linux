import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import GObject from 'gi://GObject';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {Slider} from 'resource:///org/gnome/shell/ui/slider.js';

const CTL = GLib.build_filenamev([GLib.get_home_dir(), '.local/bin/cosmo-ctl']);
const PANEL = GLib.build_filenamev([GLib.get_home_dir(), '.local/bin/cosmo-panel']);
const PROFILES = ['Default', 'HiFi', 'Movie', 'Music'];

function ctl(...args) {
    try { Gio.Subprocess.new([CTL, ...args], Gio.SubprocessFlags.NONE); } catch (e) { logError(e); }
}
function ctlGet(cb) {
    try {
        const p = Gio.Subprocess.new([CTL, 'get'], Gio.SubprocessFlags.STDOUT_PIPE);
        p.communicate_utf8_async(null, null, (proc, res) => {
            try { cb(JSON.parse(proc.communicate_utf8_finish(res)[1])); } catch (e) { /* ignore */ }
        });
    } catch (e) { logError(e); }
}

const Indicator = GObject.registerClass(
class CosmoIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'RedGear Cosmo 7.1');
        this.add_child(new St.Icon({icon_name: 'audio-headphones-symbolic', style_class: 'system-status-icon'}));
        this._busy = false;

        const volItem = new PopupMenu.PopupBaseMenuItem({activate: false});
        volItem.add_child(new St.Icon({icon_name: 'audio-volume-high-symbolic', style_class: 'popup-menu-icon'}));
        this._vol = new Slider(0.5);
        this._vol.connect('notify::value', () => { if (!this._busy) ctl('set', 'vol', String(Math.round(this._vol.value * 100))); });
        volItem.add_child(this._vol);
        this.menu.addMenuItem(volItem);

        this._sw = {};
        const add = (key, label) => {
            const it = new PopupMenu.PopupSwitchMenuItem(label, false);
            it.connect('toggled', (_i, state) => { if (!this._busy) ctl('set', key, state ? 'true' : 'false'); });
            this.menu.addMenuItem(it); this._sw[key] = it;
        };
        add('mute', 'Mute');
        add('virtual71', 'Virtual 7.1 surround');
        add('karaoke', 'Karaoke');
        add('mic_mute', 'Mute microphone');
        add('mic_nr', 'Mic noise reduction');

        this._prof = new PopupMenu.PopupSubMenuMenuItem('Profile');
        this._profItems = {};
        for (const p of PROFILES) {
            const it = new PopupMenu.PopupMenuItem(p);
            it.connect('activate', () => { ctl('profile', p); this._markProfile(p); });
            this._prof.menu.addMenuItem(it); this._profItems[p] = it;
        }
        this.menu.addMenuItem(this._prof);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        const open = new PopupMenu.PopupMenuItem('Open full panel…');
        open.connect('activate', () => { try { Gio.Subprocess.new([PANEL], Gio.SubprocessFlags.NONE); } catch (e) { logError(e); } });
        this.menu.addMenuItem(open);

        this.menu.connect('open-state-changed', (_m, open_) => { if (open_) this.refresh(); });
    }

    _markProfile(name) {
        for (const [p, it] of Object.entries(this._profItems))
            it.setOrnament(p === name ? PopupMenu.Ornament.DOT : PopupMenu.Ornament.NONE);
    }

    refresh() {
        ctlGet(c => {
            this._busy = true;
            this._vol.value = (c.vol ?? 50) / 100;
            for (const [k, it] of Object.entries(this._sw)) it.setToggleState(!!c[k]);
            this._markProfile(c.profile);
            this._busy = false;
        });
    }
});

export default class CosmoExtension extends Extension {
    enable() {
        this._ind = null;
        this._pid = GLib.build_filenamev([GLib.get_user_runtime_dir(), 'redgear-cosmo.pid']);
        this._tick();
        this._timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 3, () => { this._tick(); return GLib.SOURCE_CONTINUE; });
    }
    _tick() {
        const present = GLib.file_test(this._pid, GLib.FileTest.EXISTS);
        if (present && !this._ind) {
            this._ind = new Indicator();
            Main.panel.addToStatusArea(this.uuid, this._ind);
            this._ind.refresh();
        } else if (!present && this._ind) {
            this._ind.destroy(); this._ind = null;
        }
    }
    disable() {
        if (this._timer) GLib.source_remove(this._timer);
        this._timer = null;
        this._ind?.destroy(); this._ind = null;
    }
}
