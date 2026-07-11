import os
import json
import random
from typing import List
from flask import Flask, render_template, request, jsonify, session
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from pydub import AudioSegment
import speech_recognition as sr

app = Flask(__name__)

# CRITICAL: Adds a signing key so Flask can persist session data arrays securely across requests
app.secret_key = "german_coach_super_secure_encrypted_key_98765"

# Initialize the Gemini Client
client = genai.Client()
MODEL_ID = 'gemini-2.5-flash-lite'

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_script', methods=['POST'])
def generate_script():
    """Generates a complete multi-turn scenario dialogue script based on a random VHS A1 topic module"""
    random_topic_id = random.randint(1, 12)
    chosen_topic_description = VHS_A1_TOPICS[random_topic_id]
    
    print(f"Selected Topic #{random_topic_id}: {chosen_topic_description}")
    
    # Securely initialize user cookie lists
    session["script"] = []
    session["current_turn"] = 0
    session["actual_transcript"] = []
    session["chosen_topic_context"] = chosen_topic_description
    
    prompt = f"""
    Create a highly realistic conversation scenario between a 'User' and an 'AI_Partner' tailored strictly for a GERMAN A1 BEGINNER.
    
    Mandatory Topic Framework:
    - You MUST base this entire roleplay scenario on this specific theme: "Topic Module #{random_topic_id}: {chosen_topic_description}".
    
    Language & Grammar Guidelines for A1:
    - Use only the simplest vocabulary relevant to this specific topic framework.
    - Sentences must be short, direct, and conversational (maximum 8-12 words per line).
    - Use ONLY Present Tense (Präsens). Do not use past tenses, subjunctive forms, or complex subordinate clauses.
    """
    
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ScenarioScript,
                temperature=0.6
            )
        )
        script_data = json.loads(response.text)
        session["script"] = script_data.get("dialogue", [])
    except Exception as e:
        print(f"Generation error: {e}")
        session["script"] = []

    session.modified = True
    return jsonify({
        "status": "success", 
        "script": session["script"],
        "topic_id": random_topic_id,
        "topic_name": chosen_topic_description.split(" (")[0]
    })

@app.route('/process_audio', methods=['POST'])
def process_audio():
    """Converts the incoming browser audio block into valid PCM WAV format, then transcribes"""
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
        
    audio_file = request.files['audio']
    mode = request.form.get('mode', 'SCRIPTED') # Reads the UI state toggle
    
    incoming_temp = "incoming_raw_file.tmp"
    converted_wav = "processed_pcm_output.wav"
    audio_file.save(incoming_temp)
    
    user_spoken_german = ""
    try:
        sound = AudioSegment.from_file(incoming_temp)
        sound = sound.set_frame_rate(16000).set_channels(1)
        sound.export(converted_wav, format="wav")
        
        recognizer = sr.Recognizer()
        with sr.AudioFile(converted_wav) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio_data = recognizer.record(source)
            user_spoken_german = recognizer.recognize_google(audio_data, language="de-DE")
            print(f"Transcription Success: '{user_spoken_german}'")
    except sr.UnknownValueError:
        user_spoken_german = "[No speech recognized]"
    except Exception as e:
        print(f"Media conversion breakdown: {e}")
        user_spoken_german = "[Processing Error]"
    finally:
        for temp_file in [incoming_temp, converted_wav]:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    script = session.get("script", [])
    current_idx = session.get("current_turn", 0)
    transcript_log = session.get("actual_transcript", [])
    ai_response_german = ""
    is_finished = False

    # --- DYNAMIC FREE SPEECH LOGIC BRANCH ---
    if mode == "FREE":
        transcript_log.append({
            "speaker": "User",
            "expected_english": "[Free Conversational Speech Mode]",
            "actual_german": user_spoken_german
        })
        
        # Build contextual window baseline log for agent processing
        history_context = f"Theme/Setting: {session.get('chosen_topic_context', 'General German Conversation')}\n"
        for turn in transcript_log:
            history_context += f"{turn['speaker']}: {turn['actual_german']}\n"
            
        free_speech_prompt = f"""
        You are an interactive AI roleplay partner acting contextually inside a scene. 
        Current conversation history log:
        {history_context}
        
        Respond naturally to the last line spoken by the User.
        Strict Rules:
        - You MUST use simple, clear A1-level German sentences (Present tense only).
        - Output ONLY your single line of character dialogue response. Do not add metadata, translations, or notes.
        """
        
        try:
            actor_response = client.models.generate_content(model=MODEL_ID, contents=free_speech_prompt)
            ai_response_german = actor_response.text.strip() if actor_response.text else "Ich habe dich nicht verstanden."
        except Exception as e:
            ai_response_german = "Es gibt einen Systemfehler."
            
        transcript_log.append({
            "speaker": "AI_Partner",
            "actual_german": ai_response_german
        })

    # --- STANDARD SCRIPTED LOGIC BRANCH ---
    else:
        if current_idx < len(script):
            transcript_log.append({
                "speaker": "User",
                "expected_english": script[current_idx]["english"],
                "actual_german": user_spoken_german
            })
            current_idx += 1
            
        if current_idx < len(script) and script[current_idx]["speaker"] == "AI_Partner":
            ai_response_german = script[current_idx]['german_target']
            transcript_log.append({
                "speaker": "AI_Partner",
                "actual_german": ai_response_german
            })
            current_idx += 1
            
        session["current_turn"] = current_idx
        is_finished = current_idx >= len(script)
        
    session["actual_transcript"] = transcript_log
    session.modified = True
    
    return jsonify({
        "user_transcription": user_spoken_german,
        "ai_response_german": ai_response_german,
        "is_finished": is_finished,
        "next_turn_idx": current_idx
    })

@app.route('/get_feedback', methods=['POST'])
def get_feedback():
    """Phase 3: The AI Coach processes the persistent transcript cookies and reviews errors"""
    transcript = session.get("actual_transcript", [])
    
    if not transcript:
        return jsonify({"feedback_html": "<p>No active speech data items recorded this session.</p>"})
        
    feedback_prompt = f"""
    You are an expert German Language Coach specializing in CEFR A1 teaching methods. Review the following transcript logs:
    {json.dumps(transcript, ensure_ascii=False)}
    
    Provide a comprehensive review. Format your output cleanly inside HTML components (Do not wrap output with markdown ```html block strings).
    Include:
    1. A summary of how well they did (fluency, overall vocabulary accuracy).
    2. A line-by-line breakdown of the User's turns showing:
       - What they tried to say (English context context targets)
       - What they actually said (German Spoken)
       - The ideal/corrected German way to phrase it cleanly at A1 level.
       - Explanations breaking down case assignments (Akkusativ/Dativ), word placements (V2 structure), or verb conjugations.
    """
    
    response = client.models.generate_content(model=MODEL_ID, contents=feedback_prompt)
    return jsonify({"feedback_html": response.text})

@app.route('/clear_session', methods=['POST'])
def clear_session():
    """Wipes out the conversation logs when toggling modes"""
    session["actual_transcript"] = []
    session["current_turn"] = 0
    session.modified = True
    return jsonify({"status": "cleared"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)