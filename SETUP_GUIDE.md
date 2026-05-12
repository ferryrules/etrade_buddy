# Setting Up Grandpop's E*TRADE Voice Assistant

This guide will walk you through everything, step by step. Don't worry if you've never done anything like this before - just follow along and you'll be fine!

---

## What You'll Need Before Starting

- Grandpop's Mac computer (a MacBook or iMac - either works)
- The Mac needs to be connected to the internet (Wi-Fi or ethernet)
- Grandpop's E*TRADE account login (username and password)
- E*TRADE API keys (we'll get these together in Part 1)
- The iKKEGOL foot pedal (the USB one you ordered)
- About 30-45 minutes of time

---

## Part 1: Getting E*TRADE API Keys

The voice assistant needs special "API keys" to talk to E*TRADE. Think of these like a special password that lets our app read Grandpop's account info. **The app can only read data - it cannot make trades or move money.**

1. Open **Google Chrome** (if it's not installed, download it from google.com/chrome)

2. Go to this website: **https://developer.etrade.com**

3. Click **"Get Started"** or **"Sign Up"**

4. Log in using Grandpop's E*TRADE username and password

5. You'll need to create what's called a "sandbox key" and a "production key":
   - The **sandbox key** is for testing (it uses fake data)
   - The **production key** is the real one (it uses Grandpop's actual account)

6. Once you have the keys, you'll see two pieces of information:
   - **Consumer Key** - a long string of letters and numbers
   - **Consumer Secret** - another long string of letters and numbers

7. **Write these down or copy them somewhere safe.** The setup script will ask you for them.

> **Important:** These keys are like passwords. Don't share them with anyone or post them online.

---

## Part 2: Plug In the Foot Pedal

Take the iKKEGOL foot pedal out of the box and plug the USB cable into the Mac.

**If the Mac only has USB-C ports** (the small oval ones), you'll need a USB-A to USB-C adapter. These are cheap and available at any electronics store, or you may already have one.

**If a popup appears** saying "a new keyboard has been detected," just close it or click through it. The pedal works as a keyboard - that's expected.

### Why we remap the foot pedal (important!)

Most foot pedals come configured to send the **spacebar** key. This causes two problems:

- If someone presses the spacebar on the regular keyboard while the voice assistant is running, it will accidentally trigger the assistant
- If the foot pedal is pressed while another app is in front (like Chrome or TextEdit), it will type spaces into that app

To avoid this, the setup script will offer to remap the pedal to send **F13** instead - a key that doesn't exist on any Mac keyboard, so it can never interfere with anything. It does this using a free app called **Karabiner-Elements**.

The setup script handles most of this automatically. After it installs Karabiner-Elements, you'll need to do one manual step: open Karabiner-Elements and make sure the remapping rule only applies to the foot pedal device (not the regular keyboard). The setup script will explain exactly what to do.

---

## Part 3: Run the Setup (This Does Almost Everything!)

The setup will automatically install everything the app needs. It will walk you through each step and explain what's happening.

### Step 1: Open the EtradePythonClient folder

1. Open **Finder** (the smiley face icon in the dock at the bottom of the screen)
2. Click **Downloads** in the left sidebar
3. Double-click the **EtradePythonClient** folder to open it

### Step 2: Run the setup

Find the file called **Setup Voice Assistant** and double-click it. A Terminal window will open and the setup will begin.

> **If macOS shows a warning:** Depending on your macOS version, you'll see one of two warnings:
>
> **If it offers an "Open" option:** Right-click the file instead, click **"Open"**, then click **"Open"** again on the popup.
>
> **If it only offers "Delete" or "Done":** Click **"Done"** (NOT Delete!), then go to **System Settings > Privacy & Security**, scroll down, and click **"Open Anyway"** next to the blocked file message. Enter your password if asked, then click **"Open"** on the final popup.
>
> You only need to do this once per file - after that, double-clicking works normally.

> **Tip:** If the text in the window is too small, you can make it bigger. Go to the top menu: **Terminal > Settings > Profiles > Text** and change the font size.

### Step 3: Follow along

The setup script will:

1. **Install Homebrew** (a tool installer) - it might ask for the computer's password. When you type the password, you won't see any dots or stars on the screen - that's completely normal! Just type it and press Return. This step can take 5-10 minutes.

2. **Install PortAudio** (lets the app use the microphone) - takes about a minute.

3. **Set up the app's environment** - installs all the code the app needs. Takes a couple of minutes.

4. **Ask for your API keys** - it will ask you to type or paste the Consumer Key and Consumer Secret from Part 1. If you don't have them yet, you can say "no" and add them later.

5. **Detect the foot pedal** - it will ask you to press the pedal so it can figure out which key it sends. Just step on it when it tells you to.

6. **Remind you about permissions** - it will explain what to click when macOS asks for permission.

7. **Create shortcut scripts** - so starting the app later is super easy.

When it's done, you'll see **"Setup complete!"** and a cheat sheet.

> **If you see red text that says "ERROR":** Take a screenshot and send it to Ferris.

---

## Part 4: macOS Permissions

The first time you run the voice assistant, macOS will ask for two permissions. This is macOS being careful about which apps can use the microphone and keyboard - it's a good thing!

### Permission 1: Microphone

A popup will appear saying Terminal wants to access the microphone.
- Click **"OK"** or **"Allow"**

### Permission 2: Input Monitoring (for the foot pedal)

You need to turn this on yourself:

1. Click the **Apple menu** (the Apple logo in the top-left corner of the screen)
2. Click **System Settings**
3. In the left sidebar, click **Privacy & Security**
4. Click **Input Monitoring**
5. Find **Terminal** in the list and flip the switch to **ON**
6. Close System Settings

> **After changing permissions:** You need to **close Terminal and reopen it** for the changes to take effect. Close it by pressing **Command + Q** (hold Command, press Q), then open it again from Spotlight.

### If you accidentally clicked "Don't Allow" for the microphone:

1. Click the **Apple menu** (top-left corner)
2. Click **System Settings**
3. Click **Privacy & Security**
4. Click **Microphone**
5. Find **Terminal** and flip the switch to **ON**
6. Close System Settings and restart Terminal

---

## Part 5: Test It (No E*TRADE Login Needed)

Before connecting to the real E*TRADE account, let's make sure everything works with fake data.

### Step 1: Start the test

Go to the **EtradePythonClient** folder in Downloads and double-click **Test Voice Assistant**. A Terminal window will open and the app will start talking.

### Step 2: What you should hear

The computer will start talking! It will say:
- "Voice assistant test mode. Using fake portfolio data."
- "Press space to talk. Press control C to quit."
- "Adjusting for background noise." (wait a moment)
- "Ready! Press your button to ask a question."

### Step 3: Try it out

1. **Step on the foot pedal** - you should hear a beep sound
2. **Say clearly:** "What's the price of Apple?"
3. **Wait** - the computer should say something like: "APPLE INC is at $198.50, up $1.51 or 0.77 percent."

### Step 4: Try more questions

Press the pedal each time before speaking:

- "How much is Tesla worth?"
- "Tell me about Apple" (this reads a full report with all his favorite info)
- "How many shares of Rocket Lab?"
- "What's my balance?"
- "Read my portfolio"
- "Help"

### Step 5: If something isn't working

**If you don't hear any sound:**
- Make sure the Mac's volume is turned up (press the volume up key on the keyboard)
- Check that the sound output is set to the speakers (click the speaker icon in the top menu bar)

**If it says "I couldn't hear you clearly":**
- Speak louder or move closer to the computer's microphone
- You can make it more sensitive by running the test like this instead:
  ```
  cd ~/Downloads/EtradePythonClient
  source .venv/bin/activate
  cd etrade_python_client
  python3 -u test_voice.py --button space --volume 800
  ```

**If pressing the foot pedal does nothing:**
- Make sure Terminal has Input Monitoring permission (Part 4)
- Try unplugging and replugging the pedal
- Close Terminal, reopen it, and try again

**If it says "Speech recognition error":**
- Make sure the Mac is connected to the internet

### Step 6: Stop the test

Press **Control + C** (hold Control, press C) to stop the program.

---

## Part 6: Run It For Real

Once the test works, you're ready to connect to Grandpop's real E*TRADE account!

### Step 1: Start the voice assistant

Go to the **EtradePythonClient** folder in Downloads and double-click **Start Voice Assistant**.

### Step 2: Log in to E*TRADE

The app will say "Starting authentication. I'll open a browser window for you to log in."

1. A Chrome window will open with the E*TRADE login page
2. Log in with Grandpop's E*TRADE username and password
3. After logging in, E*TRADE will show a **verification code** on the screen
4. The app will ask you to say the code
5. Read the code out loud clearly (or type it into Terminal if voice doesn't work)
6. The app will say "Authentication successful"

> **Note:** You'll need to do this login step once each day Grandpop wants to use the app. The login lasts for the trading day.

### Step 3: Using it

Once logged in, the app will automatically:
- Find Grandpop's brokerage account
- Load all his stock positions
- Say "Ready! Press your button to ask a question."

Now Grandpop can use it on his own:

1. **Press the foot pedal** (hear a beep)
2. **Ask a question** in plain English
3. **Listen** to the answer
4. **Repeat!**

### Things he can ask (press the pedal before each one):

**About specific stocks:**
- "What's the price of Apple?"
- "How much is my Tesla worth?"
- "Total gain on Microsoft"
- "Day's gain on Apple"
- "Cost per share of Tesla"
- "How many shares of Apple?"
- "Dividend on Microsoft"
- "Annual yield on Apple"
- "Expense ratio on [fund name]"

**Full report (reads all his favorites for one stock):**
- "Tell me about Apple"
- "Report on Tesla"

**About the whole account:**
- "What's my balance?"
- "Read my portfolio" (reads every stock)

**Utility commands:**
- "Refresh" (reloads the latest data)
- "Open E-Trade" (opens the E*TRADE website in Chrome if he wants to make a trade)
- "Help" (lists what he can ask)

---

## Daily Startup Cheat Sheet

Once everything is set up, here's the short version for starting it each day. **Print this out and tape it near the computer!**

```
DAILY STARTUP
=============
1. Open the EtradePythonClient folder (in Downloads)
2. Double-click "Start Voice Assistant"
3. When Chrome opens, log in to E*TRADE
4. Read the verification code out loud
5. Wait for "Ready!" - then use the foot pedal!
6. When done, press Control+C in the Terminal window
```

---

## Troubleshooting

### "I changed something and now it won't start"

Close Terminal, reopen it, and try the commands from Part 6 again. If it still doesn't work, take a screenshot of the error and send it to Ferris.

### The app says "I couldn't find any information for [stock]"

The stock might not be recognized by name. Try using the ticker symbol instead (like "AAPL" for Apple or "TSLA" for Tesla). The app automatically learns the names of all stocks in Grandpop's portfolio, but stocks not in his portfolio need to be asked about by their ticker symbol.

### The app stopped responding

Press **Control + C** to stop it, then start it again using `./start.sh`.

### The foot pedal stopped working

1. Unplug it and plug it back in
2. Restart Terminal
3. Try again

### The foot pedal is typing spaces (or other characters) in other apps

This means the pedal hasn't been remapped to F13 yet. Run the setup again (double-click **Setup Voice Assistant**) and say "yes" when it asks about remapping, or install **Karabiner-Elements** manually and remap the pedal to F13. See Part 2 of this guide for details.

### The spacebar on the keyboard triggers the voice assistant

Same fix - remap the foot pedal to F13 so the assistant only listens for F13, not the spacebar. See the section above.

### "Something about permissions"

Go to **System Settings > Privacy & Security** and make sure Terminal has both **Microphone** and **Input Monitoring** turned ON. Then restart Terminal.

### Chrome says the E*TRADE login is expired

This is normal - the login expires each day. Just stop the app (Control+C) and start it again. It will open a new login page.

### The volume is too loud or too quiet

You can change the Mac's volume with the volume keys on the keyboard. The app uses the normal system volume for speaking.

### It keeps hearing background noise

If people are talking nearby and it's picking up their voices, you can make the app less sensitive. Edit the `start.sh` file and change the last line to:

```
python3 -u voice_assistant.py --button space --volume 2500
```

The higher the number, the louder you need to speak (but background noise gets filtered out better). The default is 1500. Try values between 800 (very sensitive) and 3000 (only picks up close, loud speech).

---

## Logs & Transcripts

Every time the voice assistant runs, it saves a complete record of the session in a log file. This includes:

- **Everything Grandpop asked** and **everything the app said back** (the full transcript)
- Any errors that happened, with technical details for debugging
- Timestamps for every event

The log files are saved in:

```
~/Downloads/EtradePythonClient/etrade_python_client/logs/
```

Each file is named like `session_20260512_143022.log` (the date and time the session started). You can open these in TextEdit to read them.

### Error Email Alerts

If error alerts were set up during installation (Step 7 of the setup script), the app will automatically email Ferris when something goes wrong. The email includes the error details and the last 200 lines of the log file.

**Important:** For email alerts to work, the Mac's **Mail app** needs to be signed into an email account. If Mail isn't set up, the alerts won't send - but the app will still work fine and save everything to the log files.

If the app hits 5 errors in a row without a successful command in between, it will safely shut itself down and send a critical alert email. This prevents it from getting stuck in a loop. Just restart it with `./start.sh` if this happens.

---

## Getting Help

If something goes wrong that isn't covered here, contact Ferris! You can help him by:

1. **Check the log files** in `~/Downloads/EtradePythonClient/etrade_python_client/logs/` - the most recent file has the details
2. **Take a screenshot** of any error messages on screen
3. Send both to Ferris - the log file is especially helpful for figuring out what went wrong
