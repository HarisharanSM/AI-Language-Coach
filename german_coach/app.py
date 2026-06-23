import os
import json
from flask import Flask, render_template, request, jsonify
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List
import io
import speech_recognition as sr
from pydub import AudioSegment
import random

app = Flask(__name__)

# Initialize the Gemini Client
# Automatically picks up GEMINI_API_KEY environment variable
client = genai.Client()
MODEL_ID = 'gemini-2.5-flash-lite'

# In-memory storage for simplicity (Resets when server restarts)
session_data = {
    "script": [],
    "current_turn": 0,
    "actual_transcript": [] # Keeps track of what you and AI actually said out loud
}

# Mapping based on your completed VHS A1 Course modules
VHS_A1_TOPICS = {
    1: "Hallo! Wie geht's? (Greetings, introductions, basic well-being questions)",
    2: "Meine Familie und ich (Talking about family members, relationships, and yourself)",
    3: "Deutsch lernen (Discussing language learning, classroom items, basic study habits)",
    4: "Essen und trinken (Buying groceries, ordering food, talking about meals/preferences)",
    5: "Mein Tag (Daily routines, telling time, scheduling basic daily activities)",
    6: "Meine Wohnung (Describing an apartment, rooms, furniture, and living spaces)",
    7: "In der Stadt (Asking for directions, navigating public transport, locations in a city)",
    8: "Arbeit und Beruf (Talking about jobs, professions, workplaces, and simple tasks)",
    9: "Beim Arzt (Visiting the doctor, describing basic body parts, saying where it hurts)",
    10: "Gestern und heute (Simple temporal comparisons, daily habits, current states)",
    11: "Was ziehe ich an? (Talking about clothes, shopping for apparel, colors, and sizes)",
    12: "Jahreszeiten und Wetter (Weather conditions, seasons, simple outdoor plans)"
}

@app.route('/')
def index():
    return render_template('index.html')

class DialogueTurn(BaseModel):
    speaker: str = Field(description="Must be either 'User' or 'AI_Partner'")
    english: str = Field(description="The dialogue line written in simple English.")
    german_target: str = Field(
        description="The German translation. It MUST strictly use A1-level grammar (present tense only, simple word order, basic vocabulary)."
    )

class ScenarioScript(BaseModel):
    scenario_title: str = Field(description="A basic A1-appropriate daily topic description.")
    dialogue: List[DialogueTurn] = Field(
        description="A list of 8 to 12 simple, alternating dialogue turns simulating a beginner conversation."
    )

@app.route('/generate_script', methods=['POST'])
def generate_script():
    """Generates a complete multi-turn scenario dialogue script based on a random VHS A1 topic module"""
    
    # 1. Pick a random topic index between 1 and 12
    random_topic_id = random.randint(1, 12)
    chosen_topic_description = VHS_A1_TOPICS[random_topic_id]
    
    print(f"Selected Topic #{random_topic_id}: {chosen_topic_description}")
    
    # 2. Dynamic Prompt Injection
    prompt = f"""
    Create a highly realistic conversation scenario between a 'User' and an 'AI_Partner' tailored strictly for a GERMAN A1 BEGINNER.
    
    Mandatory Topic Framework:
    - You MUST base this entire roleplay scenario on this specific theme: "Topic Module #{random_topic_id}: {chosen_topic_description}".
    - Design a clear, practical real-world setting for this topic (e.g., if the topic is 'Beim Arzt', the scene is checking in at a clinic reception desk).
    
    Language & Grammar Guidelines for A1:
    - Use only the simplest vocabulary relevant to this specific topic framework.
    - Sentences must be short, direct, and conversational (maximum 8-12 words per line).
    - Use ONLY Present Tense (Präsens). Do not use past tenses, subjunctive forms (avoid 'hätte gerne'; use 'Ich möchte...' instead), or subordinate clauses with 'weil' or 'dass'.
    
    Structure:
    - Provide an extensive, alternating dialogue script containing between 12 to 16 total turns (User -> AI_Partner -> User -> AI_Partner). This ensures a thorough back-and-forth flow.
    """
    
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ScenarioScript,
            temperature=0.6 # A bit of variance for fresh scenario generation
        )
    )
    
    script_data = json.loads(response.text)
    actual_turns = script_data.get("dialogue", [])
    
    session_data["script"] = actual_turns
    session_data["current_turn"] = 0
    session_data["actual_transcript"] = []
    
    return jsonify({
        "status": "success", 
        "script": actual_turns,
        "topic_id": random_topic_id,
        "topic_name": chosen_topic_description.split(" (")[0] # Sends cleaner title to UI
    })

from pydub import AudioSegment
import speech_recognition as sr
import io
import os

@app.route('/process_audio', methods=['POST'])
def process_audio():
    """Converts the incoming browser audio block into valid PCM WAV format, then transcribes"""
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
        
    audio_file = request.files['audio']
    
    # Define filenames for conversion steps
    incoming_temp = "incoming_raw_file.tmp"
    converted_wav = "processed_pcm_output.wav"
    
    # Save the raw data blob sent by the browser
    audio_file.save(incoming_temp)
    
    user_spoken_german = ""
    
    try:
        print("Converting raw browser stream into PCM WAV formatting...")
        # Pydub automatically detects the underlying codec wrapper (.webm/.ogg)
        sound = AudioSegment.from_file(incoming_temp)
        
        # Enforce standard speech recognition parameters: Mono, 16000Hz, WAV container export
        sound = sound.set_frame_rate(16000).set_channels(1)
        sound.export(converted_wav, format="wav")
        
        # Pass the formatted WAV file directly into the Speech Recognizer
        recognizer = sr.Recognizer()
        with sr.AudioFile(converted_wav) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio_data = recognizer.record(source)
            
            print("Transcribing audio...")
            user_spoken_german = recognizer.recognize_google(audio_data, language="de-DE")
            print(f"Transcription Success: '{user_spoken_german}'")
            
    except sr.UnknownValueError:
        user_spoken_german = "[No clear speech recognized]"
        print("Speech recognition could not parse voice artifacts.")
    except sr.RequestError as e:
        user_spoken_german = "[STT Gateway Request Error]"
        print(f"API request fail; {e}")
    except Exception as e:
        user_spoken_german = "[Processing Error]"
        print(f"Error handling media pipeline: {str(e)}")
    finally:
        # Clean up temporary server files immediately to keep container clean
        for temp_file in [incoming_temp, converted_wav]:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    # --- Keep your standard dialogue tracking logic working seamlessly ---
    script = session_data["script"]
    current_idx = session_data["current_turn"]
    
    session_data["actual_transcript"].append({
        "speaker": "User",
        "expected_english": script[current_idx]["english"],
        "actual_german": user_spoken_german
    })
    
    current_idx += 1
    ai_response_german = ""
    
    if current_idx < len(script) and script[current_idx]["speaker"] == "AI_Partner":
        ai_response_german = script[current_idx]['german_target']
        session_data["actual_transcript"].append({
            "speaker": "AI_Partner",
            "actual_german": ai_response_german
        })
        current_idx += 1
        
    session_data["current_turn"] = current_idx
    is_finished = current_idx >= len(script)
    
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