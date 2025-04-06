from moviepy.editor import VideoFileClip
import os, uuid, re, glob, subprocess, json, shutil
import shlex
import tempfile
from ai_clip_extractor import extract_top_segments, score_segments_with_ai, transcribe_audio
from helpers import sanitize_filename, crop_to_vertical, is_vertical
import yt_dlp
from werkzeug.utils import secure_filename
from pysrt import SubRipFile, SubRipItem, SubRipTime

CLIPS_FOLDER = 'static/clips'
STYLE_MAP = {
    'professional': "FontName=Arial,FontSize=11,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=1,Outline=3,Shadow=1",
    'fun': "FontName=Comic Sans MS,FontSize=11,PrimaryColour=&H0000FFFF,OutlineColour=&H80000000,BorderStyle=1,Outline=3,Shadow=1",
    'minimal': "FontName=Helvetica,FontSize=12,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=0,Shadow=0",
    'red_alert': "FontName=Impact,FontSize=11,PrimaryColour=&H000000FF,OutlineColour=&H80000000,BorderStyle=1,Outline=4,Shadow=1",
}

def download_video(url):
    output_template = os.path.join(CLIPS_FOLDER, '%(title)s.%(ext)s')
    ydl_opts = {
        'outtmpl': output_template,
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    real_title = info['title']
    sanitized_title = sanitize_filename(real_title)

    # Search for the downloaded .mp4 file
    matches = glob.glob(os.path.join(CLIPS_FOLDER, '*.mp4'))
    if not matches:
        raise Exception("Downloaded video not found!")

    original_video_path = matches[0]  # first mp4 found
    print(f"Downloaded video path: {original_video_path}")

    # Create project folder
    project_folder = os.path.join(CLIPS_FOLDER, f"project_{sanitized_title}")
    os.makedirs(project_folder, exist_ok=True)

    target_video_path = os.path.join(project_folder, 'full_video.mp4')
    os.rename(original_video_path, target_video_path)

    return target_video_path, real_title, sanitized_title, project_folder


def create_srt(text, start, end, srt_path):
    def format_time(t):
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        ms = int((t % 1) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("1\n")
        f.write(f"{format_time(0)} --> {format_time(end - start)}\n")
        f.write(text + "\n")

def create_srt_from_text(text, output_path, clip_start=0, clip_end=30):
    if not text.strip():
        print(f" Empty text provided to create_srt_from_text, skipping.")
        return

    words = text.split()
    chunk_size = 7  # Approx 7 words per subtitle
    chunks = [' '.join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
    
    total_duration = clip_end - clip_start
    seconds_per_chunk = total_duration / max(len(chunks), 1)

    def format_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    with open(output_path, "w", encoding="utf-8") as f:
        for idx, chunk in enumerate(chunks):
            start_sec = clip_start + idx * seconds_per_chunk
            end_sec = start_sec + seconds_per_chunk
            if end_sec > clip_end:
                end_sec = clip_end

            f.write(f"{idx+1}\n")
            f.write(f"{format_time(start_sec)} --> {format_time(end_sec)}\n")
            f.write(chunk.strip() + "\n\n")
    print(f" SRT file created at {output_path}")


def burn_subtitles(video_path, srt_path, output_path, style='professional'):
    style_options = STYLE_MAP.get(style, STYLE_MAP['professional'])  # ← Get style safely
    
    subtitles_filter = f"subtitles={shlex.quote(srt_path)}:force_style='{style_options}'"

    command = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vf", subtitles_filter,
        "-c:a", "copy",
        "-movflags", "+faststart", 
        output_path
    ]

    try:
        print(f"🛠️ Running command: {' '.join(command)}")  # Helpful log
        subprocess.run(command, check=True)
        print(f" Subtitles burned successfully to {output_path}")
    except subprocess.CalledProcessError as e:
        print(f" Failed to burn subtitles: {e}")


def burn_captions(input_video, srt_path, output_video, style='professional'):
    burn_subtitles(input_video, srt_path, output_video, style=style)


def create_srt_from_segments(segments, output_path, clip_start=0, clip_end=None):
    idx = 1
    with open(output_path, "w", encoding="utf-8") as f:
        for segment in segments:
            start = segment['start']
            end = segment['end']

            # Only use segments that fit inside this clip
            if start >= clip_end:
                break
            if end <= clip_start:
                continue

            # Adjust timing to clip relative
            adj_start = max(start - clip_start, 0)
            adj_end = min(end - clip_start, clip_end - clip_start)

            def format_time(seconds):
                h = int(seconds // 3600)
                m = int((seconds % 3600) // 60)
                s = int(seconds % 60)
                ms = int((seconds % 1) * 1000)
                return f"{h:02}:{m:02}:{s:02},{ms:03}"

            f.write(f"{idx}\n")
            f.write(f"{format_time(adj_start)} --> {format_time(adj_end)}\n")
            f.write(segment['text'].strip() + "\n\n")
            idx += 1


def get_rotation(filepath):
    try:
        command = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream_tags=rotate", "-of", "json", filepath
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if not result.stdout:
            return 0
        info = json.loads(result.stdout)
        rotation = int(info['streams'][0]['tags'].get('rotate', 0))
        return rotation
    except Exception as e:
        print(f" Could not detect rotation: {e}")
        return 0


def detect_video_orientation(video_path):
    clip = VideoFileClip(video_path)
    w, h = clip.size
    rotation = get_rotation(video_path)

    is_vertical = (h > w) or (rotation in [90, 270])

    print(f" Video loaded: {w}x{h} | Rotation: {rotation}° | Detected as: {'Vertical' if is_vertical else 'Horizontal'}")
    
    clip.close()
    return 'vertical' if is_vertical else 'horizontal'


def detect_orientation(video_path):
    clip = VideoFileClip(video_path)
    w, h = clip.size
    clip.close()

    # ffprobe to check rotation
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream_tags=rotate",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        rotation_str = result.stdout.strip()
        rotation = int(rotation_str) if rotation_str else 0
    except Exception as e:
        print(f"ffprobe error: {e}")
        rotation = 0

    print(f"🖥️ Original loaded video: {w}x{h} (Rotation: {rotation}°)")

    if rotation in [90, 270]:
        print(f" Rotation says vertical (rotation {rotation}°)")
        is_vertical = True
    elif h > w:
        print(f" Height > Width: definitely vertical.")
        is_vertical = True
    else:
        print(f" Width > Height and rotation 0: assume horizontal.")
        is_vertical = False

    return is_vertical

def process_upload_or_url(url=None, uploaded_file=None):
    if uploaded_file and uploaded_file.filename != '':
        filename = secure_filename(uploaded_file.filename)
        sanitized_filename = sanitize_filename(filename.rsplit('.', 1)[0]) + '.mp4'

        project_folder = os.path.join(CLIPS_FOLDER, f"project_{sanitized_filename}")
        os.makedirs(project_folder, exist_ok=True)

        saved_video_path = os.path.join(project_folder, 'full_video.mp4')
        uploaded_file.save(saved_video_path)

        video_path = saved_video_path
        video_title = sanitized_filename

        # Transcribe full uploaded video
        full_transcript = transcribe_audio(video_path)
        print(" Uploaded video transcribed.")

    elif url:
        video_path, video_title, project_folder = download_video(url)
        full_transcript = None

    else:
        raise Exception("No video URL or file uploaded!")

    return video_path, video_title, project_folder, full_transcript

def slice_transcript_by_time(full_transcript, clip_start, clip_end, video_duration=None):
    if not full_transcript:
        return []

    selected_words = []

    for word in full_transcript:
        word_start = word.get('start', 0)
        word_end = word.get('end', 0)
        text = word.get('text', '').strip()

        if word_start < clip_end and word_end > clip_start and text:
            selected_words.append(word)

    return selected_words


def extract_subclip(video_path, start, end, output_path):
    clip = VideoFileClip(video_path).subclip(start, end)
    clip.write_videofile(
        output_path,
        codec='libx264',
        audio_codec='aac',
        temp_audiofile='temp-audio.m4a',
        remove_temp=True,
        logger=None
    )
    clip.close()

from datetime import timedelta

def format_timestamp(seconds):
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    milliseconds = int((td.total_seconds() - total_seconds) * 1000)
    return f"{total_seconds // 3600:02}:{(total_seconds % 3600) // 60:02}:{total_seconds % 60:02},{milliseconds:03}"



def seconds_to_subrip_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return SubRipTime(hours=hours, minutes=minutes, seconds=secs, milliseconds=milliseconds)


def generate_caption_srt(selected_words, srt_path, clip_start, clip_end):
    subs = SubRipFile()

    for i, word in enumerate(selected_words):
        start_sec = word.get('start', clip_start)
        end_sec = word.get('end', clip_end)

        subs.append(
            SubRipItem(
                index=i+1,
                start=seconds_to_subrip_time(start_sec - clip_start),
                end=seconds_to_subrip_time(end_sec - clip_start),
                text=word.get('text', '')
            )
        )

    subs.save(srt_path, encoding='utf-8')
    print(f" SRT file saved: {srt_path}")


def create_vertical_version(input_video, output_video):
    crop_to_vertical(input_video, output_video)

def build_clip_metadata(project_folder, clip_filename, segment, caption_text):
    return {
        "project_folder": os.path.basename(project_folder),
        "clip_file": os.path.basename(clip_filename),
        "start": segment['start'],
        "end": segment['end'],
        "reason": segment.get('reason', 'No reason provided'),
        "viral_score": segment.get('viral_score', 0),
        "caption_text": caption_text
    }


MIN_CLIP_LENGTH = 15  # minimum duration in seconds for any clip

def clip_segments(video_path, segments, title_prefix, project_folder, should_burn_captions='yes', caption_style='professional', full_transcript=None):
    try:
        clip = VideoFileClip(video_path)
        w, h = clip.size
        duration = clip.duration
        is_vertical = h > w
    except Exception as e:
        print(f" Error loading video: {e}")
        return []

    safe_prefix = sanitize_filename(title_prefix)
    clipped_files = []

    for i, seg in enumerate(segments):
        try:
            start = max(0, seg['start'] - 0.5)  # small pad before start
            end = min(seg['end'], duration)
            if start >= duration or (end - start) < 5:
                print(f" Skipping clip {i+1}: invalid or too short.")
                continue

            print(f" Processing clip {i+1}: start={start:.2f}, end={end:.2f}, duration={end-start:.2f}s")

            #  Step 1: Extract raw clip
            raw_clip_path = os.path.join(project_folder, f"{safe_prefix}_clip_{i+1}_raw.mp4")
            extract_subclip(video_path, start, end, raw_clip_path)
            print(f" Extracted raw clip to: {raw_clip_path}")

            #  Step 2: Slice words from transcript
            selected_words = slice_transcript_by_time(full_transcript, start, end, duration)

            if should_burn_captions == 'yes' and selected_words:
                #  Step 3: Generate SRT
                srt_path = os.path.join(project_folder, f"{safe_prefix}_clip_{i+1}.srt")
                generate_caption_srt(selected_words, srt_path, start, end)
                print(f" SRT file created at {srt_path}")

                #  Step 4: Burn subtitles
                captioned_path = os.path.join(project_folder, f"{safe_prefix}_clip_{i+1}_captioned.mp4")
                burn_captions(raw_clip_path, srt_path, captioned_path, caption_style)
                print(f" Burned captioned clip created at: {captioned_path}")
                final_clip_path = captioned_path
            else:
                print(f" No captions for clip {i+1}, using raw clip.")
                final_clip_path = raw_clip_path

            #  Step 5: Handle vertical version
            vertical_clip_path = os.path.join(project_folder, f"{safe_prefix}_clip_{i+1}_vertical.mp4")
            if is_vertical:
                shutil.copy2(final_clip_path, vertical_clip_path)
                print(f" Copied vertical clip: {vertical_clip_path}")
            else:
                create_vertical_version(final_clip_path, vertical_clip_path)
                print(f" Created vertical version: {vertical_clip_path}")

            #  Step 6: Clip metadata
            clip_info = build_clip_metadata(project_folder, vertical_clip_path, seg, " ".join([w['text'] for w in selected_words]))
            clipped_files.append(clip_info)

        except Exception as e:
            print(f" Error processing clip {i+1}: {e}")
            continue

    clip.close()
    return clipped_files
