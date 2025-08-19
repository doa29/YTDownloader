import streamlit as st
import yt_dlp
import os
import zipfile
from io import BytesIO
from urllib.parse import urlparse

st.set_page_config(page_title="YouTube Downloader", layout="centered")
st.title("📥 YouTube Video & Playlist Downloader")

# quick check if link is YouTube
def is_valid_youtube_url(url: str) -> bool:
    try:
        u = urlparse(url)
        return u.netloc and "youtube" in u.netloc or "youtu.be" in u.netloc
    except:
        return False

progress_placeholder = st.empty()
status_placeholder = st.empty()

# show download progress
def make_progress_hook():
    bar = progress_placeholder.progress(0, text="Preparing…")

    def _hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            pct = int(done * 100 / total) if total else 0
            bar.progress(min(max(pct, 0), 100))
        elif d.get("status") == "finished":
            bar.progress(100, text="Processing…")
    return _hook

# yt-dlp options
def build_ydl_opts():
    return {
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": "%(title)s [%(id)s].%(ext)s",
        "noplaylist": False,
        "retries": 10,
        "fragment_retries": 10,
        "continuedl": True,
        "concurrent_fragment_downloads": 4,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [make_progress_hook()],
    }

# main download
def download_any(url: str):
    files = []
    try:
        ydl_opts = build_ydl_opts()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            def collect(obj):
                out = []
                if "entries" in obj and obj["entries"]:
                    for e in obj["entries"]:
                        if e:
                            out += collect(e)
                else:
                    out.append(ydl.prepare_filename(obj))
                return out

            files = collect(info)

        if not files:
            raise RuntimeError("No files created.")

        status_placeholder.success("✅ Done!")

        if len(files) == 1:
            fname = files[0]
            with open(fname, "rb") as f:
                st.download_button(
                    label="⬇️ Download Video",
                    data=f,
                    file_name=os.path.basename(fname),
                    mime="video/mp4",
                )
        else:
            buf = BytesIO()
            with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
                for path in files:
                    if path and os.path.exists(path):
                        z.write(path, arcname=os.path.basename(path))
            buf.seek(0)
            st.download_button(
                label=f"⬇️ Download {len(files)} videos as ZIP",
                data=buf,
                file_name="youtube_videos.zip",
                mime="application/zip",
            )

    except Exception as e:
        status_placeholder.error(f"❌ Error: {e}")

url = st.text_input("Enter YouTube URL")

if st.button("Download"):
    progress_placeholder.empty()
    status_placeholder.empty()

    if not url.strip():
        st.warning("⚠️ Please enter a URL.")
    elif not is_valid_youtube_url(url.strip()):
        st.warning("⚠️ Not a valid YouTube link.")
    else:
        download_any(url.strip())
