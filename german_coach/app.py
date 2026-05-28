import os
import json
from flask import Flask, render_template, request, jsonify
from google import genai
from google.genai import types

app = Flask(__name__)

# Initialize the Gemini Client
# Automatically picks up GEMINI_API_KEY environment variable
client = genai.Client()
MODEL_ID = 'gemini-2.5-flash'

# In-memory storage for simplicity (Resets when server restarts)
session_data = {
    "script": [],
    "current_turn": 0,
    "actual_transcript": [] # Keeps track of what you and AI actually said out loud
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_script', methods=['POST'])
def generate_script():
    """Generates a 5-minute scenario dialogue script using Gemini"""
    prompt = """
    Generate a 5-minute realistic conversation scenario between a 'User' and an 'AI_Partner'.
    Pick a practical topic (e.g., ordering food, checking into a hotel, or buying a train ticket).
    
    Output strictly valid JSON with a list of dialogue turns. Do not wrap in markdown blocks like ```json.
    Each turn must contain:
    1. 'speaker': Either 'User' or 'AI_Partner'
    2. 'english': The line in English
    3. 'german_target': The mathematically/grammatically ideal German translation for reference.
    
    Example format:
    [
      {"speaker": "User", "english": "Hello, I'd like a coffee.", "german_target": "Hallo, ich hätte gerne einen Kaffee."},
      {"speaker": "AI_Partner", "english": "Sure, with milk?", "german_target": "Gerne, mit Milch?"}
    ]
    """
    
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.7
        )
    )
    
    script = json.loads(response.text)
    session_data["script"] = script
    session_data["current_turn"] = 0
    session_data["actual_transcript"] = []
    
    return jsonify({"status": "success", "script": script})

@app.route('/process_audio', methods=['POST'])
def process_audio():
    """Handles Voice-to-Text, Agent Roleplay Engine, and Text-to-Voice"""
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
        
    audio_file = request.files['audio']
    
    # 1. VOICE-TO-TEXT (Using Gemini's Native Multimodal Audio Capability)
    # We save the temporary audio file to send to Gemini
    audio_path = "temp_user_input.wav"
    audio_file.save(audio_path)
    
    # Upload audio using the Files API
    audio_upload = client.files.upload(file=audio_path)
    
    # Ask Gemini to transcribe the spoken German accurately
    transcription_prompt = "Transcribe exactly what is spoken in this audio file. The language spoken is German. Do not translate it. Output only the transcription."
    stt_response = client.models.generate_content(
        model=MODEL_ID,
        contents=[audio_upload, transcription_prompt]
    )
    user_spoken_german = stt_response.text.strip()
    
    # Clean up the audio upload
    client.files.delete(name=audio_upload.name)
    if os.path.exists(audio_path):
        os.remove(audio_path)
        
    # Log what the user actually said
    script = session_data["script"]
    current_idx = session_data["current_turn"]
    
    session_data["actual_transcript"].append({
        "speaker": "User",
        "expected_english": script[current_idx]["english"],
        "actual_german": user_spoken_german
    })
    
    # Advance to the AI's turn
    current_idx += 1
    ai_response_german = ""
    
    # 2. THE ACTOR: If it's the AI's turn, fetch its response script line
    if current_idx < len(script) and script[current_idx]["speaker"] == "AI_Partner":
        ai_line = script[current_idx]
        
        # We let Gemini adapt the target slightly to sound perfectly conversational based on history
        actor_prompt = f"""
        You are roleplaying a scenario. The target line to say is: "{ai_line['german_target']}".
        Say this line naturally in German. Do not add explanations, do not break character.
        """
        actor_response = client.models.generate_content(model=MODEL_ID, contents=actor_prompt)
        ai_response_german = actor_response.text.strip()
        
        session_data["actual_transcript"].append({
            "speaker": "AI_Partner",
            "actual_german": ai_response_german
        })
        current_idx += 1 # Advance past AI turn
        
    session_data["current_turn"] = current_idx
    is_finished = current_idx >= len(script)
    
    # 3. TEXT-TO-VOICE (Simulated via a Gemini text generation requested to act as a placeholder, 
    # or you can seamlessly drop in ElevenLabs/OpenAI TTS bytes here. For simplicity, we pass text back 
    # to the frontend to use the native browser SpeechSynthesis API, saving bandwidth and latency!)
    
    return jsonify({
        "user_transcription": user_spoken_german,
        "ai_response_german": ai_response_german,
        "is_finished": is_finished,
        "next_turn_idx": current_idx
    })

@app.route('/get_feedback', methods=['POST'])
def get_feedback():
    """Phase 3: The AI Coach processes the transcript and reviews errors"""
    transcript = session_data["actual_transcript"]
    
    feedback_prompt = f"""
    You are an expert German Language Coach. Review the following transcript of a roleplay.
    Compare what the 'User' actually spoke in German against the 'expected_english' blueprint line they were attempting to translate.
    
    Transcript Data:
    {json.dumps(transcript, ensure_ascii=False)}
    
    Provide a comprehensive review. Format your output cleanly in HTML. 
    Include:
    1. A summary of how well they did.
    2. A line-by-line breakdown of the User's turns showing:
       - What they tried to say (English)
       - What they actually said (German Spoken)
       - The ideal/corrected German way to say it.
       - Clear, encouraging bullet points explaining grammatical errors, case issues (Dativ/Akkusativ), word order changes, or vocabulary improvements.
    """
    
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=feedback_prompt
    )
    
    return jsonify({"feedback_html": response.text})

if __name__ == '__main__':
    app.run(debug=True, port=5000)