"""
Voice-driven E*TRADE portfolio reader for visually impaired users.

Usage:
    python voice_assistant.py [--sandbox] [--button KEY] [--volume THRESHOLD]
                              [--alert-email EMAIL] [--fallback-button KEY]

Press a physical button (default: spacebar) to talk, then ask your question.
A USB arcade button or foot pedal works great — plug it in and configure it
to send the spacebar key.

Examples after pressing the button:
    "What's the price of Apple?"
    "How much is my Tesla worth?"
    "Tell me about Microsoft"
    "What's my account balance?"
    "Read my portfolio"
"""

import argparse
import audioop
import configparser
import json
import logging
import os
import smtplib
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from logging.handlers import RotatingFileHandler

import speech_recognition as sr
from pynput import keyboard
from rauth import OAuth1Service

from query_parser import parse_query, register_portfolio_stocks, FIELD_HELP

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(__file__), "config.ini"))

# ---------------------------------------------------------------------------
# Logging — a single combined log file for transcript + errors + debug
# ---------------------------------------------------------------------------
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logger = logging.getLogger("voice_assistant")
logger.setLevel(logging.DEBUG)

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("  [%(levelname)s] %(message)s"))
console_handler.setLevel(logging.WARNING)
logger.addHandler(console_handler)

# Separate transcript logger — human-readable conversation history
transcript_logger = logging.getLogger("transcript")
transcript_logger.setLevel(logging.INFO)
transcript_handler = logging.FileHandler(LOG_FILE)
transcript_handler.setFormatter(logging.Formatter(
    "%(asctime)s | TRANSCRIPT | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
transcript_logger.addHandler(transcript_handler)

logger.info("Session started. Log file: %s", LOG_FILE)


# ---------------------------------------------------------------------------
# Email alerts
# ---------------------------------------------------------------------------

def send_error_email(alert_email, error_summary, log_file_path):
    """Send an error alert email with the log file contents attached."""
    if not alert_email:
        return

    try:
        log_tail = ""
        try:
            with open(log_file_path, "r") as f:
                lines = f.readlines()
                log_tail = "".join(lines[-200:])
        except Exception:
            log_tail = "(could not read log file)"

        subject = f"E*TRADE Voice Assistant Error — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        body = f"""The E*TRADE Voice Assistant hit an error and recovered.

ERROR SUMMARY:
{error_summary}

LAST 200 LOG LINES:
{log_tail}

---
Log file location on Grandpop's Mac: {log_file_path}
"""
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["To"] = alert_email
        msg["From"] = alert_email
        msg.attach(MIMEText(body, "plain"))

        # Use macOS built-in mail command as a simple fallback
        result = subprocess.run(
            ["osascript", "-e",
             f'tell application "Mail"\n'
             f'  set newMessage to make new outgoing message with properties '
             f'{{subject:"{subject}", visible:false}}\n'
             f'  tell newMessage\n'
             f'    make new to recipient at end of to recipients '
             f'with properties {{address:"{alert_email}"}}\n'
             f'    set content to "{body[:5000]}"\n'
             f'    send\n'
             f'  end tell\n'
             f'end tell'],
            capture_output=True, text=True, timeout=30
        )

        if result.returncode != 0:
            # Fallback: try the mail command line tool
            process = subprocess.Popen(
                ["mail", "-s", subject, alert_email],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            process.communicate(input=body.encode(), timeout=30)

        logger.info("Error alert email sent to %s", alert_email)

    except Exception as email_err:
        logger.error("Failed to send error email: %s", email_err)


# ---------------------------------------------------------------------------
# Token cache (macOS Keychain) — lets us skip the verifier-code dance until
# the token actually expires (E*TRADE expires access tokens at midnight ET
# and after 2 hours of inactivity, but inactivity can be silently renewed).
# ---------------------------------------------------------------------------

class TokenStore:
    """
    Stores the E*TRADE OAuth access token + secret in macOS Keychain.

    We use the `security` command rather than the `keyring` Python package so
    we don't add a new dependency. The token is encrypted by macOS, tied to
    grandpa's login keychain, and never lives on disk in plaintext.

    Service / account names are constants so any future tooling (e.g. a
    "reset-auth" script) can find / delete the entry.
    """

    SERVICE_NAME = "com.ferryrules.etrade-voice-assistant"
    ACCOUNT_NAME = "etrade_oauth_token"

    @classmethod
    def save(cls, access_token, access_token_secret):
        """Persist the token pair. Overwrites any existing entry."""
        payload = json.dumps({
            "access_token": access_token,
            "access_token_secret": access_token_secret,
            "saved_at": datetime.now().isoformat(),
        })
        try:
            subprocess.run(
                [
                    "security", "add-generic-password",
                    "-U",
                    "-s", cls.SERVICE_NAME,
                    "-a", cls.ACCOUNT_NAME,
                    "-D", "E*TRADE OAuth token (cached by voice assistant)",
                    "-w", payload,
                ],
                check=True, capture_output=True, text=True,
            )
            logger.info("Saved E*TRADE OAuth token to macOS Keychain")
        except subprocess.CalledProcessError as e:
            logger.error("Failed to save token to Keychain: %s", e.stderr or e)

    @classmethod
    def load(cls):
        """Return (access_token, access_token_secret) or (None, None) if not stored."""
        try:
            result = subprocess.run(
                [
                    "security", "find-generic-password",
                    "-s", cls.SERVICE_NAME,
                    "-a", cls.ACCOUNT_NAME,
                    "-w",
                ],
                check=True, capture_output=True, text=True,
            )
            payload = json.loads(result.stdout.strip())
            token = payload.get("access_token")
            secret = payload.get("access_token_secret")
            if token and secret:
                logger.info(
                    "Loaded cached E*TRADE OAuth token from Keychain (saved %s)",
                    payload.get("saved_at", "unknown"),
                )
                return token, secret
        except subprocess.CalledProcessError:
            logger.info("No cached E*TRADE OAuth token found in Keychain")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Cached token entry is corrupt: %s. Clearing it.", e)
            cls.clear()
        return None, None

    @classmethod
    def clear(cls):
        """Delete the cached token entry. Safe to call when nothing is stored."""
        result = subprocess.run(
            [
                "security", "delete-generic-password",
                "-s", cls.SERVICE_NAME,
                "-a", cls.ACCOUNT_NAME,
            ],
            check=False, capture_output=True, text=True,
        )
        if result.returncode == 0:
            logger.info("Cleared cached E*TRADE OAuth token from Keychain")


# ---------------------------------------------------------------------------
# Speech helpers (with transcript logging)
# ---------------------------------------------------------------------------

def speak(text):
    """Speak text aloud using macOS say command and log to transcript."""
    print(f"  🔊 {text}")
    transcript_logger.info("ASSISTANT: %s", text)
    subprocess.run(["say", "-r", "175", text], check=False)


def beep():
    """Play a short beep to indicate listening."""
    subprocess.run(["afplay", "/System/Library/Sounds/Tink.aiff"], check=False)


class ETradeVoiceAssistant:
    BUTTON_KEYS = {
        "space": keyboard.Key.space,
        "enter": keyboard.Key.enter,
        "shift": keyboard.Key.shift,
        "shift_r": keyboard.Key.shift_r,
        "f5": keyboard.Key.f5,
        "f12": keyboard.Key.f12,
        "f13": keyboard.Key.f13,
        "f14": keyboard.Key.f14,
        "f15": keyboard.Key.f15,
        "f16": keyboard.Key.f16,
        "f17": keyboard.Key.f17,
        "f18": keyboard.Key.f18,
        "f19": keyboard.Key.f19,
        "f20": keyboard.Key.f20,
    }

    MAX_CONSECUTIVE_ERRORS = 5

    def __init__(self, sandbox=False, button_key="space", volume_threshold=1500,
                 alert_email=None, fallback_button=None):
        self.sandbox = sandbox
        self.base_url = config["DEFAULT"]["SANDBOX_BASE_URL"] if sandbox else config["DEFAULT"]["PROD_BASE_URL"]
        self.session = None
        self.accounts = []
        self.account = None
        self.portfolio_cache = {}
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = False
        self.volume_threshold = volume_threshold
        self.running = True
        self.button_pressed = threading.Event()
        self._button_key_name = button_key
        self._button_key = self.BUTTON_KEYS.get(button_key, keyboard.Key.space)
        self._fallback_key_name = fallback_button
        self._fallback_key = self.BUTTON_KEYS.get(fallback_button) if fallback_button else None
        self.alert_email = alert_email
        self._consecutive_errors = 0

    def authenticate(self):
        """
        Establish an authenticated E*TRADE OAuth1 session.

        Strategy:
          1. Build the OAuth1Service from configured consumer key / secret.
          2. Try to resume a previously saved access token from macOS Keychain
             (calling /oauth/renew_access_token to make sure it's still valid).
          3. If no cached token exists or the renew fails (e.g. it's past
             midnight ET and the token has expired), fall back to the full
             interactive flow with the verifier code, then save the fresh
             token for tomorrow.
        """
        consumer_key = config["DEFAULT"].get("CONSUMER_KEY", "").strip()
        consumer_secret = config["DEFAULT"].get("CONSUMER_SECRET", "").strip()

        if (not consumer_key or not consumer_secret
                or "PLEASE_ENTER" in consumer_key
                or "PLEASE_ENTER" in consumer_secret):
            speak(
                "Your E-Trade API keys are not set up yet. "
                "Please run the Setup Voice Assistant script and enter your "
                "Consumer Key and Consumer Secret from developer dot E-Trade dot com."
            )
            logger.error(
                "Authentication aborted: config.ini still contains placeholder API keys"
            )
            raise RuntimeError("E*TRADE API keys are not configured in config.ini")

        self._etrade = OAuth1Service(
            name="etrade",
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            request_token_url="https://api.etrade.com/oauth/request_token",
            access_token_url="https://api.etrade.com/oauth/access_token",
            authorize_url="https://us.etrade.com/e/t/etws/authorize?key={}&token={}",
            base_url="https://api.etrade.com",
        )

        if self._try_resume_saved_session():
            speak("Welcome back. I'm already logged in to E-Trade from earlier.")
            logger.info("Resumed E*TRADE session from cached token (no browser login needed)")
            return

        self._interactive_authenticate()

    def _try_resume_saved_session(self):
        """
        Attempt to reuse a token saved in macOS Keychain. Returns True if we
        end up with a working self.session, False otherwise (in which case the
        caller should do the full interactive flow).
        """
        access_token, access_token_secret = TokenStore.load()
        if not access_token or not access_token_secret:
            return False

        try:
            session = self._etrade.get_session(
                (access_token, access_token_secret)
            )
            renew_url = "https://api.etrade.com/oauth/renew_access_token"
            response = session.get(renew_url, header_auth=True, timeout=15)
        except Exception as e:
            logger.warning("Token renew attempt raised exception: %s", e)
            return False

        if response.status_code == 200:
            self.session = session
            return True

        logger.info(
            "Cached token is no longer valid (HTTP %d on renew). "
            "Falling back to interactive login.",
            response.status_code,
        )
        TokenStore.clear()
        return False

    def _interactive_authenticate(self):
        """Full OAuth1 flow with browser + spoken verifier code."""
        speak("Starting authentication. I'll open a browser window for you to log in.")
        speak("After logging in, you'll see a verification code on the screen.")
        speak("Someone nearby will need to read it to you, or use your screen reader to find it.")

        request_token, request_token_secret = self._safe_get_request_token(self._etrade)

        authorize_url = self._etrade.authorize_url.format(
            self._etrade.consumer_key, request_token
        )
        subprocess.run(["open", "-a", "Google Chrome", authorize_url], check=False)

        speak("Browser opened. Please log in and get the verification code.")

        code = self._listen_for_code()
        if not code:
            speak("I didn't catch a verification code. Let me try again.")
            code = self._listen_for_code()

        if not code:
            speak("Still couldn't get the code. You can type it instead.")
            code = input("Enter verification code: ").strip()

        self.session, access_token, access_token_secret = self._safe_get_auth_session(
            self._etrade, request_token, request_token_secret, code
        )
        TokenStore.save(access_token, access_token_secret)
        speak("Authentication successful. I'll remember this so you don't need a code next time.")
        logger.info("OAuth authentication completed (token cached for reuse)")

    def _safe_get_request_token(self, etrade):
        """
        Wrap rauth's get_request_token so we can:
          - Check the HTTP status code first (rauth doesn't)
          - Decode the response as UTF-8 (rauth uses ASCII via parse_qsl(bytes))
        Returns (request_token, request_token_secret).
        """
        response = etrade.get_raw_request_token(
            params={"oauth_callback": "oob"}
        )
        return self._parse_oauth_response(response, "request token")

    def _safe_get_auth_session(self, etrade, request_token, request_token_secret, code):
        """
        Wrap rauth's get_auth_session with the same protections as
        _safe_get_request_token, then build a real OAuth1Session.

        Returns (session, access_token, access_token_secret) so the caller
        can persist the raw token pair for later reuse.
        """
        response = etrade.get_raw_access_token(
            request_token,
            request_token_secret,
            params={"oauth_verifier": code},
        )
        access_token, access_token_secret = self._parse_oauth_response(
            response, "access token"
        )
        session = etrade.get_session((access_token, access_token_secret))
        return session, access_token, access_token_secret

    @staticmethod
    def _parse_oauth_response(response, what):
        """
        Validate the HTTP response from E*TRADE's OAuth endpoint and parse the
        token pair out of it. Provides clear, voice-friendly error messages
        instead of the cryptic 'ascii codec' error from rauth's parse_utf8_qsl
        when E*TRADE returns an HTML error page (e.g. for bad credentials).
        """
        from urllib.parse import parse_qsl

        if response.status_code != 200:
            try:
                body = response.content.decode("utf-8", errors="replace")
            except Exception:
                body = "(unreadable response body)"
            logger.error(
                "E*TRADE OAuth %s request failed: HTTP %d. Body: %s",
                what, response.status_code, body[:500],
            )
            if response.status_code in (401, 403):
                speak(
                    "E-Trade rejected the request. "
                    "Your Consumer Key or Consumer Secret may be wrong, "
                    "or your developer app may need to be re-approved."
                )
            else:
                speak(
                    f"E-Trade returned an error while getting the {what}. "
                    f"H-T-T-P status {response.status_code}."
                )
            raise RuntimeError(
                f"E*TRADE OAuth {what} request failed with HTTP "
                f"{response.status_code}"
            )

        try:
            text = response.content.decode("utf-8")
        except UnicodeDecodeError:
            text = response.content.decode("latin-1")

        pairs = dict(parse_qsl(text))
        token = pairs.get("oauth_token")
        secret = pairs.get("oauth_token_secret")
        if not token or not secret:
            logger.error(
                "E*TRADE OAuth %s response did not contain expected fields. "
                "Body: %s", what, text[:500],
            )
            speak(
                f"E-Trade returned an unexpected response while getting the {what}."
            )
            raise RuntimeError(
                f"E*TRADE OAuth {what} response missing oauth_token / "
                f"oauth_token_secret"
            )
        return token, secret

    def _listen_for_code(self):
        """Listen for a spoken verification code (alphanumeric)."""
        speak("Please say your verification code now.")
        beep()
        with self.microphone as source:
            try:
                audio = self.recognizer.listen(source, timeout=15, phrase_time_limit=10)
                text = self.recognizer.recognize_google(audio).strip()
                clean = text.replace(" ", "").upper()
                speak(f"I heard: {clean}. Is that correct? Say yes or no.")
                beep()
                audio = self.recognizer.listen(source, timeout=8, phrase_time_limit=5)
                confirm = self.recognizer.recognize_google(audio).strip().lower()
                if "yes" in confirm or "yeah" in confirm or "correct" in confirm:
                    return clean
                return None
            except (sr.UnknownValueError, sr.WaitTimeoutError):
                return None

    def load_accounts(self):
        """Fetch account list and select a brokerage account."""
        url = self.base_url + "/v1/accounts/list.json"
        response = self.session.get(url, header_auth=True)

        if response.status_code != 200:
            speak("I couldn't load your accounts. Please try again later.")
            logger.error("Account list failed: %s", response.text)
            return False

        data = response.json()
        try:
            accounts = data["AccountListResponse"]["Accounts"]["Account"]
        except (KeyError, TypeError):
            speak("No accounts found.")
            return False

        self.accounts = [a for a in accounts if a.get("accountStatus") != "CLOSED"]

        brokerage = [a for a in self.accounts if a.get("institutionType") == "BROKERAGE"]
        candidates = brokerage if brokerage else self.accounts

        if not candidates:
            speak("No active accounts found.")
            return False

        if len(candidates) == 1:
            self.account = candidates[0]
            name = self.account.get("accountDesc", "your account").strip()
            speak(f"Connected to {name}.")
        else:
            self.account = self._choose_account(candidates)

        logger.info("Selected account: %s", self.account.get("accountIdKey"))
        return True

    def _choose_account(self, candidates):
        """Let the user pick an account by voice when multiple are available."""
        speak(f"I found {len(candidates)} accounts.")
        for i, acct in enumerate(candidates, 1):
            desc = acct.get("accountDesc", "").strip() or f"Account {i}"
            speak(f"Account {i}: {desc}.")

        speak("Which account would you like to use? Say the number.")
        beep()

        with self.microphone as source:
            try:
                audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=5)
                text = self.recognizer.recognize_google(audio).strip().lower()
                logger.info("Account selection heard: %s", text)
                transcript_logger.info("USER: %s", text)

                word_to_num = {
                    "one": 1, "1": 1, "first": 1, "won": 1,
                    "two": 2, "2": 2, "second": 2, "to": 2, "too": 2,
                    "three": 3, "3": 3, "third": 3,
                    "four": 4, "4": 4, "fourth": 4, "for": 4,
                    "five": 5, "5": 5, "fifth": 5,
                }

                choice = None
                for word in text.split():
                    if word in word_to_num:
                        choice = word_to_num[word]
                        break

                if choice and 1 <= choice <= len(candidates):
                    selected = candidates[choice - 1]
                    name = selected.get("accountDesc", "").strip() or f"Account {choice}"
                    speak(f"Connected to {name}.")
                    return selected

            except (sr.UnknownValueError, sr.WaitTimeoutError, sr.RequestError):
                pass

        speak(f"I didn't catch that. Using the first account: {candidates[0].get('accountDesc', '').strip()}.")
        return candidates[0]

    def refresh_portfolio(self):
        """Fetch portfolio positions and cache them keyed by symbol and description."""
        url = self.base_url + "/v1/accounts/" + self.account["accountIdKey"] + "/portfolio.json"
        response = self.session.get(url, header_auth=True)

        if response.status_code == 204:
            speak("Your portfolio is empty.")
            self.portfolio_cache = {}
            return

        if response.status_code != 200:
            speak("I couldn't load your portfolio right now.")
            logger.error("Portfolio fetch failed: %s", response.text)
            return

        data = response.json()
        self.portfolio_cache = {}

        try:
            for acct_portfolio in data["PortfolioResponse"]["AccountPortfolio"]:
                for position in acct_portfolio.get("Position", []):
                    symbol = position.get("Product", {}).get("symbol", "").upper()
                    desc = position.get("symbolDescription", "").upper()
                    if symbol:
                        self.portfolio_cache[symbol] = position
                    if desc:
                        self.portfolio_cache[desc] = position
        except (KeyError, TypeError) as e:
            logger.error("Error parsing portfolio: %s", e)

        count = len(set(id(v) for v in self.portfolio_cache.values()))
        added = register_portfolio_stocks(self.portfolio_cache)
        speak(f"Loaded {count} positions from your portfolio.")
        if added:
            logger.info("Registered %d new stock names from portfolio", added)
        logger.info("Portfolio loaded: %d positions", count)

    def get_balance(self):
        """Fetch account balance."""
        url = self.base_url + "/v1/accounts/" + self.account["accountIdKey"] + "/balance.json"
        params = {"instType": self.account["institutionType"], "realTimeNAV": "true"}
        headers = {"consumerkey": config["DEFAULT"]["CONSUMER_KEY"]}
        response = self.session.get(url, header_auth=True, params=params, headers=headers)

        if response.status_code != 200:
            return None
        return response.json().get("BalanceResponse")

    def get_market_quote(self, symbol):
        """Fetch a live market quote for a symbol not in portfolio."""
        url = self.base_url + "/v1/market/quote/" + symbol + ".json"
        response = self.session.get(url, header_auth=True)

        if response.status_code != 200:
            return None

        data = response.json()
        try:
            return data["QuoteResponse"]["QuoteData"][0]
        except (KeyError, IndexError, TypeError):
            return None

    def find_position(self, symbol_query):
        """Find a position by symbol or partial description match."""
        query = symbol_query.upper().strip()

        if query in self.portfolio_cache:
            return self.portfolio_cache[query]

        for key, position in self.portfolio_cache.items():
            if query in key:
                return position

        return None

    def answer_query(self, spoken_text):
        """Parse a spoken query and speak the answer. Wrapped in error recovery."""
        try:
            self._answer_query_inner(spoken_text)
        except Exception as e:
            self._handle_error(e, context=f"Answering query '{spoken_text}'")

    def _answer_query_inner(self, spoken_text):
        """Parse a spoken query and speak the answer."""
        text = spoken_text.lower().strip()
        logger.info("Processing query: %s", text)

        if "balance" in text or "account value" in text or "how much do i have" in text:
            self._speak_balance()
            return

        if "portfolio" in text and ("read" in text or "list" in text or "all" in text or "summary" in text):
            self._speak_portfolio_summary()
            return

        if "refresh" in text or "reload" in text or "update" in text:
            speak("Refreshing your portfolio.")
            self.refresh_portfolio()
            return

        if "switch account" in text or "change account" in text or "other account" in text:
            brokerage = [a for a in self.accounts if a.get("institutionType") == "BROKERAGE"]
            candidates = brokerage if brokerage else self.accounts
            if len(candidates) <= 1:
                speak("You only have one account.")
                return
            self.account = self._choose_account(candidates)
            speak("Reloading portfolio for the new account.")
            self.refresh_portfolio()
            return

        if any(phrase in text for phrase in (
            "open etrade", "open e-trade", "open my account",
            "go to etrade", "go to e-trade",
            "i want to trade", "i want to buy", "i want to sell",
            "make a trade", "place a trade", "place an order",
            "buy stock", "sell stock", "buy shares", "sell shares",
        )):
            speak("Opening your E-Trade account in Chrome. Someone nearby can help you place a trade from there.")
            subprocess.run(["open", "-a", "Google Chrome", "https://us.etrade.com/etx/hw/accountshome"], check=False)
            return

        if "help" in text or "what can i ask" in text or "what can you do" in text:
            self._speak_help()
            return

        parsed = parse_query(text)
        if not parsed:
            speak("I didn't understand that. Try saying something like: what's the price of Apple?")
            return

        symbol, field = parsed
        position = self.find_position(symbol)

        if not position:
            speak(f"I don't see {symbol} in your portfolio. Let me check the market.")
            quote = self.get_market_quote(symbol)
            if quote:
                self._speak_market_quote(quote, field, symbol)
            else:
                speak(f"I couldn't find any information for {symbol}.")
            return

        if field == "summary":
            self._speak_full_report(position)
            return

        if field in ("expense_ratio", "gross_expense_ratio", "annual_yield"):
            self._speak_quote_field(position, field)
            return

        self._speak_position_field(position, field)

    def _speak_balance(self):
        balance = self.get_balance()
        if not balance:
            speak("I couldn't get your account balance.")
            return

        parts = []
        desc = balance.get("accountDescription", "")
        if desc:
            parts.append(f"Account: {desc}")

        computed = balance.get("Computed", {})
        rtv = computed.get("RealTimeValues", {})
        total_val = rtv.get("totalAccountValue")
        if total_val is not None:
            parts.append(f"Total account value: ${total_val:,.2f}")

        margin = computed.get("marginBuyingPower")
        if margin is not None:
            parts.append(f"Margin buying power: ${margin:,.2f}")

        cash = computed.get("cashBuyingPower")
        if cash is not None:
            parts.append(f"Cash buying power: ${cash:,.2f}")

        speak(". ".join(parts) if parts else "No balance information available.")

    def _speak_portfolio_summary(self):
        if not self.portfolio_cache:
            speak("Your portfolio is empty.")
            return

        seen = set()
        positions = []
        for pos in self.portfolio_cache.values():
            pid = id(pos)
            if pid in seen:
                continue
            seen.add(pid)
            positions.append(pos)

        speak(f"You have {len(positions)} positions.")
        for pos in positions:
            symbol = pos.get("Product", {}).get("symbol", "unknown")
            desc = pos.get("symbolDescription", symbol)
            qty = pos.get("quantity", 0)
            market_val = pos.get("marketValue")
            last_trade = None
            quick = pos.get("Quick", pos.get("quick", {}))
            if quick:
                last_trade = quick.get("lastTrade")

            line = f"{desc}: {qty:.0f} shares"
            if last_trade is not None:
                line += f" at ${last_trade:,.2f}"
            if market_val is not None:
                line += f", worth ${market_val:,.2f}"
            speak(line)

    def _speak_full_report(self, position):
        """Read all of grandpop's favorite fields for a position."""
        symbol = position.get("Product", {}).get("symbol", "")
        desc = position.get("symbolDescription", symbol)
        quick = position.get("Quick", position.get("quick", {}))

        speak(f"Here's the full report for {desc}.")

        lt = quick.get("lastTrade") if quick else None
        if lt is not None:
            speak(f"Last price: ${lt:,.2f}.")

        qty = position.get("quantity")
        if qty is not None:
            speak(f"Quantity: {qty:.0f} shares.")

        dg = position.get("daysGain")
        if dg is not None:
            direction = "up" if dg >= 0 else "down"
            speak(f"Day's gain: {direction} ${abs(dg):,.2f}.")

        cps = position.get("costPerShare")
        if cps is not None:
            speak(f"Cost per share: ${cps:,.2f}.")

        mv = position.get("marketValue")
        if mv is not None:
            speak(f"Value: ${mv:,.2f}.")

        tg = position.get("totalGain")
        if tg is not None:
            direction = "up" if tg >= 0 else "down"
            speak(f"Total gain: {direction} ${abs(tg):,.2f}.")

        quote = self.get_market_quote(symbol)
        if quote:
            mf = quote.get("MutualFund", {})
            all_data = quote.get("All", {})
            ner = mf.get("netExpenseRatio")
            if ner is not None:
                speak(f"Net expense ratio: {ner:.2f} percent.")
            else:
                speak("Net expense ratio: not available for this security.")

            dividend = all_data.get("dividend")
            if dividend is not None:
                speak(f"Dividend distribution: ${dividend:,.4f}.")
            else:
                fundamental = position.get("Fundamental", position.get("fundamental", {}))
                div_val = fundamental.get("dividend")
                if div_val is not None:
                    speak(f"Dividend: ${div_val:,.4f}.")

            annual_yield = all_data.get("yield") or all_data.get("divYield")
            if annual_yield is not None:
                speak(f"Annual yield: {annual_yield:.2f} percent.")
            else:
                speak("Annual yield: not available.")
        else:
            fundamental = position.get("Fundamental", position.get("fundamental", {}))
            div_val = fundamental.get("dividend")
            if div_val is not None:
                speak(f"Dividend: ${div_val:,.4f}.")
            div_yield = fundamental.get("divYield")
            if div_yield is not None:
                speak(f"Annual yield: {div_yield:.2f} percent.")
            speak("Couldn't fetch market quote for expense ratio.")

        speak(f"End of report for {desc}.")

    def _speak_quote_field(self, position, field):
        """Fetch expense ratio or annual yield from the market quote endpoint."""
        symbol = position.get("Product", {}).get("symbol", "")
        desc = position.get("symbolDescription", symbol)

        quote = self.get_market_quote(symbol)
        if not quote:
            speak(f"I couldn't get market data for {desc}.")
            return

        mf = quote.get("MutualFund", {})
        all_data = quote.get("All", {})

        if field == "expense_ratio":
            val = mf.get("netExpenseRatio")
            if val is not None:
                speak(f"{desc} net expense ratio is {val:.2f} percent.")
            else:
                speak(f"Net expense ratio is not available for {desc}. This field is typically only available for mutual funds and ETFs.")
        elif field == "gross_expense_ratio":
            val = mf.get("grossExpenseRatio")
            if val is not None:
                speak(f"{desc} gross expense ratio is {val:.2f} percent.")
            else:
                speak(f"Gross expense ratio is not available for {desc}.")
        elif field == "annual_yield":
            val = all_data.get("yield") or all_data.get("divYield")
            if val is not None:
                speak(f"{desc} annual yield is {val:.2f} percent.")
            else:
                speak(f"Annual yield is not available for {desc}.")

    def _speak_position_field(self, position, field):
        symbol = position.get("Product", {}).get("symbol", "")
        desc = position.get("symbolDescription", symbol)
        quick = position.get("Quick", position.get("quick", {}))
        complete = position.get("Complete", position.get("complete", {}))
        fundamental = position.get("Fundamental", position.get("fundamental", {}))

        performance = position.get("Performance", position.get("performance", {}))

        field_map = {
            "price": ("lastTrade", quick, "last trade price"),
            "last_price": ("lastTrade", quick, "last trade price"),
            "change": ("change", position, "today's change"),
            "change_pct": ("changePct", position, "today's change percent"),
            "gain": ("totalGain", position, "total gain"),
            "gain_pct": ("totalGainPct", position, "total gain percent"),
            "days_gain": ("daysGain", position, "today's gain"),
            "days_gain_pct": ("daysGainPct", position, "today's gain percent"),
            "value": ("marketValue", position, "market value"),
            "market_value": ("marketValue", position, "market value"),
            "quantity": ("quantity", position, "shares owned"),
            "cost": ("totalCost", position, "total cost"),
            "cost_per_share": ("costPerShare", position, "cost per share"),
            "price_paid": ("pricePaid", position, "price paid"),
            "pct_of_portfolio": ("pctOfPortfolio", position, "percent of portfolio"),
            "volume": ("volume", quick, "volume"),
            "pe_ratio": ("peRatio", fundamental, "P E ratio"),
            "eps": ("eps", fundamental, "earnings per share"),
            "est_earnings": ("estEarnings", complete, "estimated earnings"),
            "dividend": ("dividend", fundamental, "dividend"),
            "annual_dividend": ("annualDividend", complete, "annual dividend"),
            "div_yield": ("divYield", fundamental, "dividend yield"),
            "div_pay_date": ("divPayDate", complete, "dividend pay date"),
            "ex_div_date": ("exDividendDate", complete, "ex-dividend date"),
            "market_cap": ("marketCap", fundamental, "market cap"),
            "week52_high": ("week52High", complete, "52-week high"),
            "week52_low": ("week52Low", complete, "52-week low"),
            "week52_range": ("week52Range", fundamental, "52-week range"),
            "days_range": ("daysRange", complete, "today's range"),
            "bid": ("bid", complete, "bid price"),
            "bid_size": ("bidSize", complete, "bid size"),
            "ask": ("ask", complete, "ask price"),
            "ask_size": ("askSize", complete, "ask size"),
            "bid_ask_spread": ("bidAskSpread", complete, "bid-ask spread"),
            "open": ("open", complete, "opening price"),
            "prev_close": ("prevClose", complete, "previous close"),
            "beta": ("beta", complete, "beta"),
            "perform_1month": ("perform1Month", complete, "one-month performance"),
            "perform_3month": ("perform3Month", complete, "three-month performance"),
            "perform_6month": ("perform6Month", complete, "six-month performance"),
            "perform_12month": ("perform12Month", complete, "twelve-month performance"),
            "delta": ("delta", complete, "delta"),
            "gamma": ("gamma", complete, "gamma"),
            "theta": ("theta", complete, "theta"),
            "vega": ("vega", complete, "vega"),
            "rho": ("rho", complete, "rho"),
            "iv_pct": ("ivPct", complete, "implied volatility"),
            "open_interest": ("openInterest", complete, "open interest"),
            "days_to_expiration": ("daysToExpiration", complete, "days to expiration"),
            "intrinsic_value": ("intrinsicValue", complete, "intrinsic value"),
            "exchange": ("exchange", complete, "exchange"),
            "commissions": ("commissions", position, "commissions"),
        }

        if field == "date_acquired":
            raw = position.get("dateAcquired")
            if raw:
                from datetime import datetime
                try:
                    dt = datetime.fromtimestamp(raw / 1000)
                    speak(f"You purchased {desc} on {dt.strftime('%B %d, %Y')}.")
                except (ValueError, OSError):
                    speak(f"{desc} acquisition date data is {raw}.")
            else:
                speak(f"I don't have a purchase date for {desc}.")
            return

        if field not in field_map:
            speak(f"I don't know how to look up {field} for {desc}. Try asking for price, value, gain, or quantity.")
            return

        key, source, label = field_map[field]
        value = source.get(key) if source else None

        if value is None:
            speak(f"I don't have {label} data for {desc} right now.")
            return

        if isinstance(value, str):
            speak(f"{desc} {label} is {value}.")
        elif field in ("div_pay_date", "ex_div_date"):
            from datetime import datetime
            try:
                dt = datetime.fromtimestamp(value / 1000)
                speak(f"{desc} {label} is {dt.strftime('%B %d, %Y')}.")
            except (ValueError, OSError):
                speak(f"{desc} {label} is {value}.")
        elif "pct" in field or "yield" in field or field.startswith("perform_") or field == "iv_pct":
            speak(f"{desc} {label} is {value:.2f} percent.")
        elif "quantity" in field or field in ("bid_size", "ask_size", "open_interest"):
            speak(f"{desc} {label} is {value:,.0f}.")
        elif field in ("days_to_expiration",):
            speak(f"{desc} has {value:.0f} days to expiration.")
        elif field in ("ratio", "pe_ratio", "beta", "delta", "gamma", "theta", "vega", "rho", "eps", "est_earnings"):
            speak(f"{desc} {label} is {value:.2f}.")
        elif field in ("exchange",):
            speak(f"{desc} trades on {value}.")
        elif "cap" in field:
            if value >= 1_000_000_000_000:
                speak(f"{desc} {label} is ${value / 1_000_000_000_000:.2f} trillion.")
            elif value >= 1_000_000_000:
                speak(f"{desc} {label} is ${value / 1_000_000_000:.2f} billion.")
            elif value >= 1_000_000:
                speak(f"{desc} {label} is ${value / 1_000_000:.2f} million.")
            else:
                speak(f"{desc} {label} is ${value:,.2f}.")
        else:
            speak(f"{desc} {label} is ${value:,.2f}.")

    def _speak_market_quote(self, quote, field, symbol):
        product = quote.get("Product", {})
        sym = product.get("symbol", symbol)
        all_data = quote.get("All", {})

        if field in ("price", "last_price", "summary"):
            last = all_data.get("lastTrade")
            change = all_data.get("changeClose")
            change_pct = all_data.get("changeClosePercentage")
            if last is not None:
                msg = f"{sym} is trading at ${last:,.2f}"
                if change is not None and change_pct is not None:
                    direction = "up" if change >= 0 else "down"
                    msg += f", {direction} ${abs(change):,.2f}, or {abs(change_pct):.2f} percent"
                speak(msg + ".")
            else:
                speak(f"No price data available for {sym}.")
        elif field == "change":
            change = all_data.get("changeClose")
            if change is not None:
                speak(f"{sym} changed ${change:,.2f} today.")
            else:
                speak(f"No change data for {sym}.")
        elif field == "volume":
            vol = all_data.get("totalVolume")
            if vol is not None:
                speak(f"{sym} volume is {vol:,}.")
            else:
                speak(f"No volume data for {sym}.")
        elif field == "bid":
            bid = all_data.get("bid")
            if bid is not None:
                speak(f"{sym} bid is ${bid:,.2f}.")
        elif field == "ask":
            ask = all_data.get("ask")
            if ask is not None:
                speak(f"{sym} ask is ${ask:,.2f}.")
        elif field in ("prev_close", "previous_close"):
            pc = all_data.get("previousClose")
            if pc is not None:
                speak(f"{sym} previous close was ${pc:,.2f}.")
        else:
            last = all_data.get("lastTrade")
            if last is not None:
                speak(f"{sym} is at ${last:,.2f}. I only have market data for this stock since it's not in your portfolio.")

    def _speak_help(self):
        speak("Press your button, then ask me something like:")
        speak("What's the price of Apple?")
        speak("How much is my Tesla worth?")
        speak("Tell me about Microsoft.")
        speak("What's my account balance?")
        speak("Read my portfolio.")
        speak("Open E-Trade. This opens the website if you want to make a trade.")
        speak("You can ask about: price, value, gain, change, quantity, dividend, expense ratio, annual yield, and more.")

    def _audio_rms(self, audio_data):
        """Calculate the RMS volume level of audio data."""
        try:
            return audioop.rms(audio_data.get_raw_data(), 2)
        except Exception:
            return 0

    def _on_key_press(self, key):
        """Callback for pynput keyboard listener."""
        if key == self._button_key or (self._fallback_key and key == self._fallback_key):
            self.button_pressed.set()

    def _handle_error(self, error, context=""):
        """
        Central error handler. Logs the error, increments the counter,
        sends an email alert if configured, and gracefully recovers or
        shuts down if errors are cascading.
        """
        self._consecutive_errors += 1
        error_msg = f"{context}: {error}" if context else str(error)
        tb = traceback.format_exc()

        logger.error("ERROR (#%d) %s", self._consecutive_errors, error_msg)
        logger.debug("Traceback:\n%s", tb)
        transcript_logger.info("ERROR: %s", error_msg)

        if self._consecutive_errors == 1:
            send_error_email(
                self.alert_email,
                f"Error: {error_msg}\n\nTraceback:\n{tb}",
                LOG_FILE,
            )

        if self._consecutive_errors >= self.MAX_CONSECUTIVE_ERRORS:
            logger.critical(
                "Too many consecutive errors (%d). Shutting down to prevent crash.",
                self._consecutive_errors,
            )
            speak("I've encountered too many errors in a row. "
                  "Shutting down to be safe. Please restart me, "
                  "or contact Ferris if this keeps happening.")
            if self.alert_email:
                send_error_email(
                    self.alert_email,
                    f"CRITICAL: {self._consecutive_errors} consecutive errors. "
                    f"Assistant shut itself down.\n\nLast error: {error_msg}\n\n{tb}",
                    LOG_FILE,
                )
            self.running = False
            return

        speak("I ran into a problem, but I'm still here. Press the button to try again.")

    def _reset_error_count(self):
        """Call after a successful interaction to reset the error counter."""
        self._consecutive_errors = 0

    def listen_loop(self):
        """Button-triggered listen loop. Waits for button press, then listens."""
        speak("I'm ready. Press your button to ask a question.")
        speak(f"Your button is mapped to the {self._button_key_name} key.")
        if self._fallback_key_name:
            speak(f"You can also use the {self._fallback_key_name} key as a backup.")

        with self.microphone as source:
            speak("Adjusting for background noise. One moment.")
            self.recognizer.adjust_for_ambient_noise(source, duration=2)

        speak("Ready! Press your button whenever you want to ask something.")
        logger.info("Listen loop started. Button: %s, Fallback: %s, Volume threshold: %d",
                     self._button_key_name, self._fallback_key_name or "none",
                     self.volume_threshold)

        listener = keyboard.Listener(on_press=self._on_key_press)
        listener.daemon = True
        listener.start()

        while self.running:
            try:
                self.button_pressed.wait()
                self.button_pressed.clear()

                beep()
                transcript_logger.info("--- Button pressed ---")

                with self.microphone as source:
                    try:
                        audio = self.recognizer.listen(source, timeout=8, phrase_time_limit=15)
                    except sr.WaitTimeoutError:
                        speak("I didn't hear anything. Press the button and try again.")
                        transcript_logger.info("USER: (silence — no speech detected)")
                        continue

                rms = self._audio_rms(audio)
                logger.info("Audio RMS level: %d (threshold: %d)", rms, self.volume_threshold)

                if rms < self.volume_threshold:
                    speak("I couldn't hear you clearly. Try speaking a little louder or closer to the microphone.")
                    transcript_logger.info("USER: (too quiet — RMS %d below threshold %d)",
                                           rms, self.volume_threshold)
                    continue

                try:
                    text = self.recognizer.recognize_google(audio).lower().strip()
                except sr.UnknownValueError:
                    speak("I didn't catch that. Press the button and try again.")
                    transcript_logger.info("USER: (unintelligible)")
                    continue
                except sr.RequestError as e:
                    logger.error("Speech recognition API error: %s", e)
                    speak("I'm having trouble with speech recognition. Check your internet connection.")
                    transcript_logger.info("USER: (speech API error: %s)", e)
                    time.sleep(3)
                    continue

                logger.info("Heard: %s (RMS: %d)", text, rms)
                transcript_logger.info("USER: %s", text)

                self.answer_query(text)
                self._reset_error_count()

            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                self._handle_error(e, context="Listen loop")
                time.sleep(2)

        listener.stop()

    def run(self):
        """Main entry point with top-level error recovery."""
        logger.info("=== Voice Assistant starting ===")
        if self.alert_email:
            logger.info("Error alerts will be sent to: %s", self.alert_email)

        speak("Welcome to your E-Trade voice assistant.")

        try:
            self.authenticate()
        except Exception as e:
            self._handle_error(e, context="Authentication")
            speak("Authentication failed. Please restart and try again.")
            return

        try:
            if not self.load_accounts():
                speak("Could not load accounts. Exiting.")
                return
        except Exception as e:
            self._handle_error(e, context="Loading accounts")
            speak("Could not load accounts. Please restart and try again.")
            return

        try:
            self.refresh_portfolio()
        except Exception as e:
            self._handle_error(e, context="Loading portfolio")
            speak("Could not load portfolio, but I'll keep going. You can say 'refresh' to try again.")

        try:
            self.listen_loop()
        except KeyboardInterrupt:
            pass
        except Exception as e:
            self._handle_error(e, context="Fatal error in listen loop")

        logger.info("=== Voice Assistant shutting down ===")
        speak("Goodbye!")


def main():
    parser = argparse.ArgumentParser(description="Voice-driven E*TRADE portfolio reader")
    parser.add_argument("--sandbox", action="store_true", help="Use sandbox API")
    parser.add_argument(
        "--button", default="space",
        help="Key the physical button sends: space, enter, f5, f12 (default: space)",
    )
    parser.add_argument(
        "--volume", type=int, default=1500,
        help="Minimum audio volume (RMS) to accept speech. "
             "Raise to ignore distant voices, lower if it's rejecting grandpop. "
             "Default: 1500. Quiet room: 800. Noisy room: 2500.",
    )
    parser.add_argument(
        "--alert-email", default="ferris@ferryrules.com",
        help="Email address to send error alerts to. "
             "Uses macOS Mail app — make sure it's signed in. "
             "Default: ferris@ferryrules.com. Set to 'none' to disable.",
    )
    parser.add_argument(
        "--fallback-button", default="shift",
        help="Backup key that also triggers listening. "
             "Useful for testing without the foot pedal. "
             "Default: shift (left Shift key). Set to 'none' to disable.",
    )
    parser.add_argument(
        "--forget-auth", action="store_true",
        help="Forget the cached E*TRADE OAuth token (forces a fresh "
             "browser login next run). Use this if the assistant keeps "
             "failing right after launch.",
    )
    args = parser.parse_args()

    if args.forget_auth:
        TokenStore.clear()
        print("  [OK] Cached E*TRADE token cleared. Next run will require a fresh login.")
        return

    fallback = args.fallback_button if args.fallback_button != "none" else None
    alert = args.alert_email if args.alert_email != "none" else None

    assistant = ETradeVoiceAssistant(
        sandbox=args.sandbox,
        button_key=args.button,
        volume_threshold=args.volume,
        alert_email=alert,
        fallback_button=fallback,
    )
    assistant.run()


if __name__ == "__main__":
    main()
