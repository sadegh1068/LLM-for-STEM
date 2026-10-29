# Privacy Policy: LLM for STEM uploader

Last updated: 29 October 2026

The LLM for STEM uploader ("the tool") is a command-line program that the owner of the YouTube channel
[LLM for STEM](https://www.youtube.com/channel/UClfsjsRwp2Vuh3c5TKZOYTA) runs on their own computer to
upload their own videos to their own channel.

## YouTube API Services

The tool uses **YouTube API Services**. By using the tool you agree to be bound by the
[YouTube Terms of Service](https://www.youtube.com/t/terms). Data obtained through YouTube API Services is
also subject to the **[Google Privacy Policy](https://policies.google.com/privacy)**
(<http://www.google.com/policies/privacy>).

## What information the tool accesses

When you sign in with Google, the tool receives an OAuth access token for the scope
`https://www.googleapis.com/auth/youtube.force-ssl`. With it, the tool:

- reads your channel's name and ID, the list of your uploaded videos (ID and title) and your playlists (ID and title),
- uploads video files, thumbnails and subtitle files that you choose from your own computer,
- creates playlists and adds your videos to them,
- deletes a video or playlist only when you run a command that names it.

It does not read comments, analytics, subscribers, payment data, contacts or any other account data,
and it does not access any channel other than the one you signed in with.

## What is stored, and where

Everything stays on your own computer:

- the OAuth client file and the access/refresh token, in the folder `.yt_uploader` in your user profile,
- a progress file next to your CSV list, holding the YouTube video ID and playlist ID of each video uploaded and which steps finished.

No data is sent to the author of the tool or to any server other than Google's YouTube API.
There is no analytics, tracking, advertising or cookie use.

## Sharing

The tool shares no information with anyone. Data goes only between your computer and Google's YouTube API.

## Retention and deletion

- The token remains on your computer until you delete it. Deleting the `.yt_uploader` folder removes it.
- The progress file remains until you delete it.
- You can revoke the tool's access at any time on the Google security settings page:
  <https://security.google.com/settings/security/permissions>. After revoking, the stored token no longer works.
- Data that the tool has obtained from YouTube API Services is not kept for longer than 30 days without being refreshed;
  the progress file holds only IDs of your own videos and playlists, which you can delete at any time.

## Children

The tool is a personal production tool for an adult channel owner and is not directed at children.

## Changes and contact

Changes to this policy are published in this file, with its history in this repository.
Questions: open an issue at <https://github.com/sadegh1068/LLM-for-STEM/issues>.
