#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cloud_refresh.py — kemas kini awan (GitHub Actions) bila PC off.

Tarik: SPY/QQQ/IWM/SMH (Yahoo chart) + XAU/XAG (gold-api.com; fallback Yahoo GC=F/SI=F).
Tulis: data/cloud_refresh.json — laman (index.html) baca fail ini secara fetch;
overlay hanya aktif bila build laman > 60 min dan data awan < 4j.
Guna: python scripts/cloud_refresh.py
"""
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "cloud_refresh.json"
MYT = timezone(timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) smart-money-cloud/1.0"}
ETFS = ["SPY", "QQQ", "IWM", "SMH"]


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


def metal(sym):
    try:
        j = json.loads(get(f"https://api.gold-api.com/price/{sym}"))
        p = float(j["price"])
        if p > 0:
            return {"p": round(p, 2), "src": "gold-api"}
    except Exception:
        pass
    fsym = "GC=F" if sym == "XAU" else "SI=F"
    q = yahoo_quote(fsym)
    return {"p": q["p"], "src": "yahoo:" + fsym} if q else None


def main():
    out = {"ts": datetime.now(MYT).isoformat(timespec="seconds"), "src": "cloud", "syms": {}, "metals": {}}
    ok = 0
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
            v = metal(m)
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
