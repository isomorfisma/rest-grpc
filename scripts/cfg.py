import json
import os


def _merge(a, b):
    out = dict(a)
    for k, v in b.items():
        out[k] = _merge(a[k], v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
    return out


def load():
    cfg = json.load(open(os.environ.get("CFG", "config/experiment.json")))
    over = os.environ.get("OVERRIDE")
    if over:
        cfg = _merge(cfg, json.load(open(over)))
    return cfg


def classes(cfg):
    return [c["name"] for c in cfg["payload_classes"]]


def protocols(cfg):
    return [p["name"] for p in cfg["protocols"]]


def seconds(t):
    return float(t[:-1]) * {"s": 1, "m": 60, "h": 3600}[t[-1]]


def suffix(cfg):
    """Akhiran nama berkas keluaran, diturunkan dari folder data mentah.

    raw/ -> ""            (eksperimen penuh)
    raw_pilot/ -> "_pilot"  (pilot test)
    Dengan begitu hasil pilot tidak pernah menimpa hasil eksperimen penuh.
    """
    raw = cfg["output"]["raw_dir"].rstrip("/")
    sisa = raw.removeprefix("raw").lstrip("_")
    return f"_{sisa}" if sisa else ""