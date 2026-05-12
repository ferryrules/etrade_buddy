"""
Test the voice assistant without E*TRADE auth.
Uses fake portfolio data but real microphone + button input.

Usage: python test_voice.py [--button KEY] [--volume THRESHOLD]
"""

import argparse
import audioop
import subprocess
import threading
import time

import speech_recognition as sr
from pynput import keyboard

from query_parser import parse_query, register_portfolio_stocks

FAKE_PORTFOLIO = {
    "AAPL": {
        "Product": {"symbol": "AAPL"},
        "symbolDescription": "APPLE INC",
        "quantity": 50,
        "marketValue": 9925.00,
        "totalGain": 1250.00,
        "totalGainPct": 14.42,
        "daysGain": 75.50,
        "daysGainPct": 0.77,
        "pricePaid": 173.50,
        "totalCost": 8675.00,
        "costPerShare": 173.50,
        "change": 1.51,
        "changePct": 0.77,
        "pctOfPortfolio": 25.5,
        "Quick": {"lastTrade": 198.50, "change": 1.51, "changePct": 0.77, "volume": 54321000},
        "Fundamental": {"lastTrade": 198.50, "peRatio": 31.2, "eps": 6.36, "dividend": 1.00, "divYield": 0.50, "marketCap": 3080000000000},
    },
    "TSLA": {
        "Product": {"symbol": "TSLA"},
        "symbolDescription": "TESLA INC",
        "quantity": 25,
        "marketValue": 6812.50,
        "totalGain": -437.50,
        "totalGainPct": -6.03,
        "daysGain": 125.00,
        "daysGainPct": 1.87,
        "pricePaid": 290.00,
        "totalCost": 7250.00,
        "costPerShare": 290.00,
        "change": 5.00,
        "changePct": 1.87,
        "pctOfPortfolio": 17.5,
        "Quick": {"lastTrade": 272.50, "change": 5.00, "changePct": 1.87, "volume": 98765000},
    },
    "RKLB": {
        "Product": {"symbol": "RKLB"},
        "symbolDescription": "ROCKET LAB USA INC COM",
        "quantity": 200,
        "marketValue": 5400.00,
        "totalGain": 2400.00,
        "totalGainPct": 80.0,
        "daysGain": -50.00,
        "daysGainPct": -0.92,
        "pricePaid": 15.00,
        "totalCost": 3000.00,
        "costPerShare": 15.00,
        "change": -0.25,
        "changePct": -0.92,
        "pctOfPortfolio": 13.8,
        "Quick": {"lastTrade": 27.00, "change": -0.25, "changePct": -0.92, "volume": 12345000},
    },
    "SMCI": {
        "Product": {"symbol": "SMCI"},
        "symbolDescription": "SUPER MICRO COMPUTER INC COM",
        "quantity": 10,
        "marketValue": 4500.00,
        "totalGain": 500.00,
        "totalGainPct": 12.5,
        "daysGain": 30.00,
        "daysGainPct": 0.67,
        "pricePaid": 400.00,
        "totalCost": 4000.00,
        "costPerShare": 400.00,
        "change": 3.00,
        "changePct": 0.67,
        "pctOfPortfolio": 11.5,
        "Quick": {"lastTrade": 450.00, "change": 3.00, "changePct": 0.67, "volume": 8765000},
    },
}

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


def speak(text):
    print(f"  >> {text}")
    subprocess.run(["say", "-r", "175", text], check=False)


def beep():
    subprocess.run(["afplay", "/System/Library/Sounds/Tink.aiff"], check=False)


def build_cache(positions):
    cache = {}
    for sym, pos in positions.items():
        cache[sym] = pos
        desc = pos.get("symbolDescription", "").upper()
        if desc:
            cache[desc] = pos
    register_portfolio_stocks(cache)
    return cache


def answer(cache, text):
    text = text.lower().strip()

    if "balance" in text:
        speak("Your fake test account value is $26,637.50.")
        return

    if "portfolio" in text and ("read" in text or "list" in text or "all" in text):
        speak(f"You have {len(FAKE_PORTFOLIO)} positions.")
        for pos in FAKE_PORTFOLIO.values():
            desc = pos["symbolDescription"]
            qty = pos["quantity"]
            lt = pos["Quick"]["lastTrade"]
            mv = pos["marketValue"]
            speak(f"{desc}: {qty:.0f} shares at ${lt:,.2f}, worth ${mv:,.2f}")
        return

    if "help" in text:
        speak("Press your button, then ask: what's the price of Apple? Or: tell me about Tesla.")
        return

    parsed = parse_query(text)
    if not parsed:
        speak("I didn't understand that. Try: what's the price of Apple?")
        return

    symbol, field = parsed
    print(f"  [parsed: symbol={symbol}, field={field}]")

    pos = cache.get(symbol)
    if not pos:
        for key, p in cache.items():
            if symbol in key:
                pos = p
                break

    if not pos:
        speak(f"I don't have {symbol} in the test portfolio.")
        return

    desc = pos["symbolDescription"]
    quick = pos.get("Quick", {})
    fundamental = pos.get("Fundamental", {})

    if field == "summary":
        speak(f"Here's the full report for {desc}.")
        lt = quick.get("lastTrade")
        if lt is not None:
            speak(f"Last price: ${lt:,.2f}.")
        speak(f"Quantity: {pos['quantity']:.0f} shares.")
        dg = pos.get("daysGain", 0)
        direction = "up" if dg >= 0 else "down"
        speak(f"Day's gain: {direction} ${abs(dg):,.2f}.")
        speak(f"Cost per share: ${pos['costPerShare']:,.2f}.")
        speak(f"Value: ${pos['marketValue']:,.2f}.")
        tg = pos.get("totalGain", 0)
        direction = "up" if tg >= 0 else "down"
        speak(f"Total gain: {direction} ${abs(tg):,.2f}.")
        speak("Net expense ratio: not available in test mode.")
        div = fundamental.get("dividend")
        if div is not None:
            speak(f"Dividend: ${div:,.4f}.")
        else:
            speak("Dividend: not available.")
        dy = fundamental.get("divYield")
        if dy is not None:
            speak(f"Annual yield: {dy:.2f} percent.")
        else:
            speak("Annual yield: not available.")
        speak(f"End of report for {desc}.")
    elif field == "price":
        lt = quick.get("lastTrade", 0)
        chg = pos.get("change", 0)
        chg_pct = pos.get("changePct", 0)
        direction = "up" if chg >= 0 else "down"
        speak(f"{desc} is at ${lt:,.2f}, {direction} ${abs(chg):,.2f} or {abs(chg_pct):.2f} percent.")
    elif field in ("value", "market_value"):
        speak(f"{desc} market value is ${pos['marketValue']:,.2f}.")
    elif field == "gain":
        speak(f"{desc} total gain is ${pos['totalGain']:,.2f}, or {pos['totalGainPct']:.2f} percent.")
    elif field == "days_gain":
        dg = pos["daysGain"]
        direction = "up" if dg >= 0 else "down"
        speak(f"{desc} day's gain: {direction} ${abs(dg):,.2f}.")
    elif field == "quantity":
        speak(f"You own {pos['quantity']:.0f} shares of {desc}.")
    elif field == "change":
        speak(f"{desc} changed ${pos['change']:,.2f} today, or {pos['changePct']:.2f} percent.")
    elif field == "volume":
        speak(f"{desc} volume is {quick.get('volume', 0):,}.")
    elif field in ("cost", "cost_per_share", "price_paid"):
        speak(f"{desc} cost per share is ${pos['costPerShare']:,.2f}, total cost ${pos['totalCost']:,.2f}.")
    elif field == "pct_of_portfolio":
        speak(f"{desc} is {pos['pctOfPortfolio']:.1f} percent of your portfolio.")
    elif field == "dividend":
        div = fundamental.get("dividend")
        if div is not None:
            speak(f"{desc} dividend is ${div:,.4f}.")
        else:
            speak(f"Dividend not available for {desc} in test mode.")
    elif field == "div_yield" or field == "annual_yield":
        dy = fundamental.get("divYield")
        if dy is not None:
            speak(f"{desc} annual yield is {dy:.2f} percent.")
        else:
            speak(f"Annual yield not available for {desc} in test mode.")
    elif field == "pe_ratio":
        pe = fundamental.get("peRatio")
        if pe is not None:
            speak(f"{desc} P E ratio is {pe:.2f}.")
        else:
            speak(f"P E ratio not available for {desc} in test mode.")
    elif field == "eps":
        eps = fundamental.get("eps")
        if eps is not None:
            speak(f"{desc} earnings per share is {eps:.2f}.")
        else:
            speak(f"EPS not available for {desc} in test mode.")
    elif field == "market_cap":
        mc = fundamental.get("marketCap", 0)
        if mc >= 1_000_000_000_000:
            speak(f"{desc} market cap is ${mc / 1_000_000_000_000:.2f} trillion.")
        elif mc >= 1_000_000_000:
            speak(f"{desc} market cap is ${mc / 1_000_000_000:.2f} billion.")
        else:
            speak(f"{desc} market cap is ${mc:,.2f}.")
    elif field == "expense_ratio":
        speak(f"Net expense ratio is not available for {desc} in test mode. This is typically only for mutual funds and ETFs.")
    else:
        speak(f"I have {desc} but don't have {field} data in this test.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--button", default="space",
        help="Key the button sends: space, enter, f5, f12 (default: space)",
    )
    parser.add_argument(
        "--volume", type=int, default=1500,
        help="Min audio RMS to accept. Default 1500. Lower (800) for quiet rooms, higher (2500) for noisy.",
    )
    parser.add_argument(
        "--fallback-button", default="shift",
        help="Backup key that also triggers listening. "
             "Default: shift (left Shift). Set to 'none' to disable.",
    )
    args = parser.parse_args()

    button_key = BUTTON_KEYS.get(args.button, keyboard.Key.space)
    fallback_key = BUTTON_KEYS.get(args.fallback_button) if args.fallback_button != "none" else None
    volume_threshold = args.volume
    button_pressed = threading.Event()

    def on_key_press(key):
        if key == button_key or (fallback_key and key == fallback_key):
            button_pressed.set()

    cache = build_cache(FAKE_PORTFOLIO)
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = False
    mic = sr.Microphone()

    speak("Voice assistant test mode. Using fake portfolio data.")
    speak(f"Press {args.button} to talk. Press control C to quit.")
    if fallback_key:
        speak(f"You can also use the {args.fallback_button} key as a backup.")

    with mic as source:
        speak("Adjusting for background noise.")
        recognizer.adjust_for_ambient_noise(source, duration=2)

    speak("Ready! Press your button to ask a question.")

    listener = keyboard.Listener(on_press=on_key_press)
    listener.daemon = True
    listener.start()

    while True:
        try:
            button_pressed.wait()
            button_pressed.clear()

            beep()

            with mic as source:
                try:
                    audio = recognizer.listen(source, timeout=8, phrase_time_limit=15)
                except sr.WaitTimeoutError:
                    speak("I didn't hear anything. Press the button and try again.")
                    continue

            rms = audioop.rms(audio.get_raw_data(), 2)
            print(f"  [audio RMS: {rms}, threshold: {volume_threshold}]")

            if rms < volume_threshold:
                speak("I couldn't hear you clearly. Try speaking louder or closer to the microphone.")
                continue

            try:
                text = recognizer.recognize_google(audio).lower().strip()
            except sr.UnknownValueError:
                speak("I didn't catch that. Press the button and try again.")
                continue
            except sr.RequestError:
                speak("Speech recognition error. Check internet.")
                time.sleep(3)
                continue

            print(f"  [heard: \"{text}\"] [RMS: {rms}]")
            answer(cache, text)

        except KeyboardInterrupt:
            speak("Goodbye!")
            break

    listener.stop()


if __name__ == "__main__":
    main()
