import os, json
from dotenv import load_dotenv
from google import genai
from google.genai import types

def setup_gemini_client():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return genai.Client(api_key=api_key)


def generate_speech(moment_analysis, history, timestamp):
    client = setup_gemini_client()
    prompt = (
        f"Previous speeches: {json.dumps(history)}\n"
        f"Analysis of this moment: {moment_analysis}\n"
        
        """Write a concise professional commentary text for this moment.
        You are a poker commentator. So respond accordingly with the situation.
        If there are big actions or ALL INs, be excited! But keep you responses
        relatively short. Don't exceed 12 words"""
    )
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[prompt],
        config=types.GenerateContentConfig(temperature=0.2)
    )
    return {"timestamp": timestamp, "text": resp.text.strip()}


def main(input_commentate='./commentate_decisions.json', output_speech='./speech.json'):
    # Load commentation decisions
    with open(input_commentate) as f:
        comments = json.load(f)
    # Track speeches
    speeches = []
    for c in comments:
        if c.get('commentate') == 'YES':
            # placeholder: analysis could be in comments, or load separately
            analysis = c.get('analysis', '')
            speech_entry = generate_speech(analysis, speeches, c['timestamp'])
            speeches.append(speech_entry)
    with open(output_speech, 'w') as sf:
        json.dump(speeches, sf, indent=4)
    print(f"✅ Speech JSON written to {output_speech}")

if __name__ == '__main__':
    main()