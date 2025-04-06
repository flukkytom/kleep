# Kleep

## 📺 Turn Videos into Viral Moments Instantly!

Kleep lets you easily upload or download YouTube videos, automatically find the most viral moments, generate captions, and produce ready-to-post clips with styled subtitles. Built using Flask, yt-dlp, Whisper AI, MoviePy, and ffmpeg.

---

## 🛠️ Features
- Upload a video file or paste a YouTube URL.
- Download full video or slice into best moments.
- Automatically transcribe speech to text (OpenAI Whisper).
- Auto-generate captions and burn them into the video.
- Choose from 4 caption styles (Professional, Fun, Minimal, Red Alert).
- Mobile-friendly vertical clips.
- Simple web interface.

---

## 🔬 Tech Stack
- **Python** 3.10+
- **Flask** (backend server)
- **yt-dlp** (for YouTube downloads)
- **OpenAI Whisper** (for transcription)
- **moviepy** (for video slicing)
- **pysrt** (for .srt subtitle generation)
- **ffmpeg** (for video and subtitle burning)

---

## 🖋️ Installation

### 1. Clone the Repo
```bash
git clone https://github.com/flukkytom/kleep.git
cd viralclipper
```

### 2. Set Up Virtual Environment
```bash
python3 -m venv environment
source environment/bin/activate  # Mac/Linux
# or
environment\Scripts\activate  # Windows
```

### 3. Install Python Requirements
```bash
pip install -r requirements.txt
```

### 4. Install ffmpeg
- MacOS: `brew install ffmpeg`
- Ubuntu: `sudo apt install ffmpeg`
- Windows: Download [ffmpeg](https://ffmpeg.org/download.html) and add to PATH.

### 5. Run Flask App
```bash
export FLASK_APP=app.py
export FLASK_ENV=development
flask run
```
Then visit [http://127.0.0.1:5000/](http://127.0.0.1:5000/)

---

## 🔎 Project Structure
```bash
veedio/
🔍 app.py (Flask app + routes)
📂 video_utils.py (Video download, clip, transcribe, caption)
📂 helper.py (sanitize, text manipulation)
📂 ai_clip_extractor.py (GPT Interaction)
📂 templates/
    └︎ index.html
    └︎ results.html
    └︎ about.html
📂 static/
    └︎ clips/ (Uploaded/downloaded/processed videos)
    └︎ images/
        └︎ logo.png
requirements.txt
README.md
```

---

## 🌐 Usage
1. Launch the app with `flask run`.
2. Open your browser.
3. Choose to upload a file or paste a YouTube URL.
4. Pick your options:
   - Burn captions? Yes/No
   - Choose caption style.
5. Click **Process Video**.
6. Download the resulting viral clips!

---

## ✨ Coming Soon
- More caption styles
- Multiple YouTube link processing
- Previews before download
- Direct social media sharing

---

## ✅ Requirements
- Python 3.10+
- ffmpeg installed
- OpenAI Whisper package (automatic install via pip)

---

## 🚀 Contributors
- [Michael Obembe](https://github.com/flukkytom)

---

## ❤️ License
This project is open source under the [MIT License](LICENSE).

---

## 👋 Support
If you find this useful, please star the repo and share! 🌟

---

> "A single viral clip can open a thousand doors."

Happy Clipping! 🎬


