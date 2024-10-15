# app.py

import streamlit as st
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from github import Github
import pandas as pd
import io
from datetime import datetime
import os

# GitHub setup
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    try:
        from config import GITHUB_TOKEN
    except ImportError:
        st.error("GitHub token not found. Please set the GITHUB_TOKEN environment variable or create a config.py file.")
        st.stop()

REPO_NAME = "your_username/your_private_repo"
CSV_PATH = "qr_data.csv"

g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

# Function to scan QR code
def scan_qr(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    qr_codes = decode(gray)
    
    if qr_codes:
        qr_data = qr_codes[0].data.decode('utf-8')
        return qr_data
    return None

# Function to update GitHub database
def update_database(data):
    try:
        # Fetch existing file content
        file = repo.get_contents(CSV_PATH)
        content = file.decoded_content.decode()
        df = pd.read_csv(io.StringIO(content))
    except:
        # If file doesn't exist, create a new DataFrame
        df = pd.DataFrame(columns=['Name', 'ID Type', 'ID Number', 'Pass Type', 'Timestamp'])
    
    # Parse QR data
    name, id_type, id_number, pass_type = data.split(',')
    
    # Add new row
    new_row = {
        'Name': name,
        'ID Type': id_type,
        'ID Number': id_number,
        'Pass Type': pass_type,
        'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    df = df.append(new_row, ignore_index=True)
    
    # Save updated DataFrame
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    repo.update_file(CSV_PATH, f"Update QR data - {datetime.now()}", csv_buffer.getvalue(), file.sha if 'file' in locals() else None)

# Function to display results
def display_results():
    try:
        file = repo.get_contents(CSV_PATH)
        content = file.decoded_content.decode()
        df = pd.read_csv(io.StringIO(content))
        
        pass_types = ["28 Oct 24", "Interactive Session - 29 Oct 24", "Plenary Session - 29 Oct 24"]
        
        for pass_type in pass_types:
            st.subheader(f"Pass Type: {pass_type}")
            filtered_df = df[df['Pass Type'] == pass_type].reset_index(drop=True)
            filtered_df.index += 1  # Start index from 1
            st.dataframe(filtered_df)
            st.write(f"Total entries: {len(filtered_df)}")
            st.write("---")
    except:
        st.error("No data available or error fetching data.")

# Streamlit app
def main():
    st.title("QR Code Scanner")
    
    if not GITHUB_TOKEN:
        st.error("GitHub token not configured. Please set up the token securely.")
        return

    uploaded_file = st.file_uploader("Choose an image file", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        image = cv2.imdecode(np.frombuffer(uploaded_file.read(), np.uint8), 1)
        st.image(image, caption="Uploaded Image", use_column_width=True)
        
        if st.button("Scan QR Code"):
            qr_data = scan_qr(image)
            
            if qr_data:
                st.success(f"QR Code scanned successfully: {qr_data}")
                try:
                    update_database(qr_data)
                    st.success("Database updated successfully!")
                except Exception as e:
                    st.error(f"Failed to update database: {str(e)}")
            else:
                st.error("No QR code found in the image.")
    
    if st.button("Display Results"):
        display_results()

if __name__ == "__main__":
    main()
