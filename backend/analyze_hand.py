# analyze_hand.py

import os
import io
import json
import math
import ffmpeg                        # ffmpeg-python
from PIL import Image                # Pillow for cropping
from dotenv import load_dotenv
from google import genai
from google.genai import types
import concurrent.futures
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

def setup_gemini_client():
    """Initialize and return Gemini API client"""
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in .env")
    return genai.Client(api_key=api_key)

def analyze_video(video_path, prompt, interval_secs=1.0, max_workers=8):
    load_dotenv()
    client_11labs = ElevenLabs(
       api_key=os.getenv("ELEVENLABS_API_KEY"),
    )
    client = setup_gemini_client()

    # Paths for outputs
    analysis_path   = "./video_analysis.json"
    commentate_path = "./commentate_decisions.json"
    speech_path     = "./speech.json"
    voice_path      = "./manifest.json"
    audio_dir       = "./audio"

    # Initialize empty histories
    comments = []
    speeches = []
    voice_entries = []

    # Ensure audio directory exists
    os.makedirs(audio_dir, exist_ok=True)

    # ——— PHASE 1: probe & parallel frame analysis ———
    probe = ffmpeg.probe(video_path)
    vs = next(s for s in probe["streams"] if s["codec_type"] == "video")
    duration = float(vs.get("duration", probe["format"]["duration"]))
    num_frames = math.ceil(duration / interval_secs)
    print(f"Duration {duration:.2f}s → {num_frames} frames @ {interval_secs}s intervals")

    # Prepare (frame_index, timestamp) tasks
    frame_tasks = [(i, min(i * interval_secs, duration)) for i in range(num_frames)]

    def analyze_one(args):
        i, ts = args
        out, err = (
            ffmpeg.input(video_path, ss=ts)
                  .output("pipe:", vframes=1, format="image2pipe", vcodec="png")
                  .run(capture_stdout=True, capture_stderr=True, quiet=True)
        )
        if not out:
            text = f"ffmpeg error: {err}"
        else:
            img = Image.open(io.BytesIO(out))
            w, h = img.size
            cropped = img.crop((0, int(h * 0.7), w, h))
            resp = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[prompt, cropped],
                config=types.GenerateContentConfig(temperature=0.1)
            )
            text = resp.text.strip()

        return {"frame": i, "timestamp": round(ts, 2), "analysis": text}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        raw_results = list(executor.map(analyze_one, frame_tasks))

    # Save raw analyses
    with open(analysis_path, "w") as af:
        json.dump(raw_results, af, indent=4)
    print(f"Wrote {len(raw_results)} entries to {analysis_path}")

    # ——— PHASE 2a: single-pass commentation decision ———
    commentation_prompt = (
        f"You are a poker commentator. Below is a JSON array of frame analyses:\n\n"
        f"{json.dumps(raw_results)}\n\n"
        "For each entry decide if it’s worthy of commentary, following these rules:\n"
        "- Only comment on big actions (bets, raises, ALL INs).\n"
        "- Aim for ~1 comment every 10 frames; no two YES within 10 seconds.\n"
        "- Reply with a JSON array of the same length, each object:\n"
        "  {\"timestamp\": <number>, \"frame\": <int>, \"commentate\": \"YES\"|\"NO\"}\n"
        "Return _only_ the JSON array."
    )
    c_resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[commentation_prompt],
        config=types.GenerateContentConfig(temperature=0.0)
    )

    # Robustly extract the JSON array from the LLM response:
    raw_text = c_resp.text.strip()
    start = raw_text.find('[')
    end   = raw_text.rfind(']')
    if start == -1 or end == -1:
        raise ValueError(f"Failed to parse commentation JSON from LLM response:\n{raw_text}")

    comments = json.loads(raw_text[start:end+1])

    with open(commentate_path, "w") as cf:
        json.dump(comments, cf, indent=4)
    print(f"Wrote commentation decisions to {commentate_path}")

    # ——— PHASE 2b: speech generation after comment JSON is complete ———
    for entry in comments:
        if entry["commentate"] == "YES":
            # find the corresponding analysis
            analysis_text = next(r["analysis"] for r in raw_results if r["frame"] == entry["frame"])
            speech_prompt = (
                f"Speech history: {json.dumps(speeches)}\n"
                f"Moment analysis: {raw_results}\n"
                f"Current timestamp: {entry['timestamp']}\n"
                "Write a concise professional poker commentary (<=15 words). "
                "Be calm except for ALL INs where you show excitement."
                """Be sure to be variable in the content you present — don't repeats
                content you already mentioned in the speech history. Specifically, sometimes
                it may be hard to tell what action happened. Check the moment analysis to see
                what changed at the timestamp."""
            )
            s_resp = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[speech_prompt],
                config=types.GenerateContentConfig(temperature=0.2)
            )
            speeches.append({
                "timestamp": entry["timestamp"],
                "text": s_resp.text.strip()
            })

    with open(speech_path, "w") as sf:
        json.dump(speeches, sf, indent=4)
    print(f"Wrote speech output to {speech_path}")

    # ——— PHASE 3: text to audio ———
    for entry in speeches:
        response = client_11labs.text_to_speech.convert(
            voice_id="pNInz6obpgDQGcFmaJgB", # Adam pre-made voice
            output_format="mp3_22050_32",
            text=entry["text"],
            model_id="eleven_turbo_v2_5", # use the turbo model for low latency
            # Optional voice settings that allow you to customize the output
            voice_settings=VoiceSettings(
                stability=0.0,
                similarity_boost=1.0,
                style=0.4,
                use_speaker_boost=True,
                speed=1.0,
            ),
        )

        audio_path = f"{audio_dir}/{entry['timestamp']}.mp3"
        with open(audio_path, "wb") as f:
            for chunk in response:
                if chunk:
                    f.write(chunk)
        
        # Add entry to voice_entries list
        voice_entries.append({
            "filename": os.path.basename(audio_path),
            "start": entry["timestamp"],
            "end": entry["timestamp"] + float(ffmpeg.probe(audio_path)["format"]["duration"])
        })

    # Save voice entries to manifest.json
    with open(f"{audio_dir}/{voice_path}", "w") as vf:
        json.dump(voice_entries, vf, indent=4)
    print(f"Wrote voice file paths to {voice_path}")

    return raw_results
