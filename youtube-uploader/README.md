# LLM for STEM uploader

[![YouTube channel: LLM for STEM](https://img.shields.io/badge/YouTube-LLM%20for%20STEM-FF0000?logo=youtube&logoColor=white)](https://www.youtube.com/channel/UClfsjsRwp2Vuh3c5TKZOYTA)

**[Privacy Policy](PRIVACY.md)** · **[Terms of Service](TERMS.md)**

A small command-line tool that uploads the finished episodes of the YouTube channel
[LLM for STEM](https://www.youtube.com/channel/UClfsjsRwp2Vuh3c5TKZOYTA) to that same channel.
It is run by the channel owner on their own computer. It has no website, no server and no other users.

This tool uses **YouTube API Services**. By using it you agree to the
[YouTube Terms of Service](https://www.youtube.com/t/terms), and your data is handled under the
[Google Privacy Policy](https://policies.google.com/privacy). See [PRIVACY.md](PRIVACY.md) and [TERMS.md](TERMS.md).

## What it does

For each row of a CSV list marked `ready`, it:

1. uploads the video file (`videos.insert`, resumable, with retries),
2. sets the title, description, tags, category, language, "made for kids" and "altered or synthetic content" flags, privacy, and an optional scheduled publish time,
3. sets the custom thumbnail (`thumbnails.set`),
4. uploads the subtitle file (`captions.insert`),
5. adds the video to the named playlist, creating the playlist if it does not exist (`playlists.insert`, `playlistItems.insert`).

Progress is saved after every step, so a re-run resumes where it stopped and never uploads a video twice.

## YouTube API methods used

`channels.list`, `videos.insert`, `videos.list`, `videos.delete`, `thumbnails.set`, `captions.insert`,
`captions.list`, `playlists.list`, `playlists.insert`, `playlists.delete`, `playlistItems.list`,
`playlistItems.insert`. OAuth scope: `https://www.googleapis.com/auth/youtube.force-ssl`.
Typical volume: one to four uploads per month, well under the default quota.

## Setup

1. In Google Cloud, enable **YouTube Data API v3** and create an OAuth client of type **Desktop app**.
2. Save the downloaded client file as `%USERPROFILE%\.yt_uploader\client_secret.json` (Windows) or `~/.yt_uploader/client_secret.json`.
3. `python -m pip install -r requirements.txt`
4. `python yt_upload.py auth` opens Google's sign-in page once; the access token is saved next to the client file.

## Use

```
python yt_upload.py list                    # your uploads (video id, title) and playlists
python yt_upload.py check  uploads.csv      # validate every 'ready' row, no network
python yt_upload.py upload uploads.csv      # upload every 'ready' row
python yt_upload.py upload uploads.csv --only ep05
```

The CSV columns are documented at the top of [yt_upload.py](yt_upload.py); a template is in
[uploads.example.csv](uploads.example.csv).

## Revoking access

Remove "LLM for STEM uploader" at <https://myaccount.google.com/permissions>
(Google Account → Security → Third-party apps & services), and delete the `.yt_uploader` folder.
