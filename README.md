# E*TRADE Voice Assistant

A voice-driven E*TRADE portfolio reader for visually-impaired users on macOS.
Push a foot pedal, ask a question, hear the answer.

> "What's the price of Apple?"
> "How much is my Tesla worth?"
> "What's my account balance?"
> "Read my portfolio."

After a one-time install, **grandpa never has to click anything**. The
assistant runs as a macOS background service that auto-starts at login and
auto-restarts if it crashes. He just hears *"Welcome to your E-Trade voice
assistant"* and can press the pedal to ask questions.

## Install (one time, on grandpa's Mac)

```bash
git clone https://github.com/ferryrules/etrade_buddy.git
cd etrade_buddy
./install.sh
```

`install.sh` will:

1. Install Homebrew + portaudio (mic support)
2. Set up the Python venv and install dependencies
3. Create `etrade_python_client/config.ini` from the template and prompt you
   for your E*TRADE Consumer Key and Consumer Secret
   (get them at <https://developer.etrade.com>)
4. Print a reminder about the macOS Microphone + Input Monitoring permissions
   you'll need to grant the first time the assistant runs
5. Install a macOS LaunchAgent (`~/Library/LaunchAgents/`) that runs the
   assistant in the background, auto-starts at login, and auto-restarts on
   crash

When the script finishes, you should hear *"Welcome to your E-Trade voice
assistant"* within ~10 seconds.

### Daily flow (for grandpa)

There is no daily flow. He logs into the Mac, hears the welcome message, and
the pedal works.

Once a calendar day (E*TRADE expires access tokens at midnight ET), the
assistant has to do one OAuth login — Chrome opens automatically, someone
logs in to E*TRADE, clicks Accept, and the assistant **auto-detects the
verifier code from the page**. No human reading required. The token is then
cached in macOS Keychain and reused for the rest of the day. Crashes in-day
are silently restarted — he won't be re-prompted.

### One-time Chrome setting (for the auto-detect to work)

The verifier-code auto-detect uses macOS AppleScript to ask Chrome "what's
on the page?". Chrome blocks this by default. Enable it once per Mac:

  **Chrome menu bar → View → Developer → Allow JavaScript from Apple Events**

If you forget, the assistant gracefully falls back to the original spoken-code
flow ("read the code to me") on the next login.

## Maintenance commands (for you, not grandpa)

| Command              | What it does |
|----------------------|--------------|
| `./status.sh`        | Is it running? Shows PID, uptime, and last 10 log lines |
| `./logs.sh`          | Live-tail the latest session log (Ctrl-C to stop) |
| `./restart.sh`       | Bounce the LaunchAgent (use this after `git pull` or editing `config.ini`) |
| `./uninstall.sh`     | Remove the LaunchAgent so it stops auto-launching. Project files untouched. |
| `./setup_pedal.sh`   | Optional. Detects what key your USB foot pedal sends and (recommended) sets up Karabiner-Elements to remap it to F13. Only needed if your pedal doesn't already send F13. |
| `./test.sh`          | Run the assistant against fake data (no E*TRADE login). For debugging speech recognition. |

## Forgetting the cached OAuth token

If the assistant gets stuck refusing to authenticate, wipe the cached token:

```bash
.venv/bin/python etrade_python_client/voice_assistant.py --forget-auth
```

Then `./restart.sh` and the next launch will run the full browser-login flow.

## Architecture

```
~/Library/LaunchAgents/
  com.ferryrules.etrade-voice-assistant.plist   <- macOS auto-start
        |
        v   (runs at login, restarts on crash)
.venv/bin/python -u etrade_python_client/voice_assistant.py
        |
        +-- Speaks via macOS `say`
        +-- Listens for the foot pedal via pynput (default: F13)
        +-- Captures audio via SpeechRecognition + Google API
        +-- Talks to E*TRADE via rauth (OAuth1)
        +-- Caches OAuth token in macOS Keychain (service:
            com.ferryrules.etrade-voice-assistant)
        +-- Logs to etrade_python_client/logs/session_<timestamp>.log
        +-- Emails crash reports via macOS Mail to ferris@ferryrules.com
```

## Files in this repo

```
install.sh                      <- one-time installer
status.sh / restart.sh / logs.sh / uninstall.sh   <- maintenance
setup_pedal.sh                  <- optional pedal detection / Karabiner remap
test.sh                         <- offline test runner
requirements.txt
etrade_python_client/
    voice_assistant.py          <- the actual assistant
    test_voice.py               <- fake-data version of the assistant
    query_parser.py             <- speech-to-API-call parser
    config.example.ini          <- tracked template
    config.ini                  <- your real keys (gitignored)
    logs/                       <- per-session logs (gitignored)
```

## Security notes

- `etrade_python_client/config.ini` (which holds your Consumer Key and Secret)
  is gitignored. **Do not commit it.** The tracked `config.example.ini` is the
  template, and `install.sh` copies it on first run.
- The OAuth access token is stored in **macOS Keychain** (encrypted at rest,
  protected by the user's login password). It is API-scoped, expires daily at
  midnight ET, and cannot be used to change account passwords or move money out
  of the account.
- The assistant can read account balances, positions, and quotes. It does not
  have a code path for placing trades — it just opens the E*TRADE web UI in
  Chrome if grandpa says "I want to trade".
