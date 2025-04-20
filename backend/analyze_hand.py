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

def analyze_video(video_path, prompt, interval_secs=1.0, max_workers=8, start_time=0, duration=None):
    """
    Analyze a segment of video
    
    Args:
        video_path: Path to video file
        prompt: Prompt for Gemini
        interval_secs: Interval between frames
        max_workers: Max parallel workers
        start_time: Start time in seconds
        duration: Duration to process in seconds, or None for entire video
    """
    load_dotenv()
    client_11labs = ElevenLabs(
       api_key=os.getenv("ELEVENLABS_API_KEY"),
    )
    client = setup_gemini_client()

    # Ensure audio directory exists
    audio_dir = "./audio"
    os.makedirs(audio_dir, exist_ok=True)

    # Paths for outputs - all stored in audio directory
    analysis_path   = f"{audio_dir}/video_analysis.json"
    commentate_path = f"{audio_dir}/commentate_decisions.json"
    speech_path     = f"{audio_dir}/speech.json"
    voice_path      = f"{audio_dir}/manifest.json"

    # Load existing data from files if they exist
    raw_results = []
    comments = []
    speeches = []
    voice_entries = []
    
    # Load existing analysis data
    if os.path.exists(analysis_path) and os.path.getsize(analysis_path) > 0:
        try:
            with open(analysis_path, 'r') as f:
                raw_results = json.load(f)
            print(f"Loaded {len(raw_results)} existing analysis entries")
        except Exception as e:
            print(f"Error loading analysis file: {e}")
    
    # Load existing comment decisions
    if os.path.exists(commentate_path) and os.path.getsize(commentate_path) > 0:
        try:
            with open(commentate_path, 'r') as f:
                comments = json.load(f)
            print(f"Loaded {len(comments)} existing comment decisions")
        except Exception as e:
            print(f"Error loading comment decisions file: {e}")
    
    # Load existing speech data
    if os.path.exists(speech_path) and os.path.getsize(speech_path) > 0:
        try:
            with open(speech_path, 'r') as f:
                speeches = json.load(f)
            print(f"Loaded {len(speeches)} existing speech entries")
        except Exception as e:
            print(f"Error loading speech file: {e}")
    
    # Load existing voice entries
    if os.path.exists(voice_path) and os.path.getsize(voice_path) > 0:
        try:
            with open(voice_path, 'r') as f:
                voice_entries = json.load(f)
            print(f"Loaded {len(voice_entries)} existing voice entries")
        except Exception as e:
            print(f"Error loading voice entries file: {e}")

    # ——— PHASE 1: probe & parallel frame analysis ———
    probe = ffmpeg.probe(video_path)
    vs = next(s for s in probe["streams"] if s["codec_type"] == "video")
    full_duration = float(vs.get("duration", probe["format"]["duration"]))
    
    # If duration is specified, use it, otherwise process the entire video
    if duration is None:
        process_duration = full_duration - start_time
    else:
        process_duration = min(duration, full_duration - start_time)
    
    # Make sure we don't try to process beyond the end of the video
    if start_time >= full_duration:
        print(f"Start time {start_time}s is beyond video duration {full_duration}s")
        return []
    
    num_frames = math.ceil(process_duration / interval_secs)
    print(f"Processing from {start_time}s for {process_duration:.2f}s → {num_frames} frames @ {interval_secs}s intervals")

    # Prepare (frame_index, timestamp) tasks
    frame_tasks = [
        (i, min(start_time + i * interval_secs, start_time + process_duration)) 
        for i in range(num_frames)
    ]

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
        new_results = list(executor.map(analyze_one, frame_tasks))

    # Append new results to existing ones
    raw_results.extend(new_results)

    # Save combined analyses
    with open(analysis_path, "w") as af:
        json.dump(raw_results, af, indent=4)
    print(f"Wrote {len(raw_results)} entries to {analysis_path}")

    # ——— PHASE 2a: single-pass commentation decision ———
    commentation_prompt = (
        f"You are a poker commentator. Below is a JSON array of frame analyses:\n\n"
        f"{json.dumps(raw_results)}\n\n"
        "For each entry decide if it's worthy of commentary, following these rules:\n"
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

    new_comments = json.loads(raw_text[start:end+1])
    
    # Add only new timestamps that don't already exist in comments
    existing_timestamps = {c["timestamp"] for c in comments}
    for comment in new_comments:
        if comment["timestamp"] not in existing_timestamps:
            comments.append(comment)

    with open(commentate_path, "w") as cf:
        json.dump(comments, cf, indent=4)
    print(f"Wrote commentation decisions to {commentate_path}")

    # ——— PHASE 2b: speech generation after comment JSON is complete ———
    # Filter comments for only YES entries that don't already have speeches
    speech_timestamps = {s["timestamp"] for s in speeches}
    comments_to_process = [c for c in comments if c["commentate"] == "YES" and c["timestamp"] not in speech_timestamps]
    
    for entry in comments_to_process:
        # find the corresponding analysis
        analysis_text = next((r["analysis"] for r in raw_results if r["frame"] == entry["frame"]), "No analysis available")
        speech_prompt = (
            f"Speech history: {json.dumps(speeches)}\n"
            f"Moment analysis: {raw_results}\n"
            f"Current timestamp: {entry['timestamp']}\n"
            "Write a concise professional poker commentary (<=15 words). "
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

    # ——— PHASE 2c: refine speech with additional context ———
    # Send all data to Gemini for refinement of speeches
    refinement_prompt = (
        f"You are a poker commentator refining existing commentary. Review the following data:\n\n"
        f"Video analysis: {json.dumps(raw_results)}\n\n"
        f"Commentary decisions: {json.dumps(comments)}\n\n" 
        f"Current speech entries: {json.dumps(speeches)}\n\n"
        "For each speech entry, provide an improved version that is:\n"
        "- Brief and concise (under 15 words)\n"
        """- To not repeat content you already mentioned in the speech history
        For example, if it is alrady mentioend that someone did an action earlier
        in the speech, try not to mention again a direct manner\n"""
        "-If the text mentions abbreviations (like 20K), expand them to the full text (like 20 thousand)"
        "Maintain the same timestamps."
    )
    
    if speeches:  # Only run refinement if there are speeches to refine
        r_resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[refinement_prompt],
            config=types.GenerateContentConfig(temperature=0.2)
        )
        
        # Extract the JSON array from the response
        refined_text = r_resp.text.strip()
        start = refined_text.find('[')
        end = refined_text.rfind(']')
        
        if start >= 0 and end >= 0:
            try:
                refined_speeches = json.loads(refined_text[start:end+1])
                # Replace the speeches with refined versions
                speeches = refined_speeches
                # Save the refined speeches
                with open(speech_path, "w") as sf:
                    json.dump(speeches, sf, indent=4)
                print(f"Wrote refined speech output to {speech_path}")
            except Exception as e:
                print(f"Error parsing refined speeches: {e}")

    # ——— PHASE 3: text to audio ———
    # Only process speeches that don't already have audio files
    speech_entries_to_process = [s for s in speeches if not any(v["start"] == s["timestamp"] for v in voice_entries)]
    
    for entry in speech_entries_to_process:
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
    with open(voice_path, "w") as vf:
        json.dump(voice_entries, vf, indent=4)
    print(f"Wrote voice file paths to {voice_path}")

    return raw_results
