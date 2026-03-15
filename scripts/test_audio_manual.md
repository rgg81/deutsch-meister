# Manual Audio Test

Step-by-step instructions for manually validating the end-to-end audio pipeline
(voice in → transcription → agent → speak tool → voice out) via Telegram.

## Prerequisites

- Bot running: `python -m nanobot gateway --config config.json`
- `config.json` has `stt` and `tts` sections configured (see `config.example.json`)
- `ffmpeg` installed (`apt install ffmpeg` or `brew install ffmpeg`)
- `faster-whisper` and `piper-tts` are installed by default via `pip install -r requirements.txt` (used only when configured in `config.json`)

### Minimal config.json audio sections

```json
{
  "stt": {
    "provider": "groq_with_fallback",
    "groq": { "api_key": "YOUR_GROQ_API_KEY" },
    "whisper": { "model": "base" }
  },
  "tts": {
    "provider": "edge_with_fallback",
    "voice": "de-DE-ConradNeural",
    "piper": { "model": "de_DE-thorsten-high" }
  }
}
```

---

## Test 1: Voice → Text (STT)

**What it validates**: Inbound voice messages are transcribed before reaching the agent.

1. Open Telegram and navigate to your bot.
2. Record and send a short voice message saying **"Guten Morgen"**.
3. **Expected**: The bot responds to your message (the response content shows the agent
   received and understood the transcribed text, proving STT worked).
4. **Check logs**: Look for a log line containing `transcrib` with the recognised text.

---

## Test 2: Text → Voice (TTS / speak tool)

**What it validates**: The agent can generate and send audio via the `speak` tool.

1. Send the text message: **"How do you pronounce Schmetterling?"**
2. **Expected**: The bot responds with a text explanation **and** a voice message
   containing the German pronunciation.
3. **Alternative trigger**: Send **`/pronounce Schmetterling`** — the bot should always
   send a voice message for `/pronounce` commands.

---

## Test 3: Full Round-Trip

**What it validates**: The complete audio loop — voice in, voice out.

1. Record and send a voice message asking:
   **"Wie sagt man butterfly auf Deutsch?"** (or any German-learning question)
2. **Expected**:
   - Bot transcribes your voice question (STT).
   - Bot responds with a text explanation.
   - Bot sends a voice message pronouncing the answer (TTS via speak tool).
3. **Check**: Both a text reply and at least one voice message should arrive.

---

## Test 4: /pronounce Command

**What it validates**: The `/pronounce` slash command triggers audio output.

1. Send: **`/pronounce Eichhörnchen`**
2. **Expected**: Bot sends a voice message with the pronunciation of "Eichhörnchen".
3. Try a longer phrase: **`/pronounce Ich lerne Deutsch`**
4. **Expected**: Voice message with natural German speech.

---

## Test 5: STT Fallback (Groq → faster-whisper)

**What it validates**: When Groq is unavailable, the local Whisper model takes over.

1. Temporarily set an invalid Groq API key in `config.json`:
   ```json
   "stt": {
     "provider": "groq_with_fallback",
     "groq": { "api_key": "invalid-key" },
     "whisper": { "model": "base" }
   }
   ```
2. Restart the bot.
3. Send a voice message saying **"Guten Morgen"**.
4. **Expected**: Transcription still succeeds (slower, using local Whisper).
5. **Check logs**: Look for a warning about the Groq provider failing, followed by
   a Whisper transcription attempt.
6. Restore your real Groq API key when done.

---

## Test 6: TTS Fallback (edge-tts → Piper)

**What it validates**: When edge-tts (cloud) is unavailable, Piper (local) takes over.

> **Requires**: `piper-tts` installed (`pip install piper-tts`) and the Thorsten
> model downloaded (`piper --model de_DE-thorsten-high --download-dir ~/.local/share/piper`).

1. Temporarily set an invalid voice name in `config.json` to force edge-tts to fail:
   ```json
   "tts": {
     "provider": "edge_with_fallback",
     "voice": "invalid-voice-to-force-failure",
     "piper": { "model": "de_DE-thorsten-high" }
   }
   ```
2. Restart the bot.
3. Send: **`/pronounce Schmetterling`**
4. **Expected**: Voice message still arrives, synthesised by Piper locally.
5. **Check logs**: Warning about edge-tts failure (bad voice), then Piper synthesis succeeds.
6. Restore your real voice name (`de-DE-ConradNeural`) when done.

---

## Automated Tests

Run the full automated audio test suite (no Telegram connection needed):

```bash
# All audio tests
pytest tests/test_audio_e2e.py -v

# Full test suite
pytest tests/
```
