import streamlit as st
import yt_dlp
import os


def on_progress(d):
    if d['status'] == 'downloading':
        percentage = d.get('_percent_str', '0%')
        st.session_state['progress'] = percentage


def download_video(url):
    try:
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'quiet': True,
            'progress_hooks': [on_progress],
            'outtmpl': '%(title)s.%(ext)s',
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        st.success("✅ Download completed!")

        # Read the downloaded video and offer it as a downloadable file
        with open(filename, "rb") as f:
            st.download_button(
                label="⬇️ Click to Download Video",
                data=f,
                file_name=os.path.basename(filename),
                mime="video/mp4"
            )



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
