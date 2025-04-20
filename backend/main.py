# main.py

from analyze_hand import analyze_video

VIDEO_PATH    = "./videos/clip2.mp4"
OUTPUT_JSON   = "./video_analysis.json"
PROMPT = '''
Give me the details of the game in the moment. I want you to be very concise (no additional text).
Organize in the following format:

Board: (cards on the board)
Players:
    - name: (name)
        cards: (cards)
        action: (action)
        chips: (chips)
        position: (position)

    - name: (name)
        cards: (cards)
        action: (action)
        chips: (chips)
        position: (position)
       ...

Pot: (total pot)
Blinds: (big blind) / (small blind)

NOTE: If you cannot see the cards, just return: "NO INFORMATION"
'''
INTERVAL_SECS = 1.5
MAX_WORKERS   = 8  # tune this to your CPU / network

if __name__ == '__main__':
    results = analyze_video(
        video_path=VIDEO_PATH,
        prompt=PROMPT,
        interval_secs=INTERVAL_SECS,
        max_workers=MAX_WORKERS
    )
    print(f"Completed analysis: {len(results)} frames processed.")
