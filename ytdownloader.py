import streamlit as st
import yt_dlp
import os
from pathlib import Path
import platform


def get_downloads_folder():
    home = Path.home()
    if platform.system() == 'Windows':
        return home / 'Downloads'
    elif platform.system() == 'Darwin':  # macOS
        return home / 'Downloads'
    else:  # Linux or anything else
        return home / 'Downloads'

def on_progress(d):
    if d['status'] == 'downloading':
        percentage = d.get('_percent_str', '0%')
        st.session_state['progress'] = percentage

def download_video(url):
    try:
        downloads_dir = get_downloads_folder()
        st.info(f"Downloading to: {downloads_dir}")

        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', 
            'progress_hooks': [on_progress],
            'outtmpl': os.path.join(str(downloads_dir), '%(title)s.%(ext)s'),
            'merge_output_format': 'mp4',  #  final output is .mp4
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        st.success("Download completed! Check your Downloads folder.")
    except Exception as e:
        st.error(f"An error occurred: {e}")


st.title("📥 YouTube Video Downloader")

url = st.text_input("Enter YouTube URL")

if st.button("Download"):
    if url:
        st.session_state['progress'] = "0%"
        download_video(url)
        st.write(f"Progress: {st.session_state.get('progress', '0%')}")
    else:
        st.warning("Please enter a URL.")
