import html
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import feedparser
import requests


# ============================================================
# PRIVATE CREDENTIALS
# These are supplied securely by GitHub Actions.
# Do not paste your real token or chat ID into this file.
# ============================================================

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


# ============================================================
# GENERAL SETTINGS
# ============================================================

STATE_FILE = Path("state.json")

# A normal scheduled run sends one report.
POSTS_PER_RUN = 1

# Wait between reports when preloading the archive.
SEED_DELAY_SECONDS = 2

# The script only examines this many recent items from each feed.
ITEMS_PER_FEED = 25

# User agent helps RSS providers identify the request properly.
USER_AGENT = (
    "OSIMU-RSS-Monitor/1.0 "
    "(automated exhibition feed; contact repository owner)"
)


# ============================================================
# RSS SOURCES
#
# Visitors only see the source names, not the internal category.
# ============================================================

FEEDS = [
    {
        "name": "Google News",
        "url": (
            "https://news.google.com/rss/search"
            "?q=goose&hl=en-SG&gl=SG&ceid=SG:en"
        ),
        "category": "wildlife",
    },
    {
        "name": "Google News",
        "url": (
            "https://news.google.com/rss/search"
            "?q=geese&hl=en-SG&gl=SG&ceid=SG:en"
        ),
        "category": "wildlife",
    },
    {
        "name": "r/HighStrangeness",
        "url": "https://www.reddit.com/r/HighStrangeness/.rss",
        "category": "anomaly",
    },
    {
        "name": "r/UnresolvedMysteries",
        "url": "https://www.reddit.com/r/UnresolvedMysteries/.rss",
        "category": "anomaly",
    },
]


# ============================================================
# CONTENT RESTRICTIONS
#
# Items containing these words are excluded.
# Add more terms later if unwanted stories appear.
# ============================================================

BLOCKED_TERMS = [
    "nsfw",
    "graphic footage",
    "graphic video",
    "buy now",
    "coupon",
    "discount code",
    "sponsored",
    "advertorial",
    "promoted",
    "suicide",
    "self-harm",
    "murdered child",
    "child murder",
    "sexual assault",
    "rape",
]

# Especially sensitive terms for unresolved-mystery stories.
# This keeps the exhibition from unexpectedly displaying
# graphic or upsetting subjects.
SENSITIVE_TERMS = [
    "dismember",
    "decapitat",
    "corpse",
    "human remains",
    "infant death",
    "child death",
    "torture",
]


# ============================================================
# NARRATIVE PHASES
#
# The system becomes steadily less objective.
# It never explicitly says, "Geese aren't real."
# ============================================================

PHASES = [
    {
        "maximum_report": 6,
        "classification": "PUBLIC",
        "wildlife_assessments": [
            "Routine wildlife activity.",
            "Behaviour appears consistent with an ordinary waterfowl encounter.",
            "No unusual characteristics have been confirmed.",
            "The report falls within expected wildlife parameters.",
        ],
        "anomaly_assessments": [
            "Unverified anomalous report.",
            "Insufficient information for further assessment.",
            "The event has been recorded for routine monitoring.",
            "No relationship to other reports has been established.",
        ],
        "notes": [
            "No evidence of coordinated activity.",
            "No connection to other monitored events has been identified.",
            "No further action is recommended.",
            "The incident is considered isolated.",
        ],
        "confidence_range": (22, 42),
    },
    {
        "maximum_report": 12,
        "classification": "PUBLIC",
        "wildlife_assessments": [
            "Probably routine wildlife activity.",
            "Minor behavioural irregularities have been noted.",
            "The subject's positioning warrants limited monitoring.",
            "No immediate concern has been identified.",
        ],
        "anomaly_assessments": [
            "The account remains unverified.",
            "The report has been retained for cross-reference.",
            "Additional observation may be useful.",
            "The event does not currently justify escalation.",
        ],
        "notes": [
            "The recurrence is likely coincidental.",
            "No meaningful pattern has been established.",
            "Current evidence remains inconclusive.",
            "Similarities to earlier reports may be incidental.",
        ],
        "confidence_range": (35, 55),
    },
    {
        "maximum_report": 18,
        "classification": "MONITOR",
        "wildlife_assessments": [
            "Repeated observational behaviour has been noted.",
            "The location resembles previous monitored incidents.",
            "The activity is unusual but not yet actionable.",
            "The subject remained present longer than expected.",
        ],
        "anomaly_assessments": [
            "A possible relationship to earlier incidents is under review.",
            "The timing overlaps with other monitored activity.",
            "Cross-referencing has produced an inconclusive match.",
            "The incident may be relevant to an emerging pattern.",
        ],
        "notes": [
            "Coincidences continue to accumulate.",
            "The frequency is slightly above the expected baseline.",
            "Additional wildlife-related reports have been requested.",
            "The relationship between reports remains unresolved.",
        ],
        "confidence_range": (48, 68),
    },
    {
        "maximum_report": 24,
        "classification": "ELEVATED",
        "wildlife_assessments": [
            "Behaviour may be consistent with passive observation.",
            "The subject maintained a strategically useful position.",
            "Routine biological explanations remain possible.",
            "Movement patterns resemble previously documented activity.",
        ],
        "anomaly_assessments": [
            "The incident strengthens an emerging pattern.",
            "A wildlife connection cannot be ruled out.",
            "The report is compatible with the current working model.",
            "The event warrants comparison with recent field observations.",
        ],
        "notes": [
            "Previous assumptions are being reviewed.",
            "The relationship between incidents is becoming difficult to dismiss.",
            "Correlation has increased beyond the expected baseline.",
            "Independent classification of these events may no longer be appropriate.",
        ],
        "confidence_range": (62, 80),
    },
    {
        "maximum_report": 30,
        "classification": "RESTRICTED",
        "wildlife_assessments": [
            "Activity may be consistent with coordinated reconnaissance.",
            "The subject appears to have been monitoring civilian movement.",
            "The reported behaviour exceeds ordinary wildlife parameters.",
            "The subject's operational purpose remains unclear.",
        ],
        "anomaly_assessments": [
            "The incident may form part of a wider observation network.",
            "Current findings support the agency's revised hypothesis.",
            "The event is compatible with coordinated field activity.",
            "Connections to recurring wildlife observations are under review.",
        ],
        "notes": [
            "Existing biological models are under review.",
            "Civilian explanations account for fewer observed variables.",
            "The agency no longer considers each incident independently.",
            "Standard wildlife classification may be obscuring the pattern.",
        ],
        "confidence_range": (75, 90),
    },
    {
        "maximum_report": 10_000,
        "classification": "PRIORITY",
        "wildlife_assessments": [
            "Observed behaviour is consistent with field surveillance.",
            "The entity should not be approached without documentation.",
            "The subject's operational purpose remains undisclosed.",
            "Classification as ordinary wildlife cannot be assumed.",
        ],
        "anomaly_assessments": [
            "The incident supports the consolidated surveillance hypothesis.",
            "The relationship to observed goose activity is considered significant.",
            "The agency's revised model remains the leading explanation.",
            "The event aligns with the current cross-species assessment framework.",
        ],
        "notes": [
            "Conventional ornithological explanations remain incomplete.",
            "The public understanding of geese may require revision.",
            "The agency regrets dismissing the earlier reports.",
            "Classification as ordinary wildlife is no longer automatic.",
            "Questions regarding biological status have been referred upward.",
            "The absence of evidence is no longer considered reassuring.",
        ],
        "confidence_range": (86, 98),
    },
]


# ============================================================
# STATE
#
# This remembers:
# - the latest report number
# - links already used
# - the last category posted
# ============================================================

def default_state() -> dict[str, Any]:
    return {
        "report_number": 0,
        "seen_links": [],
        "last_category": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return default_state()

    try:
        with STATE_FILE.open("r", encoding="utf-8") as file:
            saved_state = json.load(file)
    except (OSError, json.JSONDecodeError):
        print("Warning: state.json could not be read. Using a new state.")
        return default_state()

    state = default_state()
    state.update(saved_state)

    state["report_number"] = int(state.get("report_number", 0))
    state["seen_links"] = list(state.get("seen_links", []))

    return state


def save_state(state: dict[str, Any]) -> None:
    # Only retain the most recent 1,500 links.
    state["seen_links"] = state["seen_links"][-1500:]

    with STATE_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            state,
            file,
            indent=2,
            ensure_ascii=False,
        )


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_html_text(value: str, maximum_length: int = 230) -> str:
    """Remove HTML, decode entities and restrict text length."""

    without_tags = re.sub(r"<[^>]+>", " ", value)
    decoded = html.unescape(without_tags)
    cleaned = " ".join(decoded.split())

    if len(cleaned) <= maximum_length:
        return cleaned

    return cleaned[: maximum_length - 1].rstrip() + "…"


def is_blocked(title: str) -> bool:
    title_lower = title.lower()

    all_restricted_terms = BLOCKED_TERMS + SENSITIVE_TERMS

    return any(term in title_lower for term in all_restricted_terms)


# ============================================================
# RSS COLLECTION
# ============================================================

def fetch_feed(feed_url: str) -> Any:
    """Download an RSS feed with a clear user agent."""

    response = requests.get(
        feed_url,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()

    return feedparser.parse(response.content)


def collect_candidates(seen_links: set[str]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []

    for source in FEEDS:
        try:
            parsed_feed = fetch_feed(source["url"])
        except requests.RequestException as error:
            print(f"Warning: could not fetch {source['name']}: {error}")
            continue

        if getattr(parsed_feed, "bozo", False):
            print(
                f"Warning: {source['name']} returned imperfect RSS data."
            )

        for entry in parsed_feed.entries[:ITEMS_PER_FEED]:
            title = clean_html_text(
                str(entry.get("title", "Untitled report"))
            )
            link = str(entry.get("link", "")).strip()

            if not link:
                continue

            if link in seen_links:
                continue

            if is_blocked(title):
                continue

            candidates.append(
                {
                    "title": title,
                    "link": link,
                    "source": source["name"],
                    "category": source["category"],
                }
            )

    random.shuffle(candidates)
    return candidates


# ============================================================
# SELECTION
#
# Prefer the opposite category from the previous report.
# This produces a wildlife/anomaly rhythm without being rigid.
# ============================================================

def select_candidate(
    candidates: list[dict[str, str]],
    last_category: str | None,
) -> dict[str, str] | None:
    if not candidates:
        return None

    preferred_category = None

    if last_category == "wildlife":
        preferred_category = "anomaly"
    elif last_category == "anomaly":
        preferred_category = "wildlife"

    if preferred_category:
        preferred_candidates = [
            candidate
            for candidate in candidates
            if candidate["category"] == preferred_category
        ]

        if preferred_candidates:
            return random.choice(preferred_candidates)

    return random.choice(candidates)


# ============================================================
# REPORT GENERATION
# ============================================================

def get_phase(report_number: int) -> dict[str, Any]:
    for phase in PHASES:
        if report_number <= phase["maximum_report"]:
            return phase

    return PHASES[-1]
    
def confidence_label(confidence: int) -> str:
    if confidence < 40:
        return "LOW"

    if confidence < 60:
        return "LIMITED"

    if confidence < 75:
        return "MODERATE"

    if confidence < 88:
        return "HIGH"

    return "ELEVATED"

def format_report(
    item: dict[str, str],
    report_number: int,
) -> str:
    phase = get_phase(report_number)

    if item["category"] == "wildlife":
        assessment = random.choice(
            phase["wildlife_assessments"]
        )
    else:
        assessment = random.choice(
            phase["anomaly_assessments"]
        )

    editorial_note = random.choice(
        phase["notes"]
    )

    confidence = random.randint(
        phase["confidence_range"][0],
        phase["confidence_range"][1],
    )

    confidence_text = confidence_label(confidence)

    timestamp = datetime.now(timezone.utc).strftime(
        "%d %b %Y · %H:%M UTC"
    ).upper()

    classification = phase["classification"]

    if classification == "PUBLIC":
        monitoring_status = "ROUTINE MONITORING"

    elif classification == "MONITOR":
        monitoring_status = "ACTIVE MONITORING"

    elif classification == "ELEVATED":
        monitoring_status = "ELEVATED REVIEW"

    elif classification == "RESTRICTED":
        monitoring_status = "RESTRICTED ASSESSMENT"

    else:
        monitoring_status = "PRIORITY MONITORING"

    return (
        f"OSIMU LIVE MONITORING BULLETIN\n"
        f"REPORT {report_number:03d} · {timestamp}\n\n"

        f"STATUS\n"
        f"{monitoring_status}\n\n"

        f"SOURCE DESK\n"
        f"{item['source']}\n\n"

        f"DEVELOPING REPORT\n"
        f"{item['title']}\n\n"

        f"INITIAL ASSESSMENT\n"
        f"{assessment}\n\n"

        f"ANALYTICAL CONFIDENCE\n"
        f"{confidence}% · {confidence_text}\n\n"

        f"EDITORIAL NOTE\n"
        f"{editorial_note}\n\n"

        f"OPEN-SOURCE RECORD\n"
        f"{item['link']}"
    )

# ============================================================
# TELEGRAM
# ============================================================

def send_telegram_message(message: str) -> None:
    endpoint = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_TOKEN}/sendMessage"
    )

    response = requests.post(
        endpoint,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "disable_web_page_preview": True,
        },
        timeout=30,
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram rejected the message: {result}"
        )


# ============================================================
# RUNNER
# ============================================================

def run(post_count: int) -> None:
    state = load_state()
    seen_links = set(state["seen_links"])

    sent_count = 0

    while sent_count < post_count:
        candidates = collect_candidates(seen_links)

        selected_item = select_candidate(
            candidates,
            state.get("last_category"),
        )

        if selected_item is None:
            print(
                "No unseen eligible RSS entries are currently available."
            )
            break

        next_report_number = state["report_number"] + 1

        message = format_report(
            selected_item,
            next_report_number,
        )

        # Only update the state after Telegram confirms success.
        send_telegram_message(message)

        state["report_number"] = next_report_number
        state["seen_links"].append(selected_item["link"])
        state["last_category"] = selected_item["category"]

        seen_links.add(selected_item["link"])
        save_state(state)

        sent_count += 1

        print(
            f"Sent report #{next_report_number}: "
            f"{selected_item['title']}"
        )

        if sent_count < post_count:
            time.sleep(SEED_DELAY_SECONDS)

    print(f"Completed. Reports sent: {sent_count}")


def get_requested_post_count() -> int:
    if "--seed" not in sys.argv:
        return POSTS_PER_RUN

    seed_index = sys.argv.index("--seed")

    try:
        requested_count = int(sys.argv[seed_index + 1])
    except (IndexError, ValueError):
        raise SystemExit(
            "Invalid seed command. Use: python rss_bot.py --seed 30"
        )

    if requested_count < 1 or requested_count > 60:
        raise SystemExit(
            "Seed count must be between 1 and 60."
        )

    return requested_count


if __name__ == "__main__":
    number_of_posts = get_requested_post_count()
    run(number_of_posts)
