import streamlit as st
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from github import Github
import pandas as pd
import io
from datetime import datetime
import os

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    try:
        from config import GITHUB_TOKEN
    except ImportError:
        st.error("GitHub token not found. Please set the GITHUB_TOKEN environment variable or create a config.py file.")
        st.stop()

REPO_NAME = "SWAVLAMBAN-24/swavlamban-24"
CSV_PATH = "qr_data.csv"

g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

def scan_qr(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    qr_codes = decode(gray)
    
    if qr_codes:
        qr_data = qr_codes[0].data.decode('utf-8')
        return qr_data
    return None

def update_database(data):
    try:
        file = repo.get_contents(CSV_PATH)
        content = file.decoded_content.decode()
        df = pd.read_csv(io.StringIO(content))
    except:
        df = pd.DataFrame(columns=['Name', 'ID Type', 'ID Number', 'Pass Type', 'Timestamp', 'Email', 'Phone'])
    
    name, id_type, id_number, pass_type, email, phone = data.split(',')
    
    existing_entry = df[(df['Name'] == name) & 
                        (df['Phone'] == phone) & 
                        (df['Email'] == email) & 
                        (df['Pass Type'] == pass_type)]
    
    if not existing_entry.empty:
        return False, "This QR code has already been scanned for this session."
    
    new_row = {
        'Name': name,
        'ID Type': id_type,
        'ID Number': id_number,
        'Pass Type': pass_type,
        'Email': email,
        'Phone': phone,
        'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    df = df.append(new_row, ignore_index=True)
    
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    repo.update_file(CSV_PATH, f"Update QR data - {datetime.now()}", csv_buffer.getvalue(), file.sha if 'file' in locals() else None)
    
    return True, "Database updated successfully!"

def display_results():
    try:
        file = repo.get_contents(CSV_PATH)
        content = file.decoded_content.decode()
        df = pd.read_csv(io.StringIO(content))
        
        pass_types = ["28 Oct 24", "Interactive Session - 29 Oct 24", "Plenary Session - 29 Oct 24"]
        
        for pass_type in pass_types:
            st.subheader(f"Pass Type: {pass_type}")
            filtered_df = df[df['Pass Type'] == pass_type].reset_index(drop=True)
            filtered_df.index += 1  
            st.dataframe(filtered_df)
            st.write(f"Total entries: {len(filtered_df)}")
            st.write("---")
    except:
        st.error("No data available or error fetching data.")

def main():
    st.title("QR Code Scanner")
    
    if not GITHUB_TOKEN:
        st.error("GitHub token not configured. Please set up the token securely.")
        return

    scan_method = st.radio("Choose scanning method:", ("Upload Image", "Use Camera"))

    if scan_method == "Upload Image":
        uploaded_file = st.file_uploader("Choose an image file", type=["jpg", "jpeg", "png"])
        
        if uploaded_file is not None:
            image = cv2.imdecode(np.frombuffer(uploaded_file.read(), np.uint8), 1)
            st.image(image, caption="Uploaded Image", use_column_width=True)
            
            if st.button("Scan QR Code"):
                qr_data = scan_qr(image)
                
                if qr_data:
                    st.success(f"QR Code scanned successfully: {qr_data}")
                    try:
                        success, message = update_database(qr_data)
                        if success:
                            st.success(message)
                        else:
                            st.warning(message)
                    except Exception as e:
                        st.error(f"Failed to update database: {str(e)}")
                else:
                    st.error("No QR code found in the image.")
    else:
        st.write("Scan QR code using your device camera:")
        scanned_code = qr_scanner()
        if scanned_code:
            st.success(f"QR Code scanned successfully: {scanned_code}")
            try:
                success, message = update_database(scanned_code)
                if success:
                    st.success(message)
                else:
                    st.warning(message)
            except Exception as e:
                st.error(f"Failed to update database: {str(e)}")

    if st.button("Display Results"):
        display_results()
