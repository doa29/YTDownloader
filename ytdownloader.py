import streamlit as st
import os, sys, shutil, io, zipfile, re
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

# basic styles
st.set_page_config(page_title="YouTube Downloader", page_icon="⬇️", layout="centered")
st.title("YouTube Downloader")
url = st.text_input("Enter YouTube URL")
go = st.button("Download")
bar = st.progress(0, text="Idle")
msg = st.empty()

# helpers
YT_HOSTS = ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com")
def looks_like_youtube(u: str) -> bool:
    return any(h in u for h in YT_HOSTS)

def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None

def safe_name(name: str) -> str:
    name = os.path.basename(name)
    name = re.sub(r"[\\/:*?\\\"<>|]+", "_", name)
    name = re.sub(r"\\s+", " ", name).strip()
    return name or "video.mp4"

def make_zip(paths):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            if os.path.exists(p):
                z.write(p, arcname=safe_name(p))
    buf.seek(0)
    return buf

def collect_outputs_from_hook(d):
    if d.get("status") == "downloading":
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        done = d.get("downloaded_bytes") or 0
        pct = int(done * 100 / total) if total else 0
        bar.progress(min(max(pct, 0), 99), text=f"Downloading… {pct}%")
    elif d.get("status") == "finished":
        bar.progress(100, text="Processing…")
        fn = d.get("filename")
        if fn:
            finished_files.add(fn)

def run_download(u: str):
    clients_orders = [
        ["android","web_embedded","ios","web"],
        ["ios","web","android","web_embedded"],
        ["web","android","ios","web_embedded"],
    ]
    base_opts = {
        "outtmpl": "%(title)s [%(id)s].%(ext)s",
        "retries": 10,
        "fragment_retries": 10,
        "continuedl": True,
        "concurrent_fragment_downloads": 4,
        "socket_timeout": 30,
        "quiet": True,
        "no_warnings": True,
        "geo_bypass": True,
        "geo_bypass_country": "US",
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "*/*",
            "Referer": "https://www.youtube.com/",
        },
        "progress_hooks": [collect_outputs_from_hook],
    }
    if ffmpeg_available():
        base_opts.update({
            "format": "bv*+ba/b",
            "merge_output_format": "mp4",
        })
    else:
        base_opts.update({
            "format": "best[acodec!=none][vcodec!=none]/best[ext=mp4][acodec!=none][vcodec!=none]",
        })

    last_err = None
    for order in clients_orders:
        opts = dict(base_opts)
        opts["extractor_args"] = {"youtube": {"player_client": [order]}}
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(u, download=True)
            return info
        except DownloadError as e:
            last_err = e
            continue
    if last_err:
        raise last_err

# main
if go:
    if not url or not looks_like_youtube(url):
        st.warning("Please enter a valid YouTube or youtu.be URL.")
        st.stop()
    bar.progress(0, text="Starting…")
    msg.empty()
    try:
        global finished_files
        finished_files = set()
        info = run_download(url)
        # collect from info as a backup
        paths = set()
        if "entries" in info and isinstance(info["entries"], list):
            for e in info["entries"]:
                fn = e.get("_filename") or e.get("requested_downloads",[{}])[0].get("filepath")
                if fn:
                    paths.add(fn)
        else:
            fn = info.get("_filename") or info.get("requested_downloads",[{}])[0].get("filepath")
            if fn:
                paths.add(fn)
        paths |= finished_files
        paths = [p for p in paths if p and os.path.exists(p)]
        if not paths:
            raise RuntimeError("No files were created (maybe blocked/restricted).")
        st.success("Done!")
        if len(paths) == 1:
            p = paths[0]
            with open(p, "rb") as f:
                st.download_button("⬇️ Download Video", data=f.read(), file_name=safe_name(p), mime="video/mp4")
        else:
            zipbuf = make_zip(paths)
            st.download_button("⬇️ Download ZIP", data=zipbuf, file_name="playlist.zip", mime="application/zip")
    except DownloadError as e:
        st.error("❌ Download error.")
        st.caption(str(e))
    except Exception as e:
        st.error(f"❌ Error: {e}")
