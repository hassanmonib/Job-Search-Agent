"""Run Streamlit app from project root. Use: python run_app.py"""
import os
import subprocess
import sys

root = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.join(root, "job_signal_ai")
os.chdir(app_dir)
subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"], check=True)
