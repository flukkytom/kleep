from flask import Flask, request, render_template, send_from_directory, url_for, session, redirect
# from flask import render_template, request, redirect, url_for, session
from video_utils import download_video, clip_segments
from helpers import allowed_file, sanitize_filename, beautify_title
import os, uuid, re
from werkzeug.utils import secure_filename
from ai_clip_extractor import extract_top_segments, score_segments_with_ai, transcribe_audio
from datetime import datetime

CLIPS_FOLDER = 'static/clips'
MAX_FILE_SIZE_MB = 400 #MB

def register_routes(app):

    @app.route('/')
    def index():
        return render_template('index.html', year=datetime.now().year)

    @app.route('/process', methods=['POST'])
    def process():
        url = request.form.get('url')
        uploaded_file = request.files.get('video_file')
        should_burn_captions = request.form.get('burn_captions', 'yes')
        caption_style = request.form.get('caption_style', 'professional')
        just_download = request.form.get('just_download') 


        if just_download:
            # Just download the video, no processing
            video_path, real_title, video_title, project_folder = download_video(url)
            session['real_title'] = real_title

            return render_template('results.html', video_path=video_path, real_title=real_title, clips=[])
        
        elif uploaded_file and uploaded_file.filename != '':
            filename = secure_filename(uploaded_file.filename)

            if not allowed_file(filename):
                return " Only MP4, MOV, MKV files are allowed.", 400

            uploaded_file.seek(0, 2)
            file_size = uploaded_file.tell() / (1024 * 1024)
            uploaded_file.seek(0)

            if file_size > MAX_FILE_SIZE_MB:
                return f" File too large! Max {MAX_FILE_SIZE_MB} MB allowed.", 400

            real_title = filename.rsplit('.', 1)[0]
            sanitized_filename = sanitize_filename(real_title) + '.mp4'

            project_folder = os.path.join(CLIPS_FOLDER, f"project_{sanitized_filename}")
            os.makedirs(project_folder, exist_ok=True)

            saved_video_path = os.path.join(project_folder, 'full_video.mp4')
            uploaded_file.save(saved_video_path)

            video_path = saved_video_path
            video_title = sanitized_filename
            session['real_title'] = real_title

        elif url:
            video_path, real_title, video_title, project_folder = download_video(url)
            session['real_title'] = real_title

        else:
            return " No video URL or file uploaded!", 400

        #  Step 1: Transcribe audio to text
        transcript_text = transcribe_audio(video_path)

        #  Step 2: Find highlight segments from transcript
        highlight_segments, _ = extract_top_segments(video_path, full_transcript=transcript_text, max_moments=10)

        #  Step 3: Clip video based on those moments
        clips = clip_segments(video_path, highlight_segments, video_title, project_folder, should_burn_captions, caption_style, full_transcript=transcript_text)


        #  Step 4: Store results in session
        session['clips'] = clips
        session['video_title'] = video_title

        return redirect(url_for('results_page'))


    @app.route('/results')
    def results_page():
        clips = session.get('clips', [])
        # title = session.get('video_title', 'Unknown Video')
        real_title = session.get('real_title', 'Untitled Video')
        pretty_title = beautify_title(real_title)

        return render_template('results.html', clips=clips, real_title=pretty_title, year=datetime.now().year)

    @app.route('/clips/<filename>')
    def serve_clip(filename):
        return send_from_directory(CLIPS_FOLDER, filename)
    
    @app.route('/about')
    def about():
        # return render_template('about.html')
        return render_template('about.html', year=datetime.now().year)

