"""Upload episodes to YouTube from a CSV manifest (YouTube Data API v3).

One row per video. Each row is uploaded, then gets its thumbnail, subtitles and
playlist (the playlist is created if it does not exist yet). Progress is kept in
<csv>.state.json next to the CSV, so a re-run resumes at the step that failed and
never uploads the same row twice.

Commands
  python yt_upload.py auth                 log in once (opens a browser) and show the channel
  python yt_upload.py list                 your uploads (title -> video id) and playlists
  python yt_upload.py check  uploads.csv   validate every 'ready' row, no network
  python yt_upload.py upload uploads.csv   upload every 'ready' row  [--only ep04]
  python yt_upload.py update uploads.csv   the .mp4 was uploaded by hand in YouTube Studio: find it
                                           (YouTube titles it after the file name) and set everything else

Secrets live in %USERPROFILE%\\.yt_uploader\\ (client_secret.json from Google Cloud,
token.json written after the first login), never in the project folder.

CSV columns (paths are relative to the CSV file)
  id               short key, e.g. ep04 (used by --only and by @id links)
  status           ready = upload it; published / skip / anything else = ignore
  video            video file
  title            max 100 characters
  description_file plain-text description (chapters included); no < or >
  fill             placeholder replacements, "KEY=value; KEY2=value". A value of
                   @ep03 becomes https://youtu.be/<video id of row ep03>
  thumbnail        jpg/png under 2 MB (needs a phone-verified channel)
  captions         .srt file (optional)
  caption_lang     e.g. en
  playlist         playlist title; created if missing
  playlist_privacy privacy of a NEW playlist: public / unlisted / private
  privacy          public / unlisted / private
  publish_at       optional, ISO time e.g. 2026-11-02T15:00:00+09:00; needs privacy=private,
                   YouTube makes the video public at that time
  tags             comma separated, 500 characters total at most
  category         28 = Science & Technology
  language         e.g. en (title/description and audio language)
  made_for_kids    yes / no
  synthetic        yes / no  (the "altered or synthetic content" label)
  notify           yes / no  (notify subscribers)
  video_id         leave empty; for rows already on YouTube paste the id, so @id links work
"""
import argparse
import csv
import datetime as dt
import json
import random
import sys
import time
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]  # upload, playlists, thumbnails, captions
SECRET_DIR = Path.home() / ".yt_uploader"
CLIENT_SECRET = SECRET_DIR / "client_secret.json"
TOKEN = SECRET_DIR / "token.json"
CHUNK = 32 * 1024 * 1024
RETRY_STATUS = {500, 502, 503, 504}
MAX_RETRIES = 10


# ---------------------------------------------------------------- auth

def service():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit("Missing libraries. Run:\n  python -m pip install -r requirements.txt")
    if not CLIENT_SECRET.exists():
        sys.exit(f"Put the OAuth 'Desktop app' client file here first:\n  {CLIENT_SECRET}")
    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
            creds = flow.run_local_server(port=0, prompt="consent")
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def my_channel(yt):
    items = yt.channels().list(part="snippet,contentDetails", mine=True).execute().get("items", [])
    if not items:
        sys.exit("This Google account has no YouTube channel.")
    return items[0]


# ---------------------------------------------------------------- manifest

def yes(v):
    return str(v).strip().lower() in {"yes", "y", "true", "1"}


def load_rows(csv_path):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_state(csv_path):
    p = Path(str(csv_path) + ".state.json")
    return p, (json.loads(p.read_text(encoding="utf-8")) if p.exists() else {})


def save_state(p, state):
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")


def video_id_of(key, rows, state):
    if state.get(key, {}).get("video_id"):
        return state[key]["video_id"]
    for r in rows:
        if r["id"] == key and r.get("video_id", "").strip():
            return r["video_id"].strip()
    return None


def build_description(row, base, rows, state, errors):
    path = base / row["description_file"]
    if not path.exists():
        errors.append(f"description file not found: {path}")
        return ""
    text = path.read_text(encoding="utf-8")
    for pair in filter(None, (s.strip() for s in row.get("fill", "").split(";"))):
        key, _, value = pair.partition("=")
        key, value = key.strip(), value.strip()
        if value.startswith("@"):
            vid = video_id_of(value[1:], rows, state)
            if not vid:
                errors.append(f"{key}: row '{value[1:]}' has no video_id yet (paste it into the CSV; "
                              f"'python yt_upload.py list' shows your ids)")
                continue
            value = f"https://youtu.be/{vid}"
        if not value:
            errors.append(f"{key}: no value given in the 'fill' column")
            continue
        text = text.replace(key, value)
    if "PASTE_" in text:
        errors.append("description still contains a PASTE_ placeholder")
    if "<" in text or ">" in text:
        errors.append("description contains < or > (YouTube rejects it)")
    if len(text.encode("utf-8")) > 5000:
        errors.append(f"description is {len(text.encode('utf-8'))} bytes (limit 5000)")
    return text


def validate(row, base, rows, state):
    errors = []
    video = base / row["video"]
    if not video.exists():
        errors.append(f"video not found: {video}")
    title = row["title"].strip()
    if not title or len(title) > 100 or "<" in title or ">" in title:
        errors.append(f"title must be 1-100 characters without < >: {title!r}")
    desc = build_description(row, base, rows, state, errors)
    if row.get("thumbnail"):
        th = base / row["thumbnail"]
        if not th.exists():
            errors.append(f"thumbnail not found: {th}")
        elif th.stat().st_size > 2 * 1024 * 1024:
            errors.append(f"thumbnail is over 2 MB: {th}")
    if row.get("captions") and not (base / row["captions"]).exists():
        errors.append(f"captions not found: {base / row['captions']}")
    tags = [t.strip() for t in row.get("tags", "").split(",") if t.strip()]
    if sum(len(t) + (2 if " " in t else 0) for t in tags) + max(len(tags) - 1, 0) > 500:
        errors.append("tags exceed 500 characters")
    privacy = row.get("privacy", "private").strip().lower()
    if privacy not in {"public", "unlisted", "private"}:
        errors.append(f"privacy must be public/unlisted/private, not {privacy!r}")
    publish_at = row.get("publish_at", "").strip()
    if publish_at:
        try:
            when = dt.datetime.fromisoformat(publish_at.replace("Z", "+00:00"))
            if when.tzinfo is None:
                errors.append("publish_at needs a time zone, e.g. +09:00")
            elif when <= dt.datetime.now(dt.timezone.utc):
                errors.append("publish_at is in the past")
            else:
                publish_at = when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            errors.append(f"publish_at is not an ISO time: {publish_at!r}")
        if privacy != "private":
            errors.append("publish_at needs privacy=private (YouTube makes it public at that time)")
    if not row.get("playlist", "").strip():
        errors.append("no playlist given")
    return errors, desc, tags, privacy, publish_at


# ---------------------------------------------------------------- upload steps

def resumable(request, label):
    """Run a resumable media request with exponential back-off (Google's sample pattern)."""
    from googleapiclient.errors import HttpError
    response, retry = None, 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"  {label}: {int(status.progress() * 100)} %", end="\r", flush=True)
        except HttpError as e:
            if e.resp.status not in RETRY_STATUS:
                raise
            retry = _backoff(retry, f"HTTP {e.resp.status}")
        except (ConnectionError, TimeoutError, OSError) as e:
            retry = _backoff(retry, repr(e))
    print(f"  {label}: done      ")
    return response


def _backoff(retry, why):
    retry += 1
    if retry > MAX_RETRIES:
        sys.exit(f"Giving up after {MAX_RETRIES} retries ({why}). Re-run the same command to resume.")
    wait = random.random() * 2 ** retry
    print(f"\n  retry {retry} in {wait:.0f} s ({why})")
    time.sleep(wait)
    return retry


def find_or_create_playlist(yt, title, privacy, cache):
    if title in cache:
        return cache[title]
    if not cache.get("_loaded"):
        req = yt.playlists().list(part="snippet", mine=True, maxResults=50)
        while req is not None:
            resp = req.execute()
            for p in resp.get("items", []):
                cache.setdefault(p["snippet"]["title"], p["id"])
            req = yt.playlists().list_next(req, resp)
        cache["_loaded"] = True
        if title in cache:
            return cache[title]
    body = {"snippet": {"title": title}, "status": {"privacyStatus": privacy or "public"}}
    pid = yt.playlists().insert(part="snippet,status", body=body).execute()["id"]
    print(f"  created playlist '{title}' ({privacy or 'public'})")
    cache[title] = pid
    return pid


def video_body(row, desc, tags, privacy, publish_at):
    lang = row.get("language", "en").strip() or "en"
    status = {
        "privacyStatus": privacy,
        "selfDeclaredMadeForKids": yes(row.get("made_for_kids", "no")),
        "containsSyntheticMedia": yes(row.get("synthetic", "no")),
        "license": "youtube",
        "embeddable": True,
    }
    if publish_at:
        status["publishAt"] = publish_at
    return {
        "snippet": {
            "title": row["title"].strip(),
            "description": desc,
            "tags": tags,
            "categoryId": row.get("category", "28").strip() or "28",
            "defaultLanguage": lang,
            "defaultAudioLanguage": lang,
        },
        "status": status,
    }


def upload_row(yt, row, base, rows, state, state_path, playlists):
    from googleapiclient.http import MediaFileUpload
    key = row["id"]
    errors, desc, tags, privacy, publish_at = validate(row, base, rows, state)
    if errors:
        print(f"[{key}] NOT uploaded:\n  - " + "\n  - ".join(errors))
        return False
    st = state.setdefault(key, {})
    lang = row.get("language", "en").strip() or "en"

    if not st.get("video_id"):
        body = video_body(row, desc, tags, privacy, publish_at)
        media = MediaFileUpload(str(base / row["video"]), chunksize=CHUNK, resumable=True,
                                mimetype="video/*")
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media,
                                 notifySubscribers=yes(row.get("notify", "yes")))
        resp = resumable(req, f"[{key}] video")
        st.update(video_id=resp["id"], uploaded_at=dt.datetime.now().isoformat(timespec="seconds"))
        save_state(state_path, state)
        print(f"  https://youtu.be/{resp['id']}  (privacy: {resp['status']['privacyStatus']})")
    vid = st["video_id"]

    if row.get("thumbnail") and not st.get("thumbnail_done"):
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(base / row["thumbnail"]))).execute()
            st["thumbnail_done"] = True
            save_state(state_path, state)
            print(f"  [{key}] thumbnail set")
        except Exception as e:  # most often: channel not phone-verified
            print(f"  [{key}] thumbnail FAILED ({e}); verify the channel at youtube.com/verify and re-run")

    if row.get("captions") and not st.get("captions_done"):
        body = {"snippet": {"videoId": vid, "language": row.get("caption_lang", lang) or lang,
                            "name": "", "isDraft": False}}
        media = MediaFileUpload(str(base / row["captions"]), mimetype="application/octet-stream",
                                resumable=True)
        resumable(yt.captions().insert(part="snippet", body=body, media_body=media), f"[{key}] captions")
        st["captions_done"] = True
        save_state(state_path, state)

    if not st.get("playlist_done"):
        pid = find_or_create_playlist(yt, row["playlist"].strip(), row.get("playlist_privacy", "").strip(),
                                      playlists)
        yt.playlistItems().insert(part="snippet", body={"snippet": {
            "playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
        st.update(playlist_done=True, playlist_id=pid)
        save_state(state_path, state)
        print(f"  [{key}] added to playlist '{row['playlist'].strip()}'")
    return True


# ---------------------------------------------------------------- commands

def cmd_auth(_):
    ch = my_channel(service())
    print(f"Logged in. Channel: {ch['snippet']['title']}  (id {ch['id']})")


def cmd_list(_):
    yt = service()
    ch = my_channel(yt)
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    print(f"Channel: {ch['snippet']['title']}\n\nUploads (video id  title):")
    req = yt.playlistItems().list(part="snippet", playlistId=uploads, maxResults=50)
    while req is not None:
        resp = req.execute()
        for it in resp.get("items", []):
            print(f"  {it['snippet']['resourceId']['videoId']}  {it['snippet']['title']}")
        req = yt.playlistItems().list_next(req, resp)
    print("\nPlaylists (id  title):")
    req = yt.playlists().list(part="snippet", mine=True, maxResults=50)
    while req is not None:
        resp = req.execute()
        for p in resp.get("items", []):
            print(f"  {p['id']}  {p['snippet']['title']}")
        req = yt.playlists().list_next(req, resp)


def selected(args, rows, state):
    out = []
    for r in rows:
        if args.only and r["id"] not in args.only:
            continue
        if r.get("status", "").strip().lower() != "ready":
            continue
        out.append(r)
    return out


def cmd_check(args):
    csv_path = Path(args.csv).resolve()
    rows = load_rows(csv_path)
    _, state = load_state(csv_path)
    todo = selected(args, rows, state)
    if not todo:
        print("No rows with status=ready.")
    bad = 0
    for r in todo:
        errors, desc, tags, privacy, publish_at = validate(r, csv_path.parent, rows, state)
        done = state.get(r["id"], {})
        tag = f"already uploaded as {done['video_id']}, will resume" if done.get("video_id") else "new"
        if errors:
            bad += 1
            print(f"[{r['id']}] PROBLEMS ({tag}):\n  - " + "\n  - ".join(errors))
        else:
            size = (csv_path.parent / r["video"]).stat().st_size / 1e6
            when = f", goes public {publish_at}" if publish_at else ""
            print(f"[{r['id']}] OK ({tag}): '{r['title']}', {size:.0f} MB, {privacy}{when}, "
                  f"playlist '{r['playlist']}', {len(tags)} tags, description {len(desc)} chars")
    skipped = [r["id"] for r in rows if r.get("status", "").strip().lower() != "ready"]
    if skipped:
        print(f"Skipped (status not 'ready'): {', '.join(skipped)}")
    return bad


def cmd_upload(args):
    if cmd_check(args):
        sys.exit("Fix the problems above first (nothing was uploaded).")
    csv_path = Path(args.csv).resolve()
    rows = load_rows(csv_path)
    state_path, state = load_state(csv_path)
    yt = service()
    print(f"Channel: {my_channel(yt)['snippet']['title']}")
    playlists = {}
    ok = 0
    for r in selected(args, rows, state):
        print(f"\n[{r['id']}] {r['title']}")
        ok += upload_row(yt, r, csv_path.parent, rows, state, state_path, playlists)
    print(f"\n{ok} row(s) finished. Progress file: {state_path}")
    print("Videos from an API project that has not passed Google's audit are locked to private.")


def find_manual_upload(yt, row, base):
    """Find a video uploaded by hand in YouTube Studio: YouTube titles it after the file name."""
    stem = Path(row["video"]).stem
    uploads = my_channel(yt)["contentDetails"]["relatedPlaylists"]["uploads"]
    resp = yt.playlistItems().list(part="snippet", playlistId=uploads, maxResults=50).execute()
    hits = [it["snippet"]["resourceId"]["videoId"] for it in resp.get("items", [])
            if it["snippet"]["title"].strip() in {stem, Path(row["video"]).name}]
    return hits


def cmd_update(args):
    """Fill in a video that was uploaded by hand in YouTube Studio (no API upload, so no audit lock)."""
    if cmd_check(args):
        sys.exit("Fix the problems above first (nothing was changed).")
    csv_path = Path(args.csv).resolve()
    rows = load_rows(csv_path)
    state_path, state = load_state(csv_path)
    yt = service()
    print(f"Channel: {my_channel(yt)['snippet']['title']}")
    playlists = {}
    for r in selected(args, rows, state):
        key, base = r["id"], csv_path.parent
        st = state.setdefault(key, {})
        print(f"\n[{key}] {r['title']}")
        vid = st.get("video_id") or r.get("video_id", "").strip()
        if not vid:
            hits = find_manual_upload(yt, r, base)
            if len(hits) != 1:
                print(f"  found {len(hits)} uploads titled '{Path(r['video']).stem}' in Studio; "
                      f"paste the right video id into the CSV's video_id column and re-run")
                continue
            vid = hits[0]
        if not st.get("metadata_done"):
            errors, desc, tags, privacy, publish_at = validate(r, base, rows, state)
            body = video_body(r, desc, tags, privacy, publish_at)
            body["id"] = vid
            resp = yt.videos().update(part="snippet,status", body=body).execute()
            st.update(video_id=vid, metadata_done=True, manual_upload=True,
                      uploaded_at=dt.datetime.now().isoformat(timespec="seconds"))
            save_state(state_path, state)
            print(f"  https://youtu.be/{vid}  details set (privacy: {resp['status']['privacyStatus']})")
        upload_row(yt, r, base, rows, state, state_path, playlists)  # thumbnail, captions, playlist
        # Tags set while Studio is still processing a hand upload can be dropped: check and re-send once.
        tags = [t.strip() for t in r.get("tags", "").split(",") if t.strip()]
        snip = yt.videos().list(part="snippet", id=vid).execute()["items"][0]["snippet"]
        if tags and not snip.get("tags"):
            snip["tags"] = tags
            yt.videos().update(part="snippet", body={"id": vid, "snippet": {
                k: snip[k] for k in ("title", "description", "categoryId", "tags",
                                     "defaultLanguage", "defaultAudioLanguage") if k in snip}}).execute()
            print(f"  [{key}] tags were missing after processing; sent again")
    print(f"\nProgress file: {state_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auth").set_defaults(fn=cmd_auth)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    for name, fn in (("check", cmd_check), ("upload", cmd_upload), ("update", cmd_update)):
        p = sub.add_parser(name)
        p.add_argument("csv")
        p.add_argument("--only", nargs="+", help="row ids, e.g. --only ep04")
        p.set_defaults(fn=fn)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
