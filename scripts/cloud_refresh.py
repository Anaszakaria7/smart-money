#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cloud_refresh.py — kemas kini awan (GitHub Actions) bila PC off.

Tarik: SPY/QQQ/IWM/SMH (Yahoo chart) + XAU/XAG
       (FCSAPI bila FCSAPI_KEY ada & waktu AS; fallback gold-api.com; fallback Yahoo GC=F/SI=F).
Tulis: data/cloud_refresh.json — laman (index.html) baca fail ini secara fetch;
overlay hanya aktif bila build laman > 60 min dan data awan < 4j.
Guna: python scripts/cloud_refresh.py   (env pilihan: FCSAPI_KEY, FCSAPI_FORCE=1)
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "cloud_refresh.json"
MYT = timezone(timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) smart-money-cloud/1.1"}
ETFS = ["SPY", "QQQ", "IWM", "SMH"]
FCSAPI_KEY = os.environ.get("FCSAPI_KEY", "").strip()
_FCS_CACHE = {}
_FCS_TRIED = False


def get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def yahoo_quote(sym):
    u = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d"
    j = json.loads(get(u))
    m = j["chart"]["result"][0]["meta"]
    p = m.get("regularMarketPrice")
    c = m.get("regularMarketChangePercent")
    if p is None:
        return None
    return {"p": round(float(p), 2), "chg": round(float(c), 2) if c is not None else None}


def in_us_hours(now_utc):
    """Sesi AS lebih kurang: Isnin-Jumaat 13:30-20:00 UTC (kiraan tepat, jimat kuota)."""
    if now_utc.weekday() >= 5:
        return False
    m = now_utc.hour * 60 + now_utc.minute
    return 13 * 60 + 30 <= m <= 20 * 60


def _num(v):
    try:
        return float(str(v).replace("%", "").replace(",", ""))
    except Exception:
        return None


def _price_of(item):
    for k in ("price", "c", "close", "last", "p"):
        v = _num(item.get(k))
        if v and v > 0:
            return v
    return None


def _chg_of(item):
    for k in ("chp", "ch", "change_percent", "change_pct", "pc"):
        v = _num(item.get(k))
        if v is not None:
            return round(v, 2)
    return None


def fcsapi_metals():
    """XAU/XAG via FCSAPI (bulk = 1 kredit). {} jika tiada kunci / gagal (dicuba sekali sahaja)."""
    global _FCS_CACHE, _FCS_TRIED
    if _FCS_CACHE:
        return _FCS_CACHE
    if _FCS_TRIED or not FCSAPI_KEY:
        return {}
    _FCS_TRIED = True
    qs = urllib.parse.urlencode({"symbol": "XAU/USD,XAG/USD", "access_key": FCSAPI_KEY})
    try:
        j = json.loads(get(f"https://api-v4.fcsapi.com/forex/latest?{qs}", timeout=25))
    except Exception as e:
        print(f"warn fcsapi: {e}")
        return {}
    rows = []
    for k in ("data", "response", "result", "list"):
        v = j.get(k)
        if isinstance(v, list):
            rows = v
            break
    if not rows and isinstance(j.get("data"), dict):
        rows = [j["data"]]
    out = {}
    for it in rows:
        if not isinstance(it, dict):
            continue
        sym = str(it.get("symbol") or it.get("s") or it.get("id") or "").upper()
        p = _price_of(it)
        if p is None:
            continue
        for m in ("XAU", "XAG"):
            if m in sym or (m == "XAU" and "GOLD" in sym) or (m == "XAG" and "SILVER" in sym):
                out[m] = {"p": round(p, 2), "chg": _chg_of(it), "src": "fcsapi"}
    _FCS_CACHE = out
    return out


def metal(sym, fcs=None):
    if fcs and sym in fcs:
        return fcs[sym]
    try:
        j = json.loads(get(f"https://api.gold-api.com/price/{sym}"))
        p = float(j["price"])
        if p > 0:
            return {"p": round(p, 2), "src": "gold-api"}
    except Exception:
        pass
    if FCSAPI_KEY:
        r = fcsapi_metals()  # rescue (cth di luar waktu AS)
        if sym in r:
            return r[sym]
    fsym = "GC=F" if sym == "XAU" else "SI=F"
    q = yahoo_quote(fsym)
    return {"p": q["p"], "src": "yahoo:" + fsym} if q else None


def main():
    now_utc = datetime.now(timezone.utc)
    out = {"ts": datetime.now(MYT).isoformat(timespec="seconds"), "src": "cloud", "syms": {}, "metals": {}}
    ok = 0
    fcs = {}
    force = os.environ.get("FCSAPI_FORCE") == "1"
    if FCSAPI_KEY and (force or in_us_hours(now_utc)):
        fcs = fcsapi_metals()
        print(f"fcsapi: {len(fcs)} logam (waktu AS={'ya' if in_us_hours(now_utc) else 'paksa'})")
    for s in ETFS:
        try:
            q = yahoo_quote(s)
            if q:
                out["syms"][s] = q
                ok += 1
        except Exception as e:
            print(f"warn {s}: {e}")
    for m in ("XAU", "XAG"):
        try:
            v = metal(m, fcs)
            if v:
                out["metals"][m] = v
                ok += 1
        except Exception as e:
            print(f"warn {m}: {e}")
    if ok == 0:
        print("GAGAL: tiada data — tak tulis fail")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("TULIS:", OUT)
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
