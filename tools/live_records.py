#!/usr/bin/env python3
"""Live public-source pull for the Records chair (Del's order, 2026-11-21).

Pulls what an internet detective pulls: public Reddit discussion
(via the Arctic Shift archive, since reddit.com blocks keyless
JSON from here) and, when a social search export is supplied,
public Instagram / Facebook / Threads posts about the subject.

Doctrine (SPEC3/SPEC6): public sources only, desk work only,
never contact. Every item carries a verbatim quote from its
source text. Reddit items are SOURCED (the post's own words).
Social items mined from a search summary are UNVERIFIED (a
summary of the post, not the post). Collisions are never
invented and never merged; a live pull reports none unless a
source itself shows a same-name different-person record.

Usage: live_records.py "FBG Duck" --subs Chiraqology,hiphopheads
       [--social-xml /path/to/export.xml] --out fixture.json
"""
import argparse, json, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

API = "https://arctic-shift.photon-reddit.com/api"

def fetch(path, params, tries=2):
    url = API + path + "?" + urllib.parse.urlencode(params)
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "murder-board-live-records/1.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                d = json.loads(r.read().decode("utf-8"))
            if d.get("data"):
                return d["data"]
        except Exception as e:
            print("fetch failed:", path, e, file=sys.stderr)
        time.sleep(4)
    return []

def excerpt(text, limit=240):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:limit]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subject")
    ap.add_argument("--subs", default="Chiraqology")
    ap.add_argument("--social-xml", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pulled = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    items, seen = [], set()
    for sub in [s.strip() for s in a.subs.split(",") if s.strip()]:
        for kind, path, params, bodykey in (
            ("post", "/posts/search", {"subreddit": sub, "title": a.subject, "limit": 6}, None),
            ("comment", "/comments/search", {"subreddit": sub, "body": a.subject, "limit": 6}, None),
        ):
            for rec in fetch(path, params):
                rid = rec.get("id")
                if not rid or rid in seen:
                    continue
                seen.add(rid)
                when = datetime.fromtimestamp(rec.get("created_utc", 0), timezone.utc).strftime("%Y-%m-%d")
                if kind == "post":
                    full = (rec.get("title", "") + "\n" + (rec.get("selftext") or "")).strip()
                    quote = excerpt(rec.get("title") or rec.get("selftext"))
                    title = "Reddit post, r/%s, u/%s, %s" % (sub, rec.get("author"), when)
                else:
                    full = (rec.get("body") or "").strip()
                    quote = excerpt(rec.get("body"))
                    title = "Reddit comment, r/%s, u/%s, %s" % (sub, rec.get("author"), when)
                if not quote:
                    continue
                link = "https://www.reddit.com" + (rec.get("permalink") or "")
                items.append({
                    "title": title, "type": "reddit_" + kind,
                    "source_name": "Reddit r/%s, live pull %s via Arctic Shift archive" % (sub, pulled),
                    "label": "SOURCED", "quote": quote,
                    "text": full + "\nSource: " + link,
                })
            time.sleep(3)
    if a.social_xml:
        raw = open(a.social_xml, encoding="utf-8", errors="replace").read()
        for block in raw.split("【")[1:5]:
            url = re.search(r"URL (\S+)", block)
            plat = re.search(r"(instagram|facebook|threads)", url.group(1) if url else "")
            ev = re.search(r"Events ([^\n]+)", block)
            if not (url and ev):
                continue
            quote = excerpt(ev.group(1), 200)
            items.append({
                "title": "Social post about the subject, " + (plat.group(1) if plat else "social"),
                "type": "social_post",
                "source_name": "Public social search export, " + pulled + " (summary of the post, not the post itself)",
                "label": "UNVERIFIED", "quote": quote,
                "text": quote + "\nSource: " + url.group(1),
            })
    fx = {
        "case_id": "live-social", "live": True, "pulled_at": pulled,
        "subject": {"name": a.subject, "aliases": [], "dob": "", "state": ""},
        "items": items[:14], "collisions": [],
    }
    with open(a.out, "w") as f:
        json.dump(fx, f, indent=1)
    print("live fixture:", len(fx["items"]), "items ->", a.out)

if __name__ == "__main__":
    main()
