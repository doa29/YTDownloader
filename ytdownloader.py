import streamlit as st
import yt_dlp
import os, sys, shutil, platform, stat, tarfile, zipfile
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

# tiny http get
def _http_get(url, chunk=1024*1024):
    req = Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urlopen(req, timeout=60) as r:
        data = BytesIO()
        while True:
            b = r.read(chunk)
            if not b: break
            data.write(b)
        data.seek(0)
        return data

# download+unpack ffmpeg once to ./bin
def ensure_ffmpeg():
    # if system has ffmpeg, use it
    if shutil.which("ffmpeg"):
        return None  # yt-dlp will use PATH
    bin_dir = Path(__file__).parent / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    exe = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    ffmpeg_path = bin_dir / exe
    if ffmpeg_path.exists():
        return str(bin_dir)

    sysname = platform.system().lower()
    arch = platform.machine().lower()

    # simple targets (x86_64/arm64). more can be added later.
    urls = []
    if "windows" in sysname:
        # windows zip (essentials)
        urls = [
            "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
        ]
    elif "darwin" in sysname or "mac" in sysname:
        # macOS zip (static)
        urls = [
            "https://evermeet.cx/ffmpeg/ffmpeg.zip",
        ]
    else:
        # linux static tar.xz (amd64); arm fallback
        if "aarch64" in arch or "arm64" in arch:
            urls = [
                "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz",
            ]
        else:
            urls = [
                "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
            ]

    last_err = None
    for u in urls:
        try:
            buf = _http_get(u)
            name = u.split("/")[-1]
            p = bin_dir / name
            with open(p, "wb") as f:
                f.write(buf.read())
            # unpack
            if name.endswith(".zip"):
                with zipfile.ZipFile(p) as z:
                    # find ffmpeg binary inside
                    cand = [m for m in z.namelist() if m.endswith(exe)]
                    if not cand:
                        raise RuntimeError("ffmpeg not found in zip")
                    target = cand[0]
                    z.extract(target, bin_dir)
                    # move to bin root
                    src = bin_dir / target
                    src.rename(ffmpeg_path)
            elif name.endswith(".tar.xz") or name.endswith(".tar.bz2") or name.endswith(".tar.gz"):
                with tarfile.open(p) as t:
                    cand = [m for m in t.getmembers() if m.name.endswith(exe)]
                    if not cand:
                        raise RuntimeError("ffmpeg not found in tar")
                    m = cand[0]
                    t.extract(m, bin_dir)
                    (bin_dir / m.name).rename(ffmpeg_path)
            else:
                raise RuntimeError("unknown archive")

            # make executable (unix)
            try:
                ffmpeg_path.chmod(ffmpeg_path.stat().st_mode | stat.S_IEXEC)
            except: pass

            try: p.unlink()
            except: pass

            return str(bin_dir)
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"ffmpeg auto-setup failed: {last_err}")

def build_ydl_opts():
    try:
        loc = ensure_ffmpeg()
    except Exception as e:
        loc = None
        st.info("⚠️ Using progressive downloads (no ffmpeg).")

    has_ffmpeg = bool(loc or shutil.which("ffmpeg"))
    if has_ffmpeg:
        fmt = "bv*+ba/b"
        merge = "mp4"
    else:
        fmt = "best[acodec!=none][vcodec!=none]/best[ext=mp4][acodec!=none][vcodec!=none]"
        merge = None

    opts = {
        "format": fmt,
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
    if merge:
        opts["merge_output_format"] = merge
    if loc:
        opts["ffmpeg_location"] = loc
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

def download_any(url: str):
    files = []
    try:
        ydl_opts = build_ydl_opts()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            files = collect_files(ydl, info)

        if not files:
            raise RuntimeError("No files created.")
        status_placeholder.success("✅ Done!")

        if len(files) == 1:
            p = files[0]
            if os.path.exists(p):
                with open(p, "rb") as f:
                    st.download_button(
                        label="⬇️ Download Video",
                        data=f,
                        file_name=os.path.basename(p),
                        mime="video/mp4",
                    )
        else:
            buf = BytesIO()
            with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
                for pth in files:
                    if pth and os.path.exists(pth):
                        z.write(pth, arcname=os.path.basename(pth))
            buf.seek(0)
            st.download_button(
                label=f"⬇️ Download {len(files)} videos as ZIP",
                data=buf,
                file_name="youtube_videos.zip",
                mime="application/zip",
            )

    except yt_dlp.utils.DownloadError as e:
        status_placeholder.error("❌ Download error.")
        st.caption(str(e))
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
