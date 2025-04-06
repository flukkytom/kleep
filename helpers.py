import os, uuid, re
from moviepy.editor import VideoFileClip

ALLOWED_EXTENSIONS = {'mp4', 'mov', 'mkv'}

def sanitize_filename(name):
    # Remove problematic characters, including apostrophes
    name = re.sub(r'[\\/*?:"<>|\']', "", name)  # <-- notice the apostrophe ' added
    name = name.replace(' ', '_')
    return name.lower()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_vertical(video_clip):
    w, h = video_clip.size
    return h > w

def beautify_title(title):
    # Replace underscores with spaces and title-case it
    clean_title = title.replace('_', ' ').title()
    return clean_title

def crop_to_vertical(input_path, output_path):
    try:
        clip = VideoFileClip(input_path)
        w, h = clip.size
        print(f"📐 Cropping video: {input_path} | Size: {w}x{h}")

        if w < h:
            print("Already vertical. Just resizing height to 1080.")
            final_clip = clip.resize(height=1080)
        else:
            print("✂️ Cropping horizontal to 9:16 vertical.")
            new_w = int(h * 9 / 16)
            if new_w > w:
                new_w = w
            x_center = w / 2
            x1 = x_center - new_w / 2
            x2 = x_center + new_w / 2
            final_clip = clip.crop(x1=x1, x2=x2).resize(height=1080)

        final_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            preset='ultrafast',
            threads=4,
            fps=24,
            logger=None
        )
        print(f"Cropped and saved vertical video: {output_path}")
    except Exception as e:
        print(f"Error during vertical crop: {e}")
    finally:
        clip.close()

