import streamlit as st
import requests
import time
import os

# --------------------------
# SoraClient Class (Backend Logic)
# --------------------------
class SoraClient:
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
            "seconds": str(seconds),
            "size": size
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                return {"error": "Invalid API Key. Please check your credentials."}
            return {"error": e.response.text or str(e)}
        except requests.exceptions.RequestException as e:
            return {"error": f"Connection error: {str(e)}"}

    def get_status(self, video_id):
        url = f"{self.API_BASE}/videos/{video_id}"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def download_video(self, video_id):
        url = f"{self.API_BASE}/videos/{video_id}/content"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.content
        except Exception as e:
             raise RuntimeError(f"Download failed: {e}")

    def refine_prompt_text(self, text):
        """
        Uses a cheap model (gpt-4o-mini) to improve the prompt.
        """
        url = f"{self.API_BASE}/chat/completions"
        payload = {
            "model": "gpt-4o-mini", 
            "messages": [
                {
                    "role": "system", 
                    "content": "You are an expert prompt engineer for Sora 2 video generation. "
                               "Rewrite the user's prompt to be highly descriptive, focusing on lighting, "
                               "camera angles, textures, and physics. Keep it concise (under 150 words) but vivid."
                },
                {"role": "user", "content": text}
            ],
            "temperature": 0.7
        }
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            return f"Error refining prompt: {e}"

# --------------------------
# Helper: Cost Calculator
# --------------------------
def calculate_cost(model, seconds, size):
    duration = int(seconds)
    price_per_sec = 0.0
    
    if model == "sora-2":
        price_per_sec = 0.10
    elif model == "sora-2-pro":
        width, height = map(int, size.split("x"))
        is_hd = (width * height) > (1280 * 720)
        price_per_sec = 0.50 if is_hd else 0.30

    return price_per_sec * duration

# --------------------------
# Streamlit App
# --------------------------
def main():
    st.set_page_config(page_title="Sora 2 Studio", page_icon="🎥", layout="wide")

    # --- SESSION STATE INITIALIZATION ---
    if "refined_prompt_text" not in st.session_state:
        st.session_state.refined_prompt_text = ""

    # Custom CSS
    st.markdown("""
        <style>
        .stButton button { border-radius: 8px; font-weight: bold; }
        .cost-box { 
            background-color: #f0f2f6; 
            padding: 10px; 
            border-radius: 5px; 
            border-left: 5px solid #00c853;
            margin-bottom: 20px;
        }
        [data-testid="stStatusWidget"] { visibility: hidden; }
        </style>
    """, unsafe_allow_html=True)

    st.title("🎥 Sora 2 Studio Pro")

    # --- Sidebar ---
    with st.sidebar:
        st.header("⚙️ Settings")
        
        env_key = os.getenv("OPENAI_API_KEY", "")
        api_key = st.text_input("OpenAI API Key", value=env_key, type="password")
        
        st.markdown("""
        <small>
        🔑 <a href="https://platform.openai.com/api-keys" target="_blank">Get OpenAI API Key</a><br>
        📚 <a href="https://cookbook.openai.com/examples/sora/sora2_prompting_guide" target="_blank">Sora 2 Prompting Guide</a>
        </small>
        """, unsafe_allow_html=True)
        
        st.divider()
        model = st.selectbox("Model", ["sora-2", "sora-2-pro"], index=0)
        sizes = ["1920x1080", "1080x1920", "1280x720", "720x1280", "480x854", "854x480"]
        size = st.selectbox("Resolution", sizes, index=3)
        seconds = st.select_slider("Duration (s)", options=["4", "8", "12"], value="8")
        
        st.divider()
        st.subheader("🚀 Batch Mode")
        batch_size = st.slider("Number of Videos", 1, 5, 1)

    # --- Main Input Area (Full Width) ---
    
    # 1. Draft Section
    st.subheader("1️⃣ Concept (Draft)")
    raw_concept = st.text_area(
        "Draft your idea here...", 
        height=100, 
        placeholder="A cat eating pizza on the moon",
        key="raw_input" 
    )

    if st.button("✨ AI Refine Prompt"):
        if not api_key:
            st.error("Please enter an API Key first.")
        elif not raw_concept:
            st.warning("Please type a concept above first.")
        else:
            with st.spinner("Refining your idea..."):
                client = SoraClient(api_key)
                refined = client.refine_prompt_text(raw_concept)
                
                # Update both storage and widget key
                st.session_state.refined_prompt_text = refined
                st.session_state.final_prompt_widget = refined 
                st.rerun()

    # 2. Final Prompt Section
    st.subheader("2️⃣ Final Prompt (Ready to Generate)")
    final_prompt = st.text_area(
        "Review and edit before generating:",
        value=st.session_state.refined_prompt_text,
        height=150,
        key="final_prompt_widget"
    )
    
    active_prompt = final_prompt if final_prompt else raw_concept

    # 3. Cost & Generate
    st.write("") # Spacer
    single_cost = calculate_cost(model, seconds, size)
    total_batch_cost = single_cost * batch_size
    
    st.markdown(f"""
    <div class="cost-box">
        <b>💰 Estimated Cost:</b> ${total_batch_cost:.2f} <br>
        <small>(${single_cost:.2f} per video x {batch_size} copies)</small>
    </div>
    """, unsafe_allow_html=True)

    generate_btn = st.button(f"🚀 Generate {batch_size} Video{'s' if batch_size > 1 else ''}", type="primary", use_container_width=True)

    # --- Output Queue Section (Bottom) ---
    st.divider()
    st.subheader("📺 Output Queue")
    
    output_container = st.container()

    if generate_btn:
        if not api_key:
            st.error("Missing API Key")
            return
        if not active_prompt:
            st.error("Please enter a prompt (or refine your draft).")
            return

        client = SoraClient(api_key)
        jobs = []

        # 1. Start Jobs
        with st.status(f"🚀 Starting {batch_size} job(s)...", expanded=True) as status:
            for i in range(batch_size):
                status.write(f"Submitting job {i+1}/{batch_size}...")
                job_data = client.create_job(active_prompt, model, seconds, size)
                
                if job_data.get("error"):
                    st.error(f"Failed to start job {i+1}: {job_data['error']}")
                    continue
                    
                jobs.append({
                    "id": job_data["id"], 
                    "ui_placeholder": output_container.empty(),
                    "progress_bar": None
                })
            
            if not jobs:
                st.error("No jobs started.")
                return
            
            status.update(label="⚡ Processing Batch...", state="running")

        # 2. Poll Jobs
        active_jobs = jobs[:]
        
        while active_jobs:
            time.sleep(4)
            
            for job in reversed(active_jobs):
                data = client.get_status(job["id"])
                new_status = data.get("status", "unknown")
                progress = data.get("progress", 0)
                
                with job["ui_placeholder"].container():
                    st.write(f"**Job {job['id'][-6:]}**: `{new_status}`")
                    if not job["progress_bar"]:
                        job["progress_bar"] = st.progress(0)
                    
                    current_prog = int(progress) if progress else 0
                    if new_status == "queued":
                        job["progress_bar"].progress(5)
                    elif new_status in ["processing", "in_progress"]:
                        job["progress_bar"].progress(max(current_prog, 10))
                
                if new_status in ["succeeded", "completed"]:
                    active_jobs.remove(job)
                    with job["ui_placeholder"].container():
                        st.success(f"✅ Video {job['id'][-6:]} Ready!")
                        job["progress_bar"].progress(100)
                        try:
                            vid_bytes = client.download_video(job["id"])
                            st.video(vid_bytes)
                            st.download_button(
                                f"💾 Download {job['id'][-6:]}.mp4", 
                                vid_bytes, 
                                file_name=f"{job['id']}.mp4",
                                mime="video/mp4"
                            )
                        except Exception as e:
                            st.error(f"Download failed: {e}")
                            
                elif new_status in ["failed", "rejected", "error"]:
                    active_jobs.remove(job)
                    with job["ui_placeholder"].container():
                        st.error(f"❌ Job {job['id'][-6:]} Failed")

if __name__ == "__main__":
    main()