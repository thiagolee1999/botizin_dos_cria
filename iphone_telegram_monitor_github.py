#!/usr/bin/env python3
"""Monitor 256GB iPhone Duo pickup at Apple Eaton Centre and Yorkdale.

Either colour is acceptable. Python 3.9+, standard library only.

Usage:
    python3 iphone_telegram_monitor.py --once
    python3 iphone_telegram_monitor.py --telegram-test
    python3 iphone_telegram_monitor.py --interval 60 --checks 60 --state-file .monitor/state.json

Configure Telegram via TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.
--checks 60 performs exactly 60 attempts spaced by one minute from start to start,
then exits; GitHub Actions can launch a fresh job every hour.
--state-file persists successful observations between GitHub Actions runs when
combined with a cache restore/save. No Telegram credentials are written to disk.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

API_URL = "https://www.apple.com/ca/shop/retail/pickup-message"
BUY_URL = "https://www.apple.com/ca/shop/buy-iphone/iphone-duo"

# Verified Canadian Apple part numbers: 256GB only, either colour.
PARTS = {
    "MK244VC/A": ("Star White", "7.6-inch-display-256gb-star-white"),
    "MK254VC/A": ("Night Sky", "7.6-inch-display-256gb-night-sky"),
}

# Exact Apple retail store numbers, to avoid matching unintended GTA locations.
STORES = {
    "R121": "Eaton Centre",
    "R120": "Yorkdale",
}

# One query usually covers both stores; use fallback near Yorkdale if it doesn't.
POSTAL_CODES = ("M5V 2T6", "M6A 3A1")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/130.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-CA,en;q=0.9",
}


def apple_inventory(postal_code):
    """Get Apple pickup inventory keyed by (store ID, part number)."""
    query = [("pl", "true"), ("location", postal_code)]
    query += [(f"parts.{idx}", part) for idx, part in enumerate(PARTS)]
    url = f"{API_URL}?{urlencode(query)}"
    with urlopen(Request(url, headers=HEADERS), timeout=20) as response:
        payload = json.load(response)

    if str(payload.get("head", {}).get("status")) != "200":
        raise ValueError("Apple's inventory endpoint did not report success")

    stores = payload.get("body", {}).get("stores")
    if not isinstance(stores, list):
        raise ValueError("Apple did not return a stores list")

    results = {}
    for store in stores:
        store_id = store.get("storeNumber")
        if store_id not in STORES:
            continue
        availability = store.get("partsAvailability", {})
        for part in PARTS:
            entry = availability.get(part)
            if not isinstance(entry, dict):
                raise ValueError(f"Apple omitted {part} for {STORES[store_id]}")
            status = entry.get("pickupDisplay")
            if status not in {"available", "unavailable"}:
                raise ValueError(
                    f"Unexpected pickupDisplay={status!r} for {STORES[store_id]} / {part}"
                )
            results[(store_id, part)] = {
                "available": status == "available",
                "quote": entry.get("pickupSearchQuote") or "",
            }
    return results


def all_target_inventory():
    """Require both stores and both colours to be checked successfully."""
    results = apple_inventory(POSTAL_CODES[0])
    if {store for store, _ in results} != set(STORES):
        # Do a second lookup only if the first postal code omitted a store.
        results.update(apple_inventory(POSTAL_CODES[1]))
    expected = {(store, part) for store in STORES for part in PARTS}
    missing = expected - results.keys()
    if missing:
        raise ValueError(f"Apple did not report all requested store/model pairs: {sorted(missing)}")
    return results


def eta_priority(quote, now):
    """Sort by Apple's pickup quote, NOT the store's general 'availableNow' field.

    Values are (estimated days away, precision). Unknown pickup ETA sorts last
    among available choices, rather than being guessed as 'today'.
    """
    q = quote.strip().lower()
    if "today" in q:
        return (0, 0)
    if "tomorrow" in q:
        return (1, 0)

    # Handle dates if Apple ever provides one (e.g. 'Available Nov 10').
    dates = re.findall(r"\b([A-Za-z]{3,9}\s+\d{1,2}(?:,?\s+\d{4})?)\b", quote)
    for date_text in dates:
        for fmt in ("%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y",
                    "%b %d", "%B %d"):
            try:
                pickup = datetime.strptime(date_text, fmt).date()
                if "%Y" not in fmt:
                    pickup = pickup.replace(year=now.year)
                    if pickup < now.date():
                        pickup = pickup.replace(year=now.year + 1)
                return ((pickup - now.date()).days, 0)
            except (ValueError, OverflowError):
                pass

    # Weekday-only quotes, if supplied by Apple.
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for weekday, name in enumerate(weekdays):
        if re.search(rf"\b{name}\b", q):
            return ((weekday - now.weekday()) % 7, 1)
    return (999, 2)  # Available, but pickup date not reported.


def product_url(part):
    return f"{BUY_URL}/{PARTS[part][1]}"


def send_ntfy(topic, message, url):
    if not topic:
        return
    request = Request(
        f"https://ntfy.sh/{quote(topic, safe='')}",
        data=message.encode("utf-8"),
        headers={
            "Title": "iPhone Duo 256GB: pickup available",
            "Priority": "urgent",
            "Tags": "iphone,tada",
            "Click": url,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10):
            pass
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"[WARN] Could not send phone alert: {exc}", file=sys.stderr)


def send_telegram(bot_token, chat_id, message):
    """Send a plain-text Telegram message. Keep secrets out of error logs."""
    if not bot_token or not chat_id:
        return False
    request = Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=json.dumps({
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": True,
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            result = json.load(response)
        if not result.get("ok"):
            print("[WARN] Telegram rejected the message (check bot token/chat ID).",
                  file=sys.stderr)
            return False
        return True
    except HTTPError as exc:
        # HTTPError includes the request URL, which contains the bot token.
        print(f"[WARN] Telegram message failed (HTTP {exc.code}).", file=sys.stderr)
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        # Avoid printing exception details: they might disclose the bot token.
        print(f"[WARN] Telegram message failed ({type(exc).__name__}).", file=sys.stderr)
    return False


def show_results(results, previous, topic, now, telegram_token="", telegram_chat_id=""):
    available = [
        (store, part, info) for (store, part), info in results.items()
        if info["available"]
    ]
    available.sort(key=lambda item: (eta_priority(item[2]["quote"], now),
                                     STORES[item[0]], PARTS[item[1]][0]))
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

    if not available:
        print(f"[{timestamp}] No 256GB iPhone Duo available for pickup at either store.", flush=True)
        return {}

    best_eta = eta_priority(available[0][2]["quote"], now)
    print(f"[{timestamp}] {len(available)} available option(s) at Yorkdale / Eaton Centre:")
    print("  Earliest Apple-listed pickup options first (same ETA = tie):")
    current = {}
    telegram_alerts = []
    for store, part, info in available:
        eta = eta_priority(info["quote"], now)
        label = "FASTEST" if eta == best_eta else "LATER"
        color = PARTS[part][0]
        description = info["quote"].strip() or "Available — exact pickup time not provided"
        url = product_url(part)
        key = (store, part)
        current[key] = eta
        print(f"  [{label}] Apple {STORES[store]} | 256GB {color} | {description}")
        print(f"           {url} (select Apple {STORES[store]} at checkout)")

        # Alert on newly available stock, or if Apple's pickup ETA improves.
        # On initial startup, every available option is considered new.
        old = previous.get(key)
        if old is None or eta < old:
            kind = "IN STOCK" if old is None else "EARLIER PICKUP"
            message = f"{kind}: iPhone Duo 256GB {color}, Apple {STORES[store]}. {description}."
            print(f"           ALERT: {kind}")
            send_ntfy(topic, message, url)
            telegram_alerts.append((store, part, description, kind, url))
            print("\a", end="", flush=True)

    if telegram_alerts and telegram_token and telegram_chat_id:
        # Send one Telegram alert per poll; include all available options in ETA order,
        # not just the first one that happened to become available.
        lines = ["📱 iPhone Duo 256GB — pickup alert", ""]
        changed = {(store, part) for store, part, _, _, _ in telegram_alerts}
        for store, part, info in available:
            color = PARTS[part][0]
            pickup = info["quote"].strip() or "Available (pickup date unspecified)"
            prefix = "🆕 " if (store, part) in changed else "• "
            lines.append(f"{prefix}{STORES[store]} — {color} — {pickup}")
            lines.append(product_url(part))
        lines.append("Select the store during Apple checkout. Availability can change.")
        if not send_telegram(telegram_token, telegram_chat_id, "\n".join(lines)):
            # Failed deliveries should be retried on the next successful check.
            # A network timeout could have sent the message, so rare duplicates
            # remain possible, but silently losing the alert is worse.
            for store, part, _, _, _ in telegram_alerts:
                current.pop((store, part), None)
    print(flush=True)
    return current


def load_state(filename):
    """Load last known available options (never credentials) from a JSON file."""
    if not filename:
        return {}
    path = Path(filename)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != 1 or not isinstance(data.get("available"), list):
            raise ValueError("unrecognized state format")
        previous = {}
        for item in data["available"]:
            store, part, eta = item["store"], item["part"], item["eta"]
            if store in STORES and part in PARTS and (isinstance(eta, list) and
                    len(eta) == 2 and all(type(n) is int for n in eta)):
                previous[(store, part)] = tuple(eta)
        return previous
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print(f"[WARN] Ignoring unreadable state file ({type(exc).__name__}).", file=sys.stderr)
        return {}


def save_state(filename, previous):
    """Atomically persist the latest successfully observed stock statuses."""
    if not filename:
        return
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "available": [
            {"store": store, "part": part, "eta": list(eta)}
            for (store, part), eta in sorted(previous.items())
        ],
    }
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--once", action="store_true", help="Check once and exit")
    parser.add_argument("--interval", type=int, default=30,
                        help="Seconds between requests (default/minimum 30)")
    parser.add_argument("--ntfy-topic", help="Optional ntfy.sh topic for iPhone push alerts")
    parser.add_argument("--checks", type=int, default=None,
                        help="Run exactly this many inventory checks, then exit (default: unlimited)")
    parser.add_argument("--state-file",
                        help="JSON inventory-state file; allows persistence across workflow runs")
    parser.add_argument("--telegram-test", action="store_true",
                        help="Send a Telegram test notification, then exit (no Apple request)")
    args = parser.parse_args()
    if args.interval < 30 and not (args.once or args.telegram_test):
        parser.error("Minimum polling interval is 30 seconds")
    if args.checks is not None and args.checks < 1:
        parser.error("--checks must be at least 1")
    if args.once and args.checks not in (None, 1):
        parser.error("--once cannot be combined with --checks > 1")

    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if bool(telegram_token) != bool(telegram_chat_id):
        parser.error("Set both TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID (or neither)")
    if args.telegram_test:
        if not telegram_token:
            parser.error("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID before --telegram-test")
        ok = send_telegram(telegram_token, telegram_chat_id,
                           "✅ iPhone Duo stock monitor: Telegram notifications are working.")
        if ok:
            print("Telegram test message sent successfully.")
            return 0
        return 1

    total_checks = 1 if args.once else args.checks
    print("iPhone Duo 256GB | Star White OR Night Sky")
    print("Apple Eaton Centre (R121) OR Apple Yorkdale (R120)")
    print(f"Checking in-store pickup every {args.interval} seconds "
          f"for {total_checks if total_checks else 'unlimited'} attempt(s).\n", flush=True)
    previous = load_state(args.state_file)
    if previous:
        print(f"Restored {len(previous)} previously available option(s).", flush=True)

    # Start-to-start cadence; API latency does not accumulate into an extra
    # 60 seconds each cycle, and there is no sleep after the final check.
    started_at = time.monotonic()
    attempt = 0
    while total_checks is None or attempt < total_checks:
        attempt += 1
        now = datetime.now().astimezone()
        if total_checks:
            print(f"Check {attempt}/{total_checks}", flush=True)
        try:
            results = all_target_inventory()
            previous = show_results(results, previous, args.ntfy_topic, now,
                                    telegram_token, telegram_chat_id)
            save_state(args.state_file, previous)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
            # Network errors are NOT out of stock. Preserve last successful state.
            print(f"[{now:%Y-%m-%d %H:%M:%S}] CHECK FAILED: {exc}", file=sys.stderr)
            if args.once:
                return 1
        if total_checks is not None and attempt >= total_checks:
            print(f"Completed {attempt} checks; exiting normally.", flush=True)
            return 0
        try:
            deadline = started_at + attempt * args.interval
            time.sleep(max(0, deadline - time.monotonic()))
        except KeyboardInterrupt:
            print("\nStopped.")
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
