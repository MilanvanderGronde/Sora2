import streamlit as st
import requests
import time
import os

# --------------------------
# SoraClient Class (Backend Logic)
# --------------------------
class SoraClient:
    """
    Handles all interactions with the OpenAI Video API.
    """
    API_BASE = "https://api.openai.com/v1"

    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def create_job(self, prompt, model, seconds, size):
        url = f"{self.API_BASE}/videos"
        payload = {
            "model": model,
            "prompt": prompt,
            "seconds": seconds,  # API expects a string, e.g., "8"
            "size": size
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            # Handle 401 Unauthorized specifically
            if e.response.status_code == 401:
                return {"error": "Invalid API Key. Please check your credentials."}
            # Return detailed error from API if available
            return {"error": e.response.text or str(e)}
        except requests.exceptions.RequestException as e:
            return {"error": f"Connection error: {str(e)}"}

    def get_status(self, video_id):
        url = f"{self.API_BASE}/videos/{video_id}"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"status": "error", "error": str(e)}

    def download_video(self, video_id, progress_callback=None):
        """
        Downloads video content with a progress bar callback.
        """
        url = f"{self.API_BASE}/videos/{video_id}/content"
        try:
            response = requests.get(url, headers=self.headers, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024 * 1024 # 1MB chunks
            
            video_content = bytearray()
            downloaded = 0
            
            for chunk in response.iter_content(block_size):
                if chunk:
                    video_content.extend(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size > 0:
                        percent = min(downloaded / total_size, 1.0)
                        progress_callback(percent)
            
            return bytes(video_content)
        except requests.exceptions.RequestException as e:
             raise RuntimeError(f"Download failed: {e}")

# --------------------------
# Streamlit App (Frontend UI)
# --------------------------
def main():
    st.set_page_config(page_title="Sora 2 Studio", page_icon="🎥", layout="wide")

    # Custom CSS to hide the "Running" man and clean up UI
    st.markdown("""
        <style>
        .stTextArea textarea { font-size: 16px; }
        .stButton button { width: 100%; border-radius: 8px; font-weight: bold;}
        div[data-testid="stStatusWidget"] { visibility: hidden; }
        </style>
    """, unsafe_allow_html=True)

    st.title("🎥 Sora 2 Video Generator")
    st.markdown("Generate ultra-realistic videos using OpenAI's Sora 2 model.")

    # --- Sidebar: Configuration ---
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        env_key = os.getenv("OPENAI_API_KEY", "")
        api_key = st.text_input("OpenAI API Key", value=env_key, type="password")
        
        st.divider()
        
        # Validated Model List
        model = st.selectbox("Model", ["sora-2", "sora-2-pro"], index=0)
        
        # STRICT List of Supported Resolutions (Square/Custom often fail in v1)
        sizes = [
            "1920x1080", # Landscape 1080p
            "1080x1920", # Vertical 1080p
            "1280x720",  # Landscape 720p
            "720x1280",  # Vertical 720p (Default for Shorts/Reels)
            "480x854",   # Vertical 480p
            "854x480"    # Landscape 480p
        ]
        size = st.selectbox("Resolution (WxH)", sizes, index=3) 
        
        seconds = st.select_slider("Duration (Seconds)", options=["4", "8", "12"], value="8")
        
        st.caption("Note: 'sora-2-pro' may incur higher costs.")

    # --- Main Area ---
    col1, col2 = st.columns([1.5, 1])

    with col1:
        st.subheader("🎬 Describe your video")
        prompt = st.text_area(
            "Prompt", 
            height=300, 
            placeholder="Describe the scene, lighting, camera movement...",
        )
        generate_btn = st.button("🚀 Generate Video", type="primary")

    with col2:
        st.subheader("📺 Output")
        output_container = st.empty()

        if generate_btn:
            if not api_key:
                st.error("Please provide an OpenAI API Key in the sidebar.")
                return
            if not prompt:
                st.error("Please enter a prompt.")
                return

            client = SoraClient(api_key)
            
            # Use st.status for a clean log container
            with st.status("Initializing...", expanded=True) as status_box:
                
                # 1. Create Job
                status_box.write("📡 Sending request to OpenAI...")
                job = client.create_job(prompt, model, seconds, size)
                
                if job.get("error"):
                    status_box.update(label="❌ Error", state="error")
                    st.error(f"API Error: {job['error']}")
                    return

                video_id = job.get("id")
                if not video_id:
                     status_box.update(label="❌ Error", state="error")
                     st.error(f"API Error: No Video ID returned. Response: {job}")
                     return

                status_box.write(f"✅ Job started! ID: `{video_id}`")
                
                # ---------------------------------------------------------
                # PROGRESS BAR 1: GENERATION
                # ---------------------------------------------------------
                gen_bar = output_container.progress(0, text="Job Queued...")
                status_text = status_box.empty() # Placeholder for single-line updates
                
                while True:
                    time.sleep(4) # Poll every 4 seconds
                    job_status = client.get_status(video_id)
                    state = job_status.get("status", "unknown")
                    progress = job_status.get("progress", 0)

                    # Update Logs (Overwrite previous line)
                    status_text.markdown(f"🔄 Status: **{state}** ({progress}%)")
                    
                    # Update Progress Bar
                    if state == "queued":
                        gen_bar.progress(5, text="⏳ Queued in OpenAI cloud...")
                    elif state in ["processing", "in_progress"]: 
                        display_prog = max(int(progress), 10)
                        gen_bar.progress(display_prog, text=f"🎨 Rendering: {progress}%")

                    # CRITICAL FIX: Accept both "succeeded" AND "completed"
                    if state in ["succeeded", "completed"]:
                        gen_bar.progress(100, text="✅ Rendering Complete!")
                        status_box.update(label="✅ Generation Complete!", state="complete")
                        time.sleep(0.5)
                        gen_bar.empty()
                        break
                    
                    elif state in ["failed", "canceled", "rejected", "error"]:
                        gen_bar.progress(0, text="❌ Failed")
                        status_box.update(label="❌ Generation Failed", state="error")
                        st.error(f"Job failed with status: {state}")
                        if job_status.get("error"):
                            st.error(job_status['error'])
                        return
                
                # ---------------------------------------------------------
                # PROGRESS BAR 2: DOWNLOADING
                # ---------------------------------------------------------
                status_box.write("⬇️ Downloading video file...")
                dl_bar = output_container.progress(0, text="Downloading high-res video...")
                
                try:
                    def update_dl_bar(percent):
                        dl_bar.progress(percent, text=f"⬇️ Downloading: {int(percent*100)}%")

                    video_bytes = client.download_video(video_id, progress_callback=update_dl_bar)
                    
                    dl_bar.empty()
                    output_container.video(video_bytes)
                    
                    st.download_button(
                        label="💾 Download MP4",
                        data=video_bytes,
                        file_name=f"sora_{video_id}.mp4",
                        mime="video/mp4"
                    )
                except Exception as e:
                    status_box.update(label="❌ Download Error", state="error")
                    st.error(f"Error downloading video: {e}")

if __name__ == "__main__":
    main()