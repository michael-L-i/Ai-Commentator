# backend/app.py
import os, json, tempfile
from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
from analyze_hand import analyze_video

app = Flask(__name__, static_folder=None)
CORS(app)  # so your frontend can fetch across ports

# Create audio directory if it doesn't exist
audio_dir = "./audio"
os.makedirs(audio_dir, exist_ok=True)

# Initialize manifest - handle case when file doesn't exist
manifest = []
manifest_path = os.path.join(audio_dir, 'manifest.json')
try:
    if os.path.exists(manifest_path) and os.path.getsize(manifest_path) > 0:
        with open(manifest_path) as f:
            manifest = json.load(f)
except Exception as e:
    print(f"Warning: Could not load manifest file: {e}")
    # Create an empty manifest file
    with open(manifest_path, 'w') as f:
        json.dump([], f)

def reload_manifest():
    global manifest
    try:
        if os.path.exists(manifest_path) and os.path.getsize(manifest_path) > 0:
            with open(manifest_path) as f:
                manifest = json.load(f)
    except Exception as e:
        print(f"Warning: Could not reload manifest file: {e}")

def get_audio_entry(t):
    for e in manifest:
        if e['start'] <= t < e['end']:
            return e
    return None

@app.route('/audio/<path:filename>')
def serve_audio(filename):
    return send_from_directory(audio_dir, filename)

@app.route('/next-audio')
def next_audio():
    # GET /next-audio?time=12.34
    try:
        t = float(request.args.get('time', 0))
    except:
        return jsonify(error="invalid time"), 400

    # Ensure we have the latest manifest
    reload_manifest()
    
    entry = get_audio_entry(t)
    if not entry:
        return jsonify(filename=None), 200

    # compute how far into the clip we already are
    offset = t - entry['start']
    return jsonify(
        filename=entry['filename'],
        offset=offset
    )

@app.route('/process-video-chunk', methods=['POST'])
def process_video_chunk():
    if 'video' not in request.files:
        return jsonify(error="No video file provided"), 400
    
    video_file = request.files['video']
    chunk_time = float(request.form.get('chunkTime', '0'))
    chunk_duration = float(request.form.get('chunkDuration', '10'))  # Default to 10 seconds
    
    # Create a temporary file for the video chunk
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
        video_path = tmp.name
        video_file.save(video_path)
    
    try:
        # Set up the analysis prompt
        prompt = '''
        Give me the details of the game in the moment. I want you to be very concise (no additional text).
        Organize in the following format:

        Board: (cards on the board)
        Players:
            - name: (name)
                cards: (cards - expand abbreviations to say like 'Ace of Clubs')
                action: (action)
                chips: (chips)
                position: (position)

            - name: (name)
                cards: (cards - expand abbreviations to say like 'Ace of Clubs')
                action: (action)
                chips: (chips)
                position: (position)
               ...

        Pot: (total pot)
        Blinds: (big blind) / (small blind)

        NOTE: If you cannot see the cards, just return: "NO INFORMATION"
        '''
        
        # Run analysis on the video chunk
        results = analyze_video(
            video_path=video_path,
            prompt=prompt,
            interval_secs=1.5,
            max_workers=4,
            start_time=chunk_time,
            duration=chunk_duration
        )
        
        # Reload manifest after analysis
        reload_manifest()
        
        # Cleanup the temporary file
        os.unlink(video_path)
        
        # Return the analysis results along with success message
        return jsonify(
            success=True, 
            message=f"Video chunk from {chunk_time}s to {chunk_time + chunk_duration}s processed successfully",
            results=results,
            chunkTime=chunk_time
        )
    except Exception as e:
        # Ensure temp file is cleaned up even on error
        if os.path.exists(video_path):
            os.unlink(video_path)
        return jsonify(error=str(e)), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)