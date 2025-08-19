import streamlit as st
import yt_dlp
import os, shutil, platform, stat, tarfile, zipfile
from io import BytesIO
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from pathlib import Path

st.set_page_config(page_title="YouTube Downloader", layout="centered")
st.title("📥 YouTube Video & Playlist Downloader")

# quick link check
def is_valid_youtube_url(url: str) -> bool:
    try:
        u = urlparse(url)
        h = (u.netloc or "").lower()
        return ("youtube" in h) or ("youtu.be" in h)
    except:
        return False

progress_placeholder = st.empty()
status_placeholder = st.empty()

# progress bar
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

# small fetch helper
def _http_get(url, chunk=1024*1024):
    req = Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urlopen(req, timeout=90) as r:
        data = BytesIO()
        while True:
            b = r.read(chunk)
            if not b: break
            data.write(b)
        data.seek(0)
        return data

# ffmpeg auto-setup (downloads a portable build into ./bin)
def ensure_ffmpeg():
    if shutil.which("ffmpeg"): return None
    bin_dir = Path(__file__).parent / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    exe = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    ffmpeg_path = bin_dir / exe
    if ffmpeg_path.exists(): return str(bin_dir)

    sysname = platform.system().lower()
    arch = platform.machine().lower()
    if "windows" in sysname:
        urls = ["https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"]
    elif "darwin" in sysname or "mac" in sysname:
        urls = ["https://evermeet.cx/ffmpeg/ffmpeg.zip"]
    else:
        urls = ["https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz"] if ("aarch64" in arch or "arm64" in arch) else ["https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"]

    for u in urls:
        try:
            buf = _http_get(u)
            name = u.split("/")[-1]
            p = bin_dir / name
            with open(p, "wb") as f: f.write(buf.read())
            if name.endswith(".zip"):
                with zipfile.ZipFile(p) as z:
                    cand = [m for m in z.namelist() if m.endswith(exe)]
                    if not cand: raise RuntimeError("ffmpeg not in zip")
                    target = cand[0]
                    z.extract(target, bin_dir)
                    (bin_dir / target).rename(ffmpeg_path)
            else:
                with tarfile.open(p) as t:
                    cand = [m for m in t.getmembers() if m.name.endswith(exe)]
                    if not cand: raise RuntimeError("ffmpeg not in tar")
                    m = cand[0]
                    t.extract(m, bin_dir)
                    (bin_dir / m.name).rename(ffmpeg_path)
            try: ffmpeg_path.chmod(ffmpeg_path.stat().st_mode | stat.S_IEXEC)
            except: pass
            try: p.unlink()
            except: pass
            return str(bin_dir)
        except:
            continue
    return None

# build yt-dlp options (no cookies/proxy)
def base_ydl_opts():
    try: loc = ensure_ffmpeg()
    except: loc = None
    has_ffmpeg = bool(loc or shutil.which("ffmpeg"))

    # try different clients to reduce 403
    extractor_args = {"youtube": {"player_client": ["android", "web_embedded", "ios", "web"]}}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.youtube.com/",
        "Origin": "https://www.youtube.com",
    }

    if has_ffmpeg:
        fmt = "bv*+ba/b"; merge = "mp4"
    else:
        fmt = "best[acodec!=none][vcodec!=none]/best[ext=mp4][acodec!=none][vcodec!=none]"; merge = None

    opts = {
        "format": fmt,
        "outtmpl": "%(title)s [%(id)s].%(ext)s",
        "noplaylist": False,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [make_progress_hook()],
        "http_headers": headers,
        "extractor_args": extractor_args,
        "geo_bypass": True,
        "geo_bypass_country": "US",
        "nocheckcertificate": True,
        "retries": 10,
        "fragment_retries": 10,
        "continuedl": True,
        "concurrent_fragment_downloads": 4,
        "socket_timeout": 30,
    }
    if merge: opts["merge_output_format"] = merge
    if loc: opts["ffmpeg_location"] = loc
    return opts

# collect output files
def collect_files(ydl, obj):
    out = []
    if not obj: return out
    if "entries" in obj and obj["entries"]:
        for e in obj["entries"]:
            if e: out += collect_files(ydl, e)
    else:
        out.append(ydl.prepare_filename(obj))
    return out

# run with a few fallback client profiles if needed
CLIENT_TRIES = [
    ["android", "web_embedded", "ios", "web"],
    ["ios", "android", "web_embedded", "web"],
    ["web", "android"],
]

def download_any(url: str):
    try:
        last_err = None
        files = []

        for clients in CLIENT_TRIES:
            opts = base_ydl_opts()
            opts["extractor_args"] = {"youtube": {"player_client": clients}}
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    files = collect_files(ydl, info)
                break
            except yt_dlp.utils.DownloadError as e:
                last_err = e
                continue

        files = [f for f in files if f and os.path.exists(f)]
        if not files:
            if last_err:
                raise last_err
            raise RuntimeError("No files were created.")

        status_placeholder.success("✅ Done!")

        if len(files) == 1:
            p = files[0]
            with open(p, "rb") as f:
                st.download_button("⬇️ Download Video", f,
                    file_name=os.path.basename(p), mime="video/mp4")
        else:
            buf = BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for p in files: z.write(p, os.path.basename(p))
            buf.seek(0)
            st.download_button(f"⬇️ Download {len(files)} videos as ZIP", buf,
                file_name="youtube_videos.zip", mime="application/zip")

    except yt_dlp.utils.DownloadError as e:
        status_placeholder.error("❌ Download error.")
        st.caption(str(e))  # shows 403 reason if it happens
    except Exception as e:
        status_placeholder.error(f"❌ Error: {e}")

# UI
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
