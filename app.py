import streamlit as st
import cv2
import numpy as np
from github import Github
import pandas as pd
import io
from datetime import datetime
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
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

class VideoTransformer(VideoTransformerBase):
    def __init__(self):
        self.qr_detector = cv2.QRCodeDetector()

    def transform(self, frame):
        img = frame.to_ndarray(format="bgr24")
        
        # Detect QR code
        data, bbox, _ = self.qr_detector.detectAndDecode(img)
        
        # If QR code is detected, display it as info on the Streamlit app
        if data:
            st.session_state.qr_data = data  # Store the QR code data in session state
        
        return img

def update_database(data):
    try:
        match = re.match(r"Name:\s*(.*)\s+ID Type:\s*(.*)\s+ID Number:\s*(.*)\s+Pass Type:\s*(.*)", data)
        if not match:
            return False, "Invalid QR code format. Could not extract all required fields."

        name, id_type, id_number, pass_type = match.groups()
        #email = "unknown@example.com"  # Placeholder for email if not available
        #phone = "0000000000"  # Placeholder for phone if not available

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
            'Pass Type': pass_type, #'Email': email, 'Phone': phone,
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

def main():
    st.title("QR Code Scanner")

    if not GITHUB_TOKEN:
        st.error("GitHub token not configured. Please set up the token securely.")
        return

    scan_method = st.radio("Choose scanning method:", ("Upload Image", "Use Camera"))

    if scan_method == "Upload Image":
        uploaded_file = st.file_uploader("Choose an image file", type=["jpg", "jpeg", "png"])
        
        if uploaded_file is not None:
            st.image(image, caption="Uploaded Image", use_column_width=True)
            image = cv2.imdecode(np.frombuffer(uploaded_file.read(), np.uint8), 1)
                        
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
        st.write("Start scanning using your camera below:")
        webrtc_streamer(key="example", video_transformer_factory=VideoTransformer)

        if "qr_data" in st.session_state and st.session_state.qr_data:
            qr_data = st.session_state.qr_data
            st.success(f"QR Code scanned successfully: {qr_data}")
            if st.button("Update Database with QR Code"):
                try:
                    success, message = update_database(qr_data)
                    if success:
                        st.success(message)
                        del st.session_state.qr_data  # Clear QR code data after successful update
                    else:
                        st.warning(message)
                except Exception as e:
                    st.error(f"Failed to update database: {str(e)}")

    if st.button("Display Results"):
        display_results()

if __name__ == "__main__":
    main()
