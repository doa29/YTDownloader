import streamlit as st
import yt_dlp
from pathlib import Path
import platform


def get_downloads_folder():

    return Path.home() / 'Downloads'


def on_progress(d):
    if d['status'] == 'downloading':
        percentage = d.get('_percent_str', '0%')
        st.session_state['progress'] = percentage


def download_video(url):
    try:
        downloads_dir = get_downloads_folder()
        downloads_dir.mkdir(parents=True, exist_ok=True)
        st.info(f"📁 Downloading to: {downloads_dir}")

        ydl_opts = {
      
            'format': 'best[ext=mp4]/best',
            'progress_hooks': [on_progress],
            'outtmpl': str(downloads_dir / '%(title)s.%(ext)s'),
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        st.success("✅ Download completed! Check your Downloads folder.")
    except Exception as e:
        st.error(f"❌ An error occurred: {e}")



st.set_page_config(page_title="YouTube Downloader", layout="centered")
st.title("📥 YouTube Video Downloader")

url = st.text_input("Enter YouTube URL")

if st.button("Download"):
    if url.strip():
        if 'progress' not in st.session_state:
            st.session_state['progress'] = "0%"
        download_video(url)
        st.write(f"📊 Download Progress: {st.session_state.get('progress', '0%')}")
    else:
        st.warning("⚠️ Please enter a valid YouTube URL.")
