"""Shared logic for RedGear Cosmo 7.1: config, ALSA mixer, PipeWire FX graph generation."""
import json, math, os, re, subprocess, wave

CFG = os.path.expanduser("~/.config/redgear-cosmo/config.json")
RUNCONF = os.path.expanduser("~/.config/redgear-cosmo/fx.conf")
PIDFILE = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "redgear-cosmo.pid")
OUT_NODE = "alsa_output.usb-C-Media_Electronics_Inc._USB_Audio_Device-00.analog-stereo"
IN_NODE = "alsa_input.usb-C-Media_Electronics_Inc._USB_Audio_Device-00.mono-fallback"
BANDS = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
PROFILES = {  # from the Windows app's profile/default/*.profile
    "Default": [0] * 10,
    "HiFi": [0] * 10,
    "Movie": [-6, 0, 4, 0, 0, 0, 0, 0, 2, 1],
    "Music": [-6, 0, 4, 8, 9, 9, 5, 3, 2, 1],
}
SPEAKERS = [  # name, azimuth deg, wav
    ("Front Left", -30, "L-Front"), ("Front Right", 30, "R-Front"),
    ("Center", 0, "Center"), ("Subwoofer", 0, "Subwoofer"),
    ("Rear Left", -150, "L-BackSurround"), ("Rear Right", 150, "R-BackSurround"),
    ("Side Left", -90, "L-Surround"), ("Side Right", 90, "R-Surround"),
]
DEFAULTS = {"profile": "Default", "eq": [0] * 10, "bass": 0, "virtual71": False,
            "dist": [26, 26, 26, 24, 26, 26, 26, 26], "karaoke": False,
            "mic_boost": 0, "mic_nr": False, "mic_echo": False,
            "vol": None, "mute": None, "mic_vol": None, "mic_mute": None, "agc": None}

def load():
    c = dict(DEFAULTS)
    try: c.update(json.load(open(CFG)))
    except Exception: pass
    return c

def save(c):
    os.makedirs(os.path.dirname(CFG), exist_ok=True)
    json.dump(c, open(CFG, "w"), indent=1)

def update(**kw):
    """Merge changes into the saved config (fresh read, so panel/tray/CLI never clobber each other)."""
    c = load(); c.update(kw); save(c); return c

def reload_daemon():
    import signal
    p = daemon_pid()
    if p: os.kill(p, signal.SIGHUP)
    return p

def apply_hw(c):
    """Restore the remembered hardware mixer state (volume, mute, mic, AGC)."""
    if c.get("vol") is not None: amix("Speaker", f"{c['vol']}%")
    if c.get("mute") is not None: amix("Speaker", "mute" if c["mute"] else "unmute")
    if c.get("mic_vol") is not None: amix("Mic", f"{c['mic_vol']}%", "cap")
    if c.get("mic_mute") is not None: amix("Mic", "nocap" if c["mic_mute"] else "cap")
    if c.get("agc") is not None: amix("Auto Gain Control", "on" if c["agc"] else "off")

def run(*a):
    try: return subprocess.run(a, capture_output=True, text=True).stdout
    except FileNotFoundError: return ""

def card():
    try:
        for l in open("/proc/asound/cards"):
            m = re.match(r"\s*(\d+) \[\w+\s*\]:.*USB-Audio.*", l)
            if m and "C-Media" in open("/proc/asound/cards").read(): return m.group(1)
    except OSError: pass

def amix(ctl, *v):
    c = card()
    return run("amixer", "-c", c, "sset", ctl, *v) if c else ""

def amget(ctl):
    c = card(); out = run("amixer", "-c", c, "sget", ctl) if c else ""
    m = re.search(r"\[(\d+)%\]", out)
    return (int(m.group(1)) if m else 0), "[on]" in out

# ---- PipeWire graph ----
def _n(name, label, ctl=None, cfg=None):
    s = f'{{ type = builtin name = {name} label = {label}'
    if cfg: s += f' config = {{ {cfg} }}'
    if ctl: s += " control = { " + " ".join(f'"{k}" = {v}' for k, v in ctl.items()) + " }"
    return s + " }"

def sink_graph(c):
    nodes, links = [], []
    L = lambda o, i: links.append(f'{{ output = "{o}" input = "{i}" }}')
    ins = ["FL", "FR", "FC", "LFE", "RL", "RR", "SL", "SR"]
    chan = {"FL": 0, "FR": 1, "FC": 2, "LFE": 3, "RL": 4, "RR": 5, "SL": 6, "SR": 7}
    # input copy nodes
    for k in ins: nodes.append(_n(f"in{k}", "copy"))
    nodes += [_n("mixL", "mixer"), _n("mixR", "mixer")]
    gl, gr = [0.0] * 8, [0.0] * 8
    if c["virtual71"]:
        for idx, (name, az, _) in enumerate(SPEAKERS):
            k = ins[idx]; d = max(1, c["dist"][idx])
            s = abs(math.sin(math.radians(az)))
            near = 1 - (1 - 0.707) * (1 - s); far = 0.707 - 0.36 * s if s else near
            if k == "LFE": near = far = 0.707
            g = min(2.0, 26.0 / d)
            dl = min(0.02, d * 0.00029)
            nodes.append(_n(f"d{k}", "delay", {"Delay (s)": f"{dl:.5f}"}, "max-delay = 0.03"))
            L(f"in{k}:Out", f"d{k}:In")
            left_side = az < 0 or (az == 0)
            ipsi, contra = ("L", "R") if az < 0 else ("R", "L")
            if az == 0:
                gl[idx] = gr[idx] = near * g
                L(f"d{k}:Out", f"mixL:In {idx+1}"); L(f"d{k}:Out", f"mixR:In {idx+1}")
                continue
            nodes.append(_n(f"t{k}", "delay", {"Delay (s)": f"{0.00066 * s:.6f}"}, "max-delay = 0.002"))
            nodes.append(_n(f"f{k}", "bq_lowpass", {"Freq": 1500 + 4500 * (1 - s), "Q": 0.7, "Gain": 0}))
            L(f"d{k}:Out", f"t{k}:In"); L(f"t{k}:Out", f"f{k}:In")
            # ipsilateral ear directly, contralateral through ITD + head-shadow lowpass
            if ipsi == "L":
                gl[idx] = near * g; gr[idx] = far * g
                L(f"d{k}:Out", f"mixL:In {idx+1}"); L(f"f{k}:Out", f"mixR:In {idx+1}")
            else:
                gr[idx] = near * g; gl[idx] = far * g
                L(f"d{k}:Out", f"mixR:In {idx+1}"); L(f"f{k}:Out", f"mixL:In {idx+1}")
        if c["dist"][3]:
            pass
        # LFE through a lowpass is already implied by the speaker source; keep gain only
    else:
        gl = [1.0, 0, 0.707, 0.5, 0.707, 0, 0.707, 0]
        gr = [0, 1.0, 0.707, 0.5, 0, 0.707, 0, 0.707]
        for idx, k in enumerate(ins):
            if gl[idx]: L(f"in{k}:Out", f"mixL:In {idx+1}")
            if gr[idx]: L(f"in{k}:Out", f"mixR:In {idx+1}")
    ctl_l = {f"Gain {i+1}": f"{gl[i]:.4f}" for i in range(8)}
    ctl_r = {f"Gain {i+1}": f"{gr[i]:.4f}" for i in range(8)}
    nodes[len(ins)] = _n("mixL", "mixer", ctl_l); nodes[len(ins) + 1] = _n("mixR", "mixer", ctl_r)
    last = {"L": "mixL:Out", "R": "mixR:Out"}
    # karaoke: remove centre-panned vocals
    if c["karaoke"]:
        nodes += [_n("kL", "mixer", {"Gain 1": 1.0, "Gain 2": -0.9, "Gain 3": 0}),
                  _n("kR", "mixer", {"Gain 1": 1.0, "Gain 2": -0.9, "Gain 3": 0})]
        L(last["L"], "kL:In 1"); L(last["R"], "kL:In 2")
        L(last["R"], "kR:In 1"); L(last["L"], "kR:In 2")
        last = {"L": "kL:Out", "R": "kR:Out"}
    # EQ + bass boost
    eq = c["eq"]; steps = []
    for i, f in enumerate(BANDS):
        if eq[i]:
            lab = "bq_lowshelf" if i == 0 else "bq_highshelf" if i == 9 else "bq_peaking"
            steps.append((f"eq{i}", lab, {"Freq": f, "Q": 1.0, "Gain": eq[i]}))
    if c["bass"]:
        steps.append(("bass", "bq_lowshelf", {"Freq": 110, "Q": 0.7, "Gain": c["bass"]}))
    peak = max([0] + [s[2]["Gain"] for s in steps if s[2]["Gain"] > 0])
    steps.append(("head", "linear", {"Mult": f"{10 ** (-peak / 20):.4f}", "Add": 0}))
    for ch in "LR":
        for (nm, lab, ctl) in steps:
            nodes.append(_n(f"{nm}{ch}", lab, ctl)); L(last[ch], f"{nm}{ch}:In"); last[ch] = f"{nm}{ch}:Out"
    return nodes, links, last

def source_graph(c):
    nodes = [_n("hp", "bq_highpass", {"Freq": 140 if c["mic_nr"] else 20, "Q": 0.7, "Gain": 0}),
             _n("lp", "bq_lowpass", {"Freq": 7500 if c["mic_nr"] else 20000, "Q": 0.7, "Gain": 0}),
             _n("gain", "linear", {"Mult": f"{10 ** (c['mic_boost'] / 20):.4f}", "Add": 0})]
    links = ['{ output = "hp:Out" input = "lp:In" }', '{ output = "lp:Out" input = "gain:In" }']
    return nodes, links, "hp:In", "gain:Out"

def build_conf(c, with_mic=True):
    sn, sl, last = sink_graph(c)
    sink = f'''  {{ name = libpipewire-module-filter-chain
    args = {{
      node.description = "Cosmo FX (RedGear)"
      media.name = "Cosmo FX"
      filter.graph = {{ nodes = [ {" ".join(sn)} ] links = [ {" ".join(sl)} ]
        inputs = [ "inFL:In" "inFR:In" "inFC:In" "inLFE:In" "inRL:In" "inRR:In" "inSL:In" "inSR:In" ]
        outputs = [ "{last['L']}" "{last['R']}" ] }}
      capture.props = {{ node.name = "cosmo_fx" media.class = Audio/Sink audio.channels = 8
        audio.position = [ FL FR FC LFE RL RR SL SR ] }}
      playback.props = {{ node.name = "cosmo_fx_out" node.passive = true audio.position = [ FL FR ]
        target.object = "{OUT_NODE}" }}
    }} }}
'''
    mic = ""
    if with_mic:
        mn, ml, i, o = source_graph(c)
        mic = f'''  {{ name = libpipewire-module-filter-chain
    args = {{
      node.description = "Cosmo Mic (RedGear)"
      media.name = "Cosmo Mic"
      filter.graph = {{ nodes = [ {" ".join(mn)} ] links = [ {" ".join(ml)} ]
        inputs = [ "{i}" ] outputs = [ "{o}" ] }}
      capture.props = {{ node.name = "cosmo_mic_in" node.passive = true audio.position = [ MONO ]
        target.object = "{IN_NODE}" }}
      playback.props = {{ node.name = "cosmo_mic" media.class = Audio/Source audio.position = [ MONO ] }}
    }} }}
'''
    return f'''context.properties = {{ log.level = 1 }}
context.spa-libs = {{ audio.convert.* = audioconvert/libspa-audioconvert  support.* = support/libspa-support }}
context.modules = [
  {{ name = libpipewire-module-rt args = {{ nice.level = -11 }} flags = [ ifexists nofail ] }}
  {{ name = libpipewire-module-protocol-native }}
  {{ name = libpipewire-module-client-node }}
  {{ name = libpipewire-module-adapter }}
  {{ name = libpipewire-module-metadata }}
{sink}{mic}]
'''

def write_conf(c):
    os.makedirs(os.path.dirname(RUNCONF), exist_ok=True)
    open(RUNCONF, "w").write(build_conf(c))

def daemon_pid():
    try:
        p = int(open(PIDFILE).read())
        os.kill(p, 0); return p
    except Exception: return None

def speaker_test(idx, share=None):
    """Play a short beep (distinct pitch per speaker) on one channel of the 8ch Cosmo sink."""
    rate = 16000; freq = 440 + 110 * idx
    out = bytearray()
    for t in range(int(rate * 0.7)):
        env = min(1, t / 400, (int(rate * 0.7) - t) / 800)
        v = int(9000 * env * math.sin(2 * math.pi * freq * t / rate))
        for ch in range(8):
            out += (v if ch == idx else 0).to_bytes(2, "little", signed=True)
    p = os.path.expanduser("~/.cache/cosmo-test.wav")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    o = wave.open(p, "wb"); o.setnchannels(8); o.setsampwidth(2); o.setframerate(rate)
    o.writeframes(bytes(out)); o.close()
    subprocess.Popen(["pw-play", "--target", "cosmo_fx", p])
