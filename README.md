Here we present an AI commentator for the game of poker.

The key attributes that make this DIFFICULT are:
- latency (we want immediate reactions for real-life commentators but models take a long time to process the visual elements, generate a respond, and then create an audio file to play)
- accuracy (hallucinations)

We tackle both these issues using Gemini's new 2.5 flash model alongside some techniques to make it appear as 0 latency responses to the users.

Specifically, we follow this pipeline:
1. Parse input information and decide if any major event occurs. We first use Gemini once to extract the game board and important facial reactions / actions
   --> we store a game board for tracking, and based on the provided information at the current timestamp, decide if the model should say something or not. We keep a running timestamp logged every second
2. If something relevant occured, we start generating a response and parse an audio .wav file.
3. Once we have the .wav file, we log it in the backend with a timestamp attached
4. The KEY is HERE:
      - The user sees a 10-15s delay of what the model sees
      - We will check the cache of all timestamped audio file and see if the current timestamp the model had said something or not
      - If yes, we play the .wav file, otherwise we continue.
5. All this paried with some techniques to prevent audio play overlapped led to a MVP for an AI commentator for poker!!!
