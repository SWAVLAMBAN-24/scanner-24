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
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Initialize QR Code detector
    qr_detector = cv2.QRCodeDetector()
    
    # Detect and decode
    data, bbox, _ = qr_detector.detectAndDecode(gray)
    
    if data:
        return data
    return None

def update_database(data):
    try:
        match = re.match(r"Name:\s*(.*)\s+ID Type:\s*(.*)\s+ID Number:\s*(.*)\s+Pass Type:\s*(.*)", data)
        if not match:
            return False, "Invalid QR code format. Could not extract all required fields."

        name, id_type, id_number, pass_type = match.groups()
        email = "unknown@example.com"  # Placeholder for email if not available
        phone = "0000000000"  # Placeholder for phone if not available

        try:
            file = repo.get_contents(CSV_PATH)
            content = file.decoded_content.decode()
            df = pd.read_csv(io.StringIO(content))
        except:
            df = pd.DataFrame(columns=['Name', 'ID Type', 'ID Number', 'Pass Type', 'Timestamp', 'Email', 'Phone'])
        
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
            'Email': email,
            'Phone': phone,
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

def camera_scan():
    cap = cv2.VideoCapture(0)  # Use the default camera (0 is usually the default)

    if not cap.isOpened():
        st.error("Could not open the camera. Please check your camera settings.")
        return None

    qr_detector = cv2.QRCodeDetector()

    st.write("Press 'q' to quit scanning when done.")

    while True:
        ret, frame = cap.read()
        if not ret:
            st.error("Failed to capture an image from the camera.")
            break

        # Detect QR code in the current frame
        data, bbox, _ = qr_detector.detectAndDecode(frame)
        
        # Display the video feed
        cv2.imshow("Camera QR Code Scanner - Press 'q' to quit", frame)

        if data:
            cap.release()
            cv2.destroyAllWindows()
            return data

        # Press 'q' to exit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    return None

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
        if st.button("Start Camera Scan"):
            qr_data = camera_scan()
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
                st.warning("No QR code detected. Please try again.")

    if st.button("Display Results"):
        display_results()

if __name__ == "__main__":
    main()
