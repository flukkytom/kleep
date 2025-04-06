import openai, json, whisper
import tempfile
import math
from moviepy.editor import VideoFileClip

openai.api_key = "your-open-ai-key"

from openai import OpenAI

client = OpenAI()

def transcribe_audio(audio_path):
    model = whisper.load_model("base")
    result = model.transcribe(audio_path, word_timestamps=True)
    print("Transcription done.")

    words = []
    if 'segments' in result:
        for segment in result['segments']:
            if 'words' in segment:
                words.extend(segment['words'])  # detailed word-level
            else:
                # fallback (rare)
                words.append({
                    'start': segment.get('start', 0),
                    'end': segment.get('end', 0),
                    'text': segment.get('text', '').strip()
                })
    return words


def segment_transcript(full_text, segment_duration, video_duration):
    words = full_text.split()
    words_per_segment = math.ceil(len(words) / (video_duration / segment_duration))
    segments = []

    for i in range(0, len(words), words_per_segment):
        segment_text = " ".join(words[i:i+words_per_segment])
        start_time = (i // words_per_segment) * segment_duration
        end_time = min(start_time + segment_duration, video_duration)
        segments.append({
            "start": start_time,
            "end": end_time,
            "text": segment_text
        })
    return segments




def score_segments(segments):
    scored = []

    for seg in segments:
        prompt = f"""
You're an expert social media video editor.

Please rate the following video transcript excerpt for its viral potential on a scale of 0 to 100.

Also give a 1-2 sentence explanation WHY it is or isn't likely to go viral (focus on emotions, surprises, curiosity, humor, value).

Return your answer in this strict JSON format:
{{
    "viral_score": number,
    "reason": "your explanation here"
}}

Excerpt:
\"\"\"
{seg['text']}
\"\"\"
"""

        res = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        try:
            result = json.loads(res.choices[0].message.content.strip())
            viral_score = result.get('viral_score', 0)
            reason = result.get('reason', "No reason provided.")
        except Exception as e:
            print(f"Error parsing AI response: {e}")
            viral_score = 0
            reason = "Parsing error."

        scored.append({
            **seg,
            "viral_score": viral_score,
            "reason": reason
        })

    # Sort clips by highest viral score
    scored = sorted(scored, key=lambda x: x['viral_score'], reverse=True)

    return scored


def score_segments_with_ai(segments):
    scored = []

    for seg in segments:
        if not seg['text'].strip():
            scored.append({
                **seg,
                "viral_score": 0,
                "reason": "Empty transcript, skipped."
            })
            continue

        prompt = f"""
You're an expert social media video editor.

Please rate the following video excerpt for its VIRAL potential on a scale from 0 to 100.

Also explain in 1 short sentence WHY it's likely (or unlikely) to go viral.

Return ONLY strict JSON like this:

{{
  "viral_score": 85,
  "reason": "It is emotional and surprising."
}}

Here is the excerpt:
\"\"\"
{seg['text']}
\"\"\"
"""
        try:
            res = openai.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )

            raw = res.choices[0].message.content.strip()

            print("\nRAW AI RESPONSE:")
            print(raw)
            print("END RAW\n")

            if not raw:
                raise ValueError("Empty response from OpenAI")

            # 🛠 CLEAN UP ANY TRIPLE BACKTICKS
            raw = raw.replace('```json', '').replace('```', '').strip()

            result = json.loads(raw)

            viral_score = int(result.get("viral_score", 0))
            reason = result.get("reason", "No reason provided.")

        except Exception as e:
            print(f"Error parsing AI response: {e}")
            viral_score = 0
            reason = "AI error or empty."

        scored.append({
            **seg,
            "viral_score": viral_score,
            "reason": reason
        })

    # Sort by viral_score descending
    scored = sorted(scored, key=lambda s: s["viral_score"], reverse=True)

    return scored


def extract_top_segments(video_path, full_transcript=None, max_moments=10):
    try:
        video = VideoFileClip(video_path)
        duration = int(video.duration)
    except Exception as e:
        print(f"Error opening video for duration: {e}")
        return [], full_transcript

    # Step 1: Use provided transcript, or extract from video
    if not full_transcript:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_audio:
            video.audio.write_audiofile(
                tmp_audio.name,
                fps=16000,
                bitrate="32k"
            )
            full_transcript = transcribe_audio(tmp_audio.name)

    # Step 2: Analyze transcript for viral moments
    moments = analyze_transcript_for_moments(full_transcript, max_moments=max_moments)

    # Step 3: Attach transcript text to each moment
    segments = []
    for moment in moments:
        segment_text = extract_text_for_segment(full_transcript, moment['start'], moment['end'])
        segments.append({
            **moment,
            "text": segment_text if segment_text else "Transcript not available."
        })

    video.close()
    return segments, full_transcript



def extract_text_for_segment(full_transcript, clip_start, clip_end):
    if not full_transcript:
        return ""

    if isinstance(full_transcript, str):
        return full_transcript  # fallback if somehow old

    selected_words = []

    for word in full_transcript:
        word_start = word.get('start', 0)
        word_end = word.get('end', 0)
        text = word.get('text', '').strip()

        if word_start < clip_end and word_end > clip_start and text:
            selected_words.append(text)

    return ' '.join(selected_words)


def parse_timestamp(timestamp):
    """
    Parse a timestamp like '00:01:23,000' to seconds.
    """
    h, m, s = timestamp.replace(',', ':').split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)



def analyze_transcript_for_moments(transcript_text, max_moments=10):
    prompt = f"""
You are a world-class social media video editor.

Given the following transcript from a long video:

---
{transcript_text}
---

Your job:
- Find the best VIRAL-WORTHY MOMENTS.
- For each moment, provide:
    - "start" time (in seconds)
    - "end" time (in seconds)
    - "reason" (1 line explaining why it could go viral)
    - "viral_score" (an integer from 0 to 100, where 100 = most viral potential)

Rules:
- Each moment should be between 30 and 90 seconds long.
- Only find clear, complete thoughts (don't cut in middle of sentences).
- Return no more than {max_moments} moments total.
- FORMAT your entire output as a clean JSON array, NO commentary.

Example format:
[
  {{"start": 12, "end": 47, "reason": "Funny joke about cats", "viral_score": 85}},
  {{"start": 150, "end": 200, "reason": "Inspiring quote about persistence", "viral_score": 90}},
  ...
]
"""

    try:
        res = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )

        raw = res.choices[0].message.content.strip()

        print("\nRAW AI RESPONSE:")
        print(raw)
        print("END RAW\n")

        # Clean any backticks if GPT sends Markdown
        raw = raw.replace('```json', '').replace('```', '').strip()

        moments = json.loads(raw)

        # Validate moments to enforce 30–90 seconds
        valid_moments = []
        for moment in moments:
            duration = moment['end'] - moment['start']
            if 35 <= duration <= 90:
                valid_moments.append(moment)
            else:
                print(f"Skipping invalid clip: {duration:.2f}s - {moment}")

        return valid_moments

    except Exception as e:
        print(f"Error during viral moment analysis: {e}")
        return []


