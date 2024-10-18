import streamlit as st
import cv2
import numpy as np
from github import Github
import pandas as pd
import io
from datetime import datetime
import re

GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", None)
if not GITHUB_TOKEN:
    try:
        from config import GITHUB_TOKEN
    except ImportError:
        st.error("GitHub token not found. Please set the GITHUB_TOKEN environment variable or create a config.py file.")
        st.stop()

REPO_NAME = "SWAVLAMBAN-24/scanner-24"
CSV_PATH = "qr_data.csv"

g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

def scan_qr(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    qr_detector = cv2.QRCodeDetector()
    data, bbox, _ = qr_detector.detectAndDecode(gray)
    return data if data else None

def update_database(data):
    try:
        match = re.match(r"Name:\s*(.*)\s+ID Type:\s*(.*)\s+ID Number:\s*(.*)\s+Pass Type:\s*(.*)", data)
        if not match:
            return False, "Invalid QR code format. Could not extract all required fields."

        name, id_type, id_number, pass_type = match.groups()
 
        try:
            file = repo.get_contents(CSV_PATH)
            content = file.decoded_content.decode()
            df = pd.read_csv(io.StringIO(content))
        except:
            df = pd.DataFrame(columns=['Name', 'ID Type', 'ID Number', 'Pass Type', 'Timestamp'])
        
        existing_entry = df[(df['Name'] == name) & 
                            (df['ID Number'] == id_number) & 
                            (df['Pass Type'] == pass_type)]
        
        if not existing_entry.empty:
            return False, "This QR code has already been scanned for this session."
        
        new_row = pd.DataFrame([{
            'Name': name,
            'ID Type': id_type,
            'ID Number': id_number,
            'Pass Type': pass_type,
            'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }])
        df = pd.concat([df, new_row], ignore_index=True)

        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)

        try:
            if 'file' in locals():
                repo.update_file(CSV_PATH, f"Update QR data - {datetime.now()}", csv_buffer.getvalue(), file.sha)
            else:
                repo.create_file(CSV_PATH, f"Create QR data - {datetime.now()}", csv_buffer.getvalue())
        except Exception as e:
            return False, f"Failed to update GitHub: {str(e)}"
        
        return True, "Database updated successfully!"
    
    except Exception as e:
        return False, f"Failed to update database: {str(e)}"

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
    except Exception as e:
        st.error(f"No data available or error fetching data: {str(e)}")

def process_uploaded_file(file):
    bytes_data = file.getvalue()
    nparr = np.frombuffer(bytes_data, np.uint8)
    return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

def process_image(image):
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
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

def main():
    st.title("QR Code Scanner")

    if not GITHUB_TOKEN:
        st.error("GitHub token not configured. Please set up the token securely.")
        return

    st.write("Use your camera to scan a QR code")
    img_file_buffer = st.camera_input("Take a picture")
        
    if img_file_buffer is not None:
        image = process_uploaded_file(img_file_buffer)
        process_image(image)

    if st.button("Display Results"):
        display_results()

if __name__ == "__main__":
    main()
