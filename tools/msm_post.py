#!/usr/bin/env python3
"""Schedule a reel on Ahmed's MSM platform (https://msm.amrbdr.com/api/v1).

Token: read from env MSM_TOKEN or the file ~/.msm_token (never commit it).

Usage:
  python3 tools/msm_post.py channels
  python3 tools/msm_post.py list
  python3 tools/msm_post.py post spec.json        # one post
  python3 tools/msm_post.py post specs.json       # a JSON list of posts

Spec fields (one post):
  video_url      public mp4 url (raw.githubusercontent of this repo)
  caption        full caption text
  at_cairo       "YYYY-MM-DDTHH:MM" Cairo local time  (or "now")
  yt_title       YouTube Short title
  yt_tags        list of tags
  fb_title       Facebook reel title
  first_comment  optional first comment (FB + IG)
  platforms      optional, default ["youtube","facebook","instagram"]
                 (TikTok stays on Metricool until the right account is linked)

Channel ids (brand 1 "ayah brand"): facebook=1, instagram=2, youtube=3,
tiktok=4 (currently the WRONG account "Amr Bdreldin" -> do not use).
"""
import json, os, sys, urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://msm.amrbdr.com/api/v1"
CHANNELS = {"facebook": 1, "instagram": 2, "youtube": 3}
CAIRO = timezone(timedelta(hours=2))  # Egypt has no DST in Nov–Apr; re-check in summer


def token():
    t = os.environ.get("MSM_TOKEN")
    if not t:
        p = os.path.expanduser("~/.msm_token")
        if os.path.exists(p):
            t = open(p).read().strip()
    if not t:
        sys.exit("MSM token missing: set MSM_TOKEN or write ~/.msm_token")
    return t


def call(method, path, body=None):
    req = urllib.request.Request(
        BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + token(), "Accept": "application/json",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"status": False, "http": e.code, "body": e.read().decode("utf-8", "replace")}


def build(spec):
    plats = spec.get("platforms", ["youtube", "facebook", "instagram"])
    targets = []
    for p in plats:
        if p == "youtube":
            targets.append({"channel_id": 3, "format": "short", "options": {
                "title": spec["yt_title"], "privacy": "public",
                "tags": spec.get("yt_tags", []), "made_for_kids": False,
                "contains_synthetic_media": False}})
        elif p == "facebook":
            o = {"title": spec.get("fb_title", spec["yt_title"])}
            if spec.get("first_comment"):
                o["first_comment"] = spec["first_comment"]
            targets.append({"channel_id": 1, "format": "reel", "options": o})
        elif p == "instagram":
            o = {"share_to_feed": True}
            if spec.get("first_comment"):
                o["first_comment"] = spec["first_comment"]
            targets.append({"channel_id": 2, "format": "reel", "options": o})
        else:
            sys.exit("unsupported platform here: " + p)
    body = {"brand_id": 1, "caption": spec["caption"],
            "media_urls": [spec["video_url"]], "targets": targets}
    if spec.get("at_cairo", "now") == "now":
        body["action"] = "publish_now"
    else:
        local = datetime.fromisoformat(spec["at_cairo"]).replace(tzinfo=CAIRO)
        body["action"] = "schedule"
        body["scheduled_at"] = local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return body


def summary(resp):
    d = resp.get("data") or {}
    if not resp.get("status"):
        return "FAILED " + json.dumps(resp, ensure_ascii=False)[:800]
    return "%s id=%s %s at=%s %s" % (
        resp.get("message"), d.get("id"), d.get("status"), d.get("scheduled_at"),
        [(t["channel"]["platform"], t["status"], t.get("error_message")) for t in d.get("targets", [])])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "channels"
    if cmd == "channels":
        for c in call("GET", "/channels").get("data", []):
            print(c["id"], c["platform"], c["name"], c["username"], c["status"])
    elif cmd == "list":
        r = call("GET", "/posts?status=scheduled")
        for p in r.get("data", []) if isinstance(r.get("data"), list) else []:
            print(p["id"], p["status"], p["scheduled_at"],
                  [(t["channel"]["platform"], t["status"]) for t in p["targets"]])
    elif cmd == "post":
        specs = json.load(open(sys.argv[2]))
        for s in specs if isinstance(specs, list) else [specs]:
            body = build(s)
            print(summary(call("POST", "/posts", body)))
            # FB story must be its OWN post: the API keeps only one target per
            # channel, so reel+story in one post silently drops the reel.
            if s.get("fb_story", True) and "facebook" in s.get("platforms", ["facebook"]):
                sb = {k: v for k, v in body.items() if k != "targets"}
                sb["caption"] = ""
                sb["targets"] = [{"channel_id": 1, "format": "story",
                                  "options": {"is_ai_generated": False}}]
                print("  story:", summary(call("POST", "/posts", sb)))
    else:
        sys.exit(__doc__)
