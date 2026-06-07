# Custom Wake Words for Porcupine

Place your Picovoice Porcupine `.ppn` model files in this directory.

## How to create custom wake words

1. **Sign up** for a free Picovoice account:
   https://console.picovoice.ai/

2. **Create your wake words** in the console:
   - Go to "Wake Word" → "Create Wake Word"
   - Type your phrase (e.g. "hey alien", "hey ailien")
   - Select **Linux** as the platform
   - Download the generated `.ppn` file

3. **Place the `.ppn` files** in this directory:
   ```
   wake_words/
   ├── README.md
   ├── hey_alien.ppn      # ← your downloaded file
   └── hey_ailien.ppn     # ← your downloaded file
   ```

4. **Configure** in `.env` (project root):
   ```env
   PICOVOICE_ACCESS_KEY=your_access_key_from_console
   PICOVOICE_KEYWORD_PATHS=wake_words/hey_alien.ppn,wake_words/hey_ailien.ppn
   PICOVOICE_SENSITIVITIES=0.5,0.7
   ```

   > `PICOVOICE_SENSITIVITIES` is optional (defaults to 0.5 per keyword).
   > Higher = easier to trigger but more false positives (0.0–1.0).

5. **Restart the AI** — it will auto-detect Porcupine and use your custom wake words.

## Verify it's working

Run the AI in wake word mode and look for this log line:

```
Using Porcupine detector (custom wake words)
```

If you see `Using openWakeWord detector` instead, Porcupine isn't configured yet.

## Free tier limits

- Up to **2 custom wake words** on the free plan
- One Picovoice account per developer
- Model files run 100% offline — no internet needed after setup
