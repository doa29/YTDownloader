import streamlit as st
import yt_dlp
import os, shutil, platform, stat, tarfile, zipfile, tempfile
from io import BytesIO
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from pathlib import Path

st.set_page_config(page_title="YouTube Downloader", layout="centered")
st.title("📥 YouTube Video & Playlist Downloader")

def is_valid_youtube_url(url: str) -> bool:
    try:
        u = urlparse(url)
        h = (u.netloc or "").lower()
        return ("youtube" in h) or ("youtu.be" in h)
    except:
        return False

progress_placeholder = st.empty()
status_placeholder = st.empty()

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
        except: continue
    return None

def build_ydl_opts(cookiefile_path: str|None, proxy_url: str|None):
    try: loc = ensure_ffmpeg()
    except: loc = None
    has_ffmpeg = bool(loc or shutil.which("ffmpeg"))

    # use android client first to dodge some 403s
    extractor_args = {"youtube": {"player_client": ["android", "web"]}}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    if has_ffmpeg:
        fmt = "bv*+ba/b"; merge = "mp4"
    else:
        fmt = "best[acodec!=none][vcodec!=none]/best[ext=mp4][acodec!=none][vcodec!=none]"; merge = None

    opts = {
        "format": fmt,
        "outtmpl": "%(title)s [%(id)s].%(ext)s",
        "noplaylist": False,
        "retries": 10,
        "fragment_retries": 10,
        "continuedl": True,
        "concurrent_fragment_downloads": 4,
        "socket_timeout": 30,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": "only_download",
        "progress_hooks": [make_progress_hook()],
        "http_headers": headers,
        "extractor_args": extractor_args,
        "geo_bypass": True,
        "geo_bypass_country": "US",
    }
    if merge: opts["merge_output_format"] = merge
    if loc: opts["ffmpeg_location"] = loc
    if cookiefile_path: opts["cookiefile"] = cookiefile_path
    if proxy_url: opts["proxy"] = proxy_url.strip()
    return opts

def collect_files(ydl, obj):
    out = []
    if not obj: return out
    if "entries" in obj and obj["entries"]:
        for e in obj["entries"]:
            if e: out += collect_files(ydl, e)
    else:
        out.append(ydl.prepare_filename(obj))
    return out

def download_any(url: str, cookiefile_path: str|None, proxy_url: str|None):
    try:
        ydl_opts = build_ydl_opts(cookiefile_path, proxy_url)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            files = collect_files(ydl, info)

        if not files: raise RuntimeError("No files created.")
        status_placeholder.success("✅ Done!")

        if len(files) == 1:
            p = files[0]
            with open(p, "rb") as f:
                st.download_button("⬇️ Download Video", f, file_name=os.path.basename(p), mime="video/mp4")
        else:
            buf = BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for p in files:
                    if p and os.path.exists(p): z.write(p, os.path.basename(p))
            buf.seek(0)
            st.download_button(f"⬇️ Download {len(files)} videos as ZIP", buf, file_name="youtube_videos.zip", mime="application/zip")
    except yt_dlp.utils.DownloadError as e:
        status_placeholder.error("❌ Download error.")
        st.caption(str(e))  # actual reason (helps with 403)
    except Exception as e:
        status_placeholder.error(f"❌ Error: {e}")

# inputs
url = st.text_input("Enter YouTube URL")
cookie_file = st.file_uploader("Optional cookies.txt (Netscape format)", type=["txt"])
proxy = st.text_input("Optional proxy (e.g. http://user:pass@host:port)")

# handle cookies file
cookie_path = None
if cookie_file is not None:
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        tmp.write(cookie_file.read())
        tmp.flush(); tmp.close()
        cookie_path = tmp.name
    except:
        cookie_path = None

# button
if st.button("Download"):
    progress_placeholder.empty()
    status_placeholder.empty()
    if not url.strip():
        st.warning("⚠️ Please enter a URL.")
    elif not is_valid_youtube_url(url.strip()):
        st.warning("⚠️ Not a valid YouTube link.")
    else:
        download_any(url.strip(), cookie_path, proxy.strip() or None)
