@echo off
REM Create venv if it doesn't exist
IF NOT EXIST venv (
    python -m venv venv
)

REM Activate the virtual environment
CALL venv\Scripts\activate

REM Upgrade pip and install requirements
python -m pip install --upgrade pip
pip install -r requirements.txt

REM Run the Streamlit app
streamlit run downloader.py %*
