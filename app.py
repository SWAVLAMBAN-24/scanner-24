import streamlit as st
import cv2
import numpy as np
from github import Github
import pandas as pd
import io
from datetime import datetime
import re
from streamlit_javascript import st_javascript

# GitHub token setup
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

def main():
    st.title("QR Code Scanner")

    if not GITHUB_TOKEN:
        st.error("GitHub token not configured. Please set up the token securely.")
        return

    scan_method = st.radio("Choose scanning method:", ("Upload Image", "Use Camera"))

    if scan_method == "Upload Image":
        uploaded_file = st.file_uploader("Choose an image file", type=["jpg", "jpeg", "png"])
        
        if uploaded_file is not None:
            file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
            image = cv2.imdecode(file_bytes, 1)
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            st.image(image_rgb, caption="Uploaded Image", use_column_width=True)
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
        
        # JavaScript to access the camera and capture image
        js_code = """
        async function setupCamera() {
            const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
            const video = document.createElement('video');
            video.srcObject = stream;
            video.setAttribute('playsinline', true); // required to tell iOS safari we don't want fullscreen
            video.play();
            return [video, stream];
        }

        async function takePhoto(video) {
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext('2d').drawImage(video, 0, 0);
            return canvas.toDataURL('image/jpeg');
        }

        let video, stream;
        try {
            [video, stream] = await setupCamera();
            while (true) {
                await new Promise(resolve => setTimeout(resolve, 1000)); // Wait for 1 second
                const result = await takePhoto(video);
                if (result) {
                    stream.getTracks().forEach(track => track.stop());
                    return result;
                }
            }
        } catch (error) {
            console.error('Error accessing camera:', error);
            return null;
        }
        """
        
        if 'camera_result' not in st.session_state:
            st.session_state.camera_result = None

        if st.button("Capture QR Code"):
            with st.spinner("Accessing camera..."):
                result = st_javascript(js_code)
                st.session_state.camera_result = result

        if st.session_state.camera_result:
            st.success("Image captured successfully!")
            
            # Convert base64 to image
            img_data = re.sub('^data:image/.+;base64,', '', st.session_state.camera_result)
            img_bytes = base64.b64decode(img_data)
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            qr_data = scan_qr(img)
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
                st.error("No QR code found in the captured image.")
                st.image(img, caption="Captured Image", use_column_width=True)

            # Clear the camera result after processing
            st.session_state.camera_result = None

    if st.button("Display Results"):
        display_results()

if __name__ == "__main__":
    main()
