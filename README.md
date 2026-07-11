# AI-Powered German Language Coach 🤖🗣️

An intelligent, voice-first roleplay application tailored for CEFR A1-level beginners to practice conversational German in real-world scenarios.

<img width="2880" height="1704" alt="image" src="https://github.com/user-attachments/assets/d5ff4b6e-de6e-4f00-9d98-37e0dc0c53d9" />

---

## Core Features & Workflow

### 🎯 Use Case
A personal project developed to bridge the gap between rigid grammar drills and unpredictable conversations. The app helps absolute beginners safely build speaking confidence through structured, AI-driven roleplays.

---

### 🚀 Application Workflow

#### 1. Scenario Generation
* The user initiates a new session by clicking **"Generate New Scenario Script"**.
* The backend randomly selects one of 12 standard Volkshochschule (VHS) A1 curriculum topics (e.g., *Greetings*, *Family*, *Food*, *Daily Routines*).
* **Gemini AI** generates a contextual, 8-to-12 turn dialogue script containing English situational prompts alongside the corresponding German target phrases.

#### 2. Interactive Practice (Voice-to-Text)
* The application displays an **English prompt** to guide the learner's intent.
* The user triggers the recording via **"Click to Speak German"** to deliver their vocal response.
* An integrated Speech-to-Text (STT) engine transcribes the German utterance in real-time.
* The dialogue UI advances automatically, alternating fluidly between user inputs and AI partner responses.

#### 3. Dual-Mode Toggle Architecture
Users can switch dynamically between two learning paradigms depending on their current confidence level:
* **Scripted Roleplay Mode:** A guided experience where the user follows the structured path of the pre-generated dialogue script (ideal for building muscle memory).
* **Free Speech Mode:** An unscripted environment where the user engages in open-ended conversation. Gemini AI dynamically evaluates inputs and responds organically while strictly maintaining beginner-level complexity.

#### 4. Automated Feedback & Evaluation
* Upon completing the scenario, the user clicks **"End Scene & Get Feedback"**.
* The backend processes the multi-turn session logs, analyzing the user's transcriptions against strict A1 grammar rules.
* The system returns an evaluation report featuring real-time grammatical corrections and pronunciation insights.

---

### ✨ Key Technical Features
* **CEFR A1 Constrained Prompts:** Safety guardrails lock language generation to simple vocabulary and present tense rules only.
* **Voice-First Learning:** Hands-free approach utilizing voice recording and robust Speech-to-Text processing.
* **State & Session Tracking:** Maintains full historical context and variable tracking across multi-turn dialogues.
* **Real-Time Dialogue Logging:** Live logging infrastructure to stream and audit conversation states.
* **Intelligent Evaluation Pipeline:** AI-driven grading backend providing actionable, contextual feedback instantly.
