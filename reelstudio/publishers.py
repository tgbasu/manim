"""Publish finished reels: a local outbox, YouTube Shorts, or Instagram Reels.

Credentials come from environment variables, never from committed files.
Uploads use the official platform APIs over HTTPS with no extra dependencies.

  local      copy the video, cover, captions, and metadata into an outbox
  youtube    YouTube Data API v3 resumable upload (OAuth refresh token)
  instagram  Instagram Graph API resumable Reels upload, then publish
"""

import json
import os
from pathlib import Path
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request


class PublishError(RuntimeError):
    pass


def http(method, url, headers=None, data=None, timeout=300):
    """Return (status, headers, body). Bodies over 1 MB stream from bytes or file objects."""
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        raise PublishError(f"{method} {url.split('?')[0]} failed with {error.code}: "
                           f"{error.read().decode(errors='replace')[:500]}") from error


def require_env(*names):
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        raise PublishError("Set these environment variables to publish: " + ", ".join(missing))
    return [os.environ[name] for name in names]


def description(metadata):
    parts = [metadata["post_caption"], " ".join(metadata.get("hashtags", []))]
    if metadata.get("sources"):
        parts.append("Sources: " + "; ".join(metadata["sources"]))
    return "\n\n".join(part for part in parts if part)


class LocalPublisher:
    name = "local"

    def __init__(self, outbox):
        self.outbox = Path(outbox)

    def publish(self, video, metadata, cover=None, captions=None):
        folder = self.outbox / metadata["slug"]
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(video, folder / "video.mp4")
        for source, name in ((cover, "cover.png"), (captions, "captions.srt")):
            if source and Path(source).is_file():
                shutil.copy2(source, folder / name)
        (folder / "post.txt").write_text(f"{metadata['title']}\n\n{description(metadata)}\n", encoding="utf-8")
        return {"platform": self.name, "location": str(folder)}


class YouTubePublisher:
    """Uploads a Short; videos under three minutes in 9:16 are classified as Shorts."""

    name = "youtube"
    token_url = "https://oauth2.googleapis.com/token"
    upload_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"

    def __init__(self, privacy="private", category_id="27", made_for_kids=False,
                 synthetic_media=False, transport=http):
        if privacy not in ("private", "unlisted", "public"):
            raise PublishError("youtube.privacy must be private, unlisted, or public")
        self.privacy, self.category_id = privacy, str(category_id)
        self.made_for_kids, self.synthetic_media = made_for_kids, synthetic_media
        self.transport = transport

    def access_token(self):
        client_id, secret, refresh = require_env("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")
        body = urllib.parse.urlencode({"client_id": client_id, "client_secret": secret,
                                       "refresh_token": refresh, "grant_type": "refresh_token"}).encode()
        _, _, response = self.transport("POST", self.token_url,
                                        {"Content-Type": "application/x-www-form-urlencoded"}, body)
        return json.loads(response)["access_token"]

    def publish(self, video, metadata, cover=None, captions=None):
        token = self.access_token()
        title = metadata["title"] if "#shorts" in metadata["title"].lower() else f"{metadata['title']} #Shorts"
        resource = {
            "snippet": {
                "title": title[:100], "description": description(metadata)[:5000],
                "tags": [tag.lstrip("#") for tag in metadata.get("hashtags", [])],
                "categoryId": self.category_id,
            },
            "status": {
                "privacyStatus": self.privacy, "selfDeclaredMadeForKids": self.made_for_kids,
                "containsSyntheticMedia": self.synthetic_media,
            },
        }
        size = Path(video).stat().st_size
        _, headers, _ = self.transport("POST", self.upload_url, {
            "Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size),
        }, json.dumps(resource).encode())
        session = {key.lower(): value for key, value in headers.items()}.get("location")
        if not session:
            raise PublishError("YouTube did not return an upload session")
        with open(video, "rb") as stream:
            _, _, response = self.transport("PUT", session, {
                "Authorization": f"Bearer {token}", "Content-Type": "video/mp4", "Content-Length": str(size),
            }, stream, timeout=1800)
        video_id = json.loads(response)["id"]
        return {"platform": self.name, "id": video_id, "url": f"https://youtube.com/shorts/{video_id}",
                "privacy": self.privacy}


class InstagramPublisher:
    """Reels via the Instagram Graph API's resumable upload, so no public video URL is needed."""

    name = "instagram"

    def __init__(self, share_to_feed=True, api_version="v23.0", graph_host="https://graph.facebook.com",
                 poll_seconds=10, timeout_seconds=900, transport=http, sleep=time.sleep):
        self.share_to_feed, self.api_version = share_to_feed, api_version
        self.graph = f"{graph_host.rstrip('/')}/{api_version}"
        self.poll_seconds, self.timeout_seconds = poll_seconds, timeout_seconds
        self.transport, self.sleep = transport, sleep

    def call(self, method, path, token, params=None):
        query = urllib.parse.urlencode({**(params or {}), "access_token": token})
        url = f"{self.graph}/{path}"
        if method == "GET":
            _, _, body = self.transport("GET", f"{url}?{query}")
        else:
            _, _, body = self.transport("POST", url, {"Content-Type": "application/x-www-form-urlencoded"},
                                        query.encode())
        return json.loads(body)

    def publish(self, video, metadata, cover=None, captions=None):
        user_id, token = require_env("INSTAGRAM_USER_ID", "INSTAGRAM_ACCESS_TOKEN")
        caption = f"{metadata['post_caption']}\n\n{' '.join(metadata.get('hashtags', []))}"[:2200]
        container = self.call("POST", f"{user_id}/media", token, {
            "media_type": "REELS", "upload_type": "resumable", "caption": caption,
            "share_to_feed": "true" if self.share_to_feed else "false",
        })
        container_id = container["id"]
        size = Path(video).stat().st_size
        with open(video, "rb") as stream:
            self.transport("POST", f"https://rupload.facebook.com/ig-api-upload/{self.api_version}/{container_id}", {
                "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size),
                "Content-Length": str(size),
            }, stream, timeout=1800)
        waited = 0
        while True:
            status = self.call("GET", container_id, token, {"fields": "status_code,status"})
            code = status.get("status_code")
            if code == "FINISHED":
                break
            if code in ("ERROR", "EXPIRED"):
                raise PublishError(f"Instagram processing failed: {status.get('status', code)}")
            if waited >= self.timeout_seconds:
                raise PublishError("Instagram processing timed out; the container may still finish later")
            self.sleep(self.poll_seconds)
            waited += self.poll_seconds
        media = self.call("POST", f"{user_id}/media_publish", token, {"creation_id": container_id})
        return {"platform": self.name, "id": media["id"]}


def make_publishers(names, settings, outbox):
    publishers = []
    for name in names:
        options = dict(settings.get(name) or {})
        if name == "local":
            publishers.append(LocalPublisher(options.get("outbox", outbox)))
        elif name == "youtube":
            publishers.append(YouTubePublisher(**options))
        elif name == "instagram":
            publishers.append(InstagramPublisher(**options))
        else:
            raise PublishError(f"Unknown publisher {name!r}; choose local, youtube, or instagram")
    return publishers
