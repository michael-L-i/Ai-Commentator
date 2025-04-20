# backend/app.py
import os, json
from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS

app = Flask(__name__, static_folder=None)
CORS(app)  # so your frontend can fetch across ports

# load manifest once
with open(os.path.join('audio','manifest.json')) as f:
    manifest = json.load(f)

def get_audio_entry(t):
    for e in manifest:
        if e['start'] <= t < e['end']:
            return e
    return None

@app.route('/audio/<path:filename>')
def serve_audio(filename):
    return send_from_directory('audio', filename)

@app.route('/next-audio')
def next_audio():
    # GET /next-audio?time=12.34
    try:
        t = float(request.args.get('time', 0))
    except:
        return jsonify(error="invalid time"), 400

    entry = get_audio_entry(t)
    if not entry:
        return jsonify(filename=None), 200

    # compute how far into the clip we already are
    offset = t - entry['start']
    return jsonify(
        filename=entry['filename'],
        offset=offset
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)