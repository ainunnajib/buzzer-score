#!/usr/bin/env python3
"""
🐝 Buzzer Score — Deteksi Akun Buzzer Twitter Indonesia
========================================================

Analisis probabilitas akun buzzer Twitter/X Indonesia berdasarkan 9 sinyal perilaku.

Usage:
    python buzzer_score.py @username
    python buzzer_score.py @user1 @user2 @user3
    python buzzer_score.py --batch accounts.txt
    python buzzer_score.py @username --json
    python buzzer_score.py @username --csv

Environment:
    TWITTER_BEARER_TOKEN  — Twitter API v2 Bearer Token

Author: AI-Noon (https://github.com/ainunnajib)
License: MIT
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from io import StringIO

try:
    import tweepy
except ImportError:
    print("Error: tweepy is required. Install with: pip install tweepy")
    sys.exit(1)


# ─── Constants ───────────────────────────────────────────────────────────────

VERSION = "1.0.0"

# Classification thresholds
CLASSIFICATIONS = [
    (75, "🚨", "HIGHLY LIKELY BUZZER", "\033[91m"),  # Red
    (50, "⚠️",  "PROBABLE BUZZER",      "\033[93m"),  # Yellow
    (30, "🔍", "SUSPICIOUS",           "\033[33m"),  # Orange
    (15, "🟡", "LOW RISK",             "\033[37m"),  # Gray
    (0,  "✅", "CLEAN",                "\033[92m"),  # Green
]

# Indonesian political keywords for hashtag/content detection
POLITICAL_PATTERNS = [
    r"pilpres", r"pilkada", r"capres", r"cawapres", r"pemilu",
    r"ganti\w*", r"lawan\w*", r"tolak\w*", r"dukung\w*",
    r"coblos", r"relawan", r"timses", r"koalisi",
    # Major party names
    r"pdip", r"gerindra", r"golkar", r"nasdem", r"demokrat",
    r"pks", r"pkb", r"ppp", r"psi", r"perindo", r"hanura",
    # Common political terms
    r"anies", r"prabowo", r"ganjar", r"jokowi", r"megawati",
    r"nkri", r"pancasila", r"reformasi",
    r"kpu", r"bawaslu", r"pilkadaserentak",
]

# Compile regex once
POLITICAL_RE = re.compile(
    r"\b(" + "|".join(POLITICAL_PATTERNS) + r")\b",
    re.IGNORECASE
)

# ANSI color codes
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE = "\033[94m"
C_CYAN = "\033[96m"
C_WHITE = "\033[97m"
C_GRAY = "\033[90m"


# ─── Signal Definitions ─────────────────────────────────────────────────────

SIGNALS = {
    "age_activity":   {"name": "Account Age vs Activity",    "max": 15, "emoji": "📅"},
    "ff_ratio":       {"name": "Follower/Following Ratio",   "max": 15, "emoji": "👥"},
    "tweet_volume":   {"name": "Tweet Volume",               "max": 10, "emoji": "📊"},
    "engagement":     {"name": "Engagement Ratio",           "max": 15, "emoji": "💬"},
    "rt_ratio":       {"name": "Retweet Ratio",              "max": 10, "emoji": "🔄"},
    "pol_hashtags":   {"name": "Political Hashtag Density",  "max": 10, "emoji": "🏷️"},
    "profile":        {"name": "Profile Completeness",       "max": 10, "emoji": "👤"},
    "repetition":     {"name": "Content Repetition",         "max": 10, "emoji": "📝"},
    "listed":         {"name": "Listed Count",               "max":  5, "emoji": "📋"},
}


# ─── Twitter API Client ─────────────────────────────────────────────────────

def create_client(bearer_token: str) -> tweepy.Client:
    """Create an authenticated tweepy Client."""
    return tweepy.Client(
        bearer_token=bearer_token,
        wait_on_rate_limit=True,  # Auto-sleep on 429
    )


def fetch_user(client: tweepy.Client, username: str) -> dict:
    """
    Fetch user profile and recent tweets.
    Returns a dict with all data needed for scoring.
    """
    username = username.lstrip("@")

    # Fetch user profile
    try:
        user_resp = client.get_user(
            username=username,
            user_fields=[
                "created_at", "description", "public_metrics",
                "profile_image_url", "verified", "protected"
            ]
        )
    except tweepy.TooManyRequests:
        print(f"{C_RED}Rate limited. Waiting 60s...{C_RESET}")
        time.sleep(60)
        return fetch_user(client, username)
    except tweepy.errors.NotFound:
        return {"error": f"User @{username} not found"}
    except tweepy.errors.Forbidden:
        return {"error": f"User @{username} is suspended or restricted"}
    except Exception as e:
        return {"error": f"API error for @{username}: {str(e)}"}

    if not user_resp.data:
        return {"error": f"User @{username} not found"}

    user = user_resp.data
    metrics = user.public_metrics or {}

    # Check if protected
    if user.protected:
        return {
            "error": f"User @{username} is protected (private account)",
            "username": username,
            "name": user.name,
        }

    # Calculate account age
    created = user.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    age_days = max((now - created).days, 1)

    # Fetch recent tweets (up to 100)
    tweets = []
    try:
        tweets_resp = client.get_users_tweets(
            id=user.id,
            max_results=100,
            tweet_fields=["public_metrics", "referenced_tweets", "text", "entities"],
            exclude=None,  # Include RTs
        )
        if tweets_resp.data:
            tweets = tweets_resp.data
    except tweepy.TooManyRequests:
        print(f"{C_YELLOW}Rate limited on tweets. Waiting 60s...{C_RESET}")
        time.sleep(60)
        try:
            tweets_resp = client.get_users_tweets(
                id=user.id, max_results=100,
                tweet_fields=["public_metrics", "referenced_tweets", "text", "entities"],
            )
            if tweets_resp.data:
                tweets = tweets_resp.data
        except Exception:
            pass
    except Exception:
        pass

    # Analyze tweets
    rt_count = 0
    total_likes = 0
    total_rts = 0
    texts = []
    political_count = 0
    sample_size = len(tweets) if tweets else 0

    for tweet in tweets:
        text = tweet.text or ""
        tweet_metrics = tweet.public_metrics or {}

        # Check if it's a retweet
        is_rt = False
        if tweet.referenced_tweets:
            for ref in tweet.referenced_tweets:
                if ref.type == "retweeted":
                    is_rt = True
                    break
        if text.startswith("RT @"):
            is_rt = True

        if is_rt:
            rt_count += 1

        # Engagement
        total_likes += tweet_metrics.get("like_count", 0)
        total_rts += tweet_metrics.get("retweet_count", 0)

        # Content for repetition analysis (only non-RTs)
        if not is_rt:
            # Normalize text: remove URLs, mentions, extra whitespace
            clean = re.sub(r"https?://\S+", "", text)
            clean = re.sub(r"@\w+", "", clean).strip()
            if len(clean) > 10:
                texts.append(clean.lower())

        # Political hashtags
        political_count += len(POLITICAL_RE.findall(text))
        # Also check hashtag entities
        if tweet.entities and "hashtags" in tweet.entities:
            for ht in tweet.entities["hashtags"]:
                tag = ht.get("tag", "").lower()
                if POLITICAL_RE.match(tag):
                    political_count += 1

    # Calculate derived metrics
    tweet_count = metrics.get("tweet_count", 0)
    followers = metrics.get("followers_count", 0)
    following = metrics.get("following_count", 0)
    listed_count = metrics.get("listed_count", 0)
    tweets_per_day = tweet_count / age_days if age_days > 0 else 0

    avg_likes = total_likes / sample_size if sample_size > 0 else 0
    avg_rts_per_tweet = total_rts / sample_size if sample_size > 0 else 0
    rt_pct = (rt_count / sample_size * 100) if sample_size > 0 else 0

    # Repetition: % of duplicate texts in non-RT sample
    dup_pct = 0
    if len(texts) > 1:
        counter = Counter(texts)
        duplicated = sum(c - 1 for c in counter.values() if c > 1)
        dup_pct = (duplicated / len(texts)) * 100

    # Normalize political count to per-20-tweets basis
    pol_per_20 = (political_count / sample_size * 20) if sample_size > 0 else 0

    # Profile flags
    profile_image = user.profile_image_url or ""
    has_default_avatar = "default_profile" in profile_image or "_normal." not in profile_image
    has_no_bio = not (user.description and user.description.strip())
    has_generic_username = bool(re.match(r"^[a-z]*\d{6,}$", username.lower()))

    return {
        "username": username,
        "name": user.name,
        "bio": user.description or "",
        "created_at": created.isoformat(),
        "age_days": age_days,
        "followers": followers,
        "following": following,
        "tweet_count": tweet_count,
        "listed_count": listed_count,
        "tweets_per_day": round(tweets_per_day, 2),
        "sample_size": sample_size,
        "avg_likes": round(avg_likes, 2),
        "avg_rts": round(avg_rts_per_tweet, 2),
        "rt_pct": round(rt_pct, 1),
        "dup_pct": round(dup_pct, 1),
        "pol_per_20": round(pol_per_20, 2),
        "has_default_avatar": has_default_avatar,
        "has_no_bio": has_no_bio,
        "has_generic_username": has_generic_username,
        "verified": user.verified or False,
    }


# ─── Scoring Engine ─────────────────────────────────────────────────────────

def score_account(data: dict) -> dict:
    """
    Score an account based on 9 signals.
    Returns the data dict augmented with scoring results.
    """
    if "error" in data and "username" not in data:
        return data

    signals = []
    total_score = 0
    max_score = 0

    age_days = data.get("age_days", 999)
    tweets_per_day = data.get("tweets_per_day", 0)
    followers = data.get("followers", 0)
    following = data.get("following", 0)
    tweet_count = data.get("tweet_count", 0)
    listed_count = data.get("listed_count", 0)
    avg_likes = data.get("avg_likes", 0)
    avg_rts = data.get("avg_rts", 0)
    rt_pct = data.get("rt_pct", 0)
    dup_pct = data.get("dup_pct", 0)
    pol_per_20 = data.get("pol_per_20", 0)

    # ── Signal 1: Account Age vs Activity ──
    s1 = 0
    sig1 = SIGNALS["age_activity"]
    if age_days < 180:
        if tweets_per_day > 20:
            s1 = sig1["max"]
        elif tweets_per_day > 10:
            s1 = 10
        elif tweets_per_day > 5:
            s1 = 5
    elif age_days < 365:
        if tweets_per_day > 30:
            s1 = 10
        elif tweets_per_day > 15:
            s1 = 5
    else:
        if tweets_per_day > 50:
            s1 = 8
    signals.append({
        "key": "age_activity",
        "name": sig1["name"],
        "emoji": sig1["emoji"],
        "score": s1,
        "max": sig1["max"],
        "detail": f"{age_days} days old, {tweets_per_day:.1f} tweets/day",
    })

    # ── Signal 2: Follower/Following Ratio ──
    s2 = 0
    sig2 = SIGNALS["ff_ratio"]
    ff_ratio = (following / followers) if followers > 0 else (999 if following > 100 else 0)
    if ff_ratio > 10:
        s2 = sig2["max"]
    elif ff_ratio > 5:
        s2 = 12
    elif ff_ratio > 3:
        s2 = 8
    elif ff_ratio > 2:
        s2 = 4
    signals.append({
        "key": "ff_ratio",
        "name": sig2["name"],
        "emoji": sig2["emoji"],
        "score": s2,
        "max": sig2["max"],
        "detail": f"Following:{following} Followers:{followers} Ratio:{ff_ratio:.2f}",
    })

    # ── Signal 3: Tweet Volume ──
    s3 = 0
    sig3 = SIGNALS["tweet_volume"]
    if tweets_per_day > 50:
        s3 = sig3["max"]
    elif tweets_per_day > 30:
        s3 = 7
    elif tweets_per_day > 20:
        s3 = 4
    signals.append({
        "key": "tweet_volume",
        "name": sig3["name"],
        "emoji": sig3["emoji"],
        "score": s3,
        "max": sig3["max"],
        "detail": f"{tweets_per_day:.1f} tweets/day",
    })

    # ── Signal 4: Engagement Ratio ──
    s4 = 0
    sig4 = SIGNALS["engagement"]
    if followers > 1000:
        eng_rate = ((avg_likes + avg_rts) / followers) * 100 if followers > 0 else 0
        if eng_rate < 0.01:
            s4 = sig4["max"]
        elif eng_rate < 0.05:
            s4 = 10
        elif eng_rate < 0.1:
            s4 = 5
    elif followers < 100 and tweet_count > 5000:
        s4 = 12
    signals.append({
        "key": "engagement",
        "name": sig4["name"],
        "emoji": sig4["emoji"],
        "score": s4,
        "max": sig4["max"],
        "detail": f"Avg likes:{avg_likes:.1f} RTs:{avg_rts:.1f} Followers:{followers}",
    })

    # ── Signal 5: Retweet Ratio ──
    s5 = 0
    sig5 = SIGNALS["rt_ratio"]
    if rt_pct > 90:
        s5 = sig5["max"]
    elif rt_pct > 70:
        s5 = 7
    elif rt_pct > 50:
        s5 = 4
    signals.append({
        "key": "rt_ratio",
        "name": sig5["name"],
        "emoji": sig5["emoji"],
        "score": s5,
        "max": sig5["max"],
        "detail": f"{rt_pct:.0f}% of recent tweets are RTs",
    })

    # ── Signal 6: Political Hashtag Density ──
    s6 = 0
    sig6 = SIGNALS["pol_hashtags"]
    if pol_per_20 > 3:
        s6 = sig6["max"]
    elif pol_per_20 > 1.5:
        s6 = 7
    elif pol_per_20 > 0.5:
        s6 = 3
    signals.append({
        "key": "pol_hashtags",
        "name": sig6["name"],
        "emoji": sig6["emoji"],
        "score": s6,
        "max": sig6["max"],
        "detail": f"{pol_per_20:.1f} political keywords per 20 tweets",
    })

    # ── Signal 7: Profile Completeness ──
    s7 = 0
    sig7 = SIGNALS["profile"]
    if data.get("has_default_avatar"):
        s7 += 4
    if data.get("has_no_bio"):
        s7 += 3
    if data.get("has_generic_username"):
        s7 += 3
    s7 = min(s7, sig7["max"])
    flags = []
    if data.get("has_default_avatar"):
        flags.append("default_avatar")
    if data.get("has_no_bio"):
        flags.append("no_bio")
    if data.get("has_generic_username"):
        flags.append("generic_username")
    signals.append({
        "key": "profile",
        "name": sig7["name"],
        "emoji": sig7["emoji"],
        "score": s7,
        "max": sig7["max"],
        "detail": f"Flags: {', '.join(flags) if flags else 'none'}",
    })

    # ── Signal 8: Content Repetition ──
    s8 = 0
    sig8 = SIGNALS["repetition"]
    if dup_pct > 50:
        s8 = sig8["max"]
    elif dup_pct > 30:
        s8 = 6
    elif dup_pct > 15:
        s8 = 3
    signals.append({
        "key": "repetition",
        "name": sig8["name"],
        "emoji": sig8["emoji"],
        "score": s8,
        "max": sig8["max"],
        "detail": f"{dup_pct:.0f}% duplicate content in sample",
    })

    # ── Signal 9: Listed Count ──
    s9 = 0
    sig9 = SIGNALS["listed"]
    if tweet_count > 1000 and listed_count < 5:
        s9 = sig9["max"]
    elif tweet_count > 500 and listed_count < 2:
        s9 = 3
    signals.append({
        "key": "listed",
        "name": sig9["name"],
        "emoji": sig9["emoji"],
        "score": s9,
        "max": sig9["max"],
        "detail": f"In {listed_count} lists with {tweet_count} tweets",
    })

    # ── Totals ──
    for s in signals:
        total_score += s["score"]
        max_score += s["max"]

    probability = round(total_score * 100 / max_score) if max_score > 0 else 0

    # Classification
    classification = "CLEAN"
    cls_emoji = "✅"
    for threshold, emoji, label, _ in CLASSIFICATIONS:
        if probability >= threshold:
            classification = label
            cls_emoji = emoji
            break

    data["signals"] = signals
    data["total_score"] = total_score
    data["max_score"] = max_score
    data["probability"] = probability
    data["classification"] = classification
    data["classification_emoji"] = cls_emoji

    return data


# ─── Output Formatters ──────────────────────────────────────────────────────

def bar(value: int, maximum: int, width: int = 20) -> str:
    """Render an ASCII progress bar with color."""
    if maximum == 0:
        return "░" * width
    pct = value / maximum
    filled = int(pct * width)
    empty = width - filled

    if pct >= 0.7:
        color = C_RED
    elif pct >= 0.4:
        color = C_YELLOW
    elif pct > 0:
        color = C_GREEN
    else:
        color = C_DIM

    return f"{color}{'█' * filled}{C_DIM}{'░' * empty}{C_RESET}"


def format_number(n: int) -> str:
    """Format large numbers: 1.5K, 2.3M, etc."""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def print_result(data: dict) -> None:
    """Pretty-print a single account's buzzer score to terminal."""
    if "error" in data:
        username = data.get("username", "unknown")
        print(f"\n{C_RED}  ✗ @{username}: {data['error']}{C_RESET}")
        return

    username = data["username"]
    prob = data["probability"]
    cls = data["classification"]
    cls_emoji = data["classification_emoji"]

    # Find color for classification
    cls_color = C_GREEN
    for threshold, _, label, color in CLASSIFICATIONS:
        if prob >= threshold:
            cls_color = color
            break

    print()
    print(f"  {C_BOLD}{'═' * 56}{C_RESET}")
    print(f"  {C_BOLD}{C_BLUE}@{username}{C_RESET}  {C_DIM}{data.get('name', '')}{C_RESET}")
    if data.get("bio"):
        bio = data["bio"][:60] + ("..." if len(data["bio"]) > 60 else "")
        print(f"  {C_DIM}\"{bio}\"{C_RESET}")
    print(f"  {C_DIM}{'─' * 56}{C_RESET}")

    # Metrics row
    print(f"  {C_WHITE}Followers: {C_CYAN}{format_number(data['followers'])}{C_RESET}"
          f"  {C_WHITE}Following: {C_CYAN}{format_number(data['following'])}{C_RESET}"
          f"  {C_WHITE}Tweets: {C_CYAN}{format_number(data['tweet_count'])}{C_RESET}"
          f"  {C_WHITE}Listed: {C_CYAN}{data['listed_count']}{C_RESET}")
    print(f"  {C_WHITE}Age: {C_CYAN}{data['age_days']}d{C_RESET}"
          f"  {C_WHITE}Tweets/day: {C_CYAN}{data['tweets_per_day']:.1f}{C_RESET}"
          f"  {C_WHITE}Sample: {C_CYAN}{data.get('sample_size', 0)} tweets{C_RESET}")
    print()

    # Score gauge
    print(f"  {C_BOLD}BUZZER SCORE:{C_RESET}  {cls_color}{C_BOLD}{prob}%{C_RESET}"
          f"  {cls_emoji} {cls_color}{cls}{C_RESET}"
          f"  {C_DIM}({data['total_score']}/{data['max_score']}){C_RESET}")
    print()

    # Signal breakdown
    print(f"  {C_BOLD}Signal Breakdown:{C_RESET}")
    for sig in data["signals"]:
        name = f"{sig['emoji']} {sig['name']}"
        score_str = f"{sig['score']}/{sig['max']}"
        b = bar(sig["score"], sig["max"])
        detail = sig["detail"]
        print(f"    {name:<35s} {b} {C_BLUE}{score_str:>5s}{C_RESET}  {C_DIM}{detail}{C_RESET}")

    print(f"\n  {C_BOLD}{'═' * 56}{C_RESET}\n")


def to_json_output(results: list) -> str:
    """Convert results to JSON string."""
    output = []
    for r in results:
        # Clean up for JSON — remove ANSI, keep data
        entry = {
            "username": r.get("username", "unknown"),
            "name": r.get("name", ""),
            "bio": r.get("bio", ""),
            "created_at": r.get("created_at", ""),
            "age_days": r.get("age_days", 0),
            "metrics": {
                "followers": r.get("followers", 0),
                "following": r.get("following", 0),
                "tweets": r.get("tweet_count", 0),
                "listed": r.get("listed_count", 0),
                "tweets_per_day": r.get("tweets_per_day", 0),
            },
            "sample": {
                "size": r.get("sample_size", 0),
                "avg_likes": r.get("avg_likes", 0),
                "avg_rts": r.get("avg_rts", 0),
                "rt_pct": r.get("rt_pct", 0),
                "dup_pct": r.get("dup_pct", 0),
                "political_per_20": r.get("pol_per_20", 0),
            },
            "profile_flags": {
                "default_avatar": r.get("has_default_avatar", False),
                "no_bio": r.get("has_no_bio", False),
                "generic_username": r.get("has_generic_username", False),
            },
            "buzzer_score": {
                "probability": r.get("probability", 0),
                "classification": r.get("classification", "UNKNOWN"),
                "total_score": r.get("total_score", 0),
                "max_score": r.get("max_score", 0),
                "signals": r.get("signals", []),
            },
        }
        if "error" in r:
            entry["error"] = r["error"]
        output.append(entry)

    return json.dumps(output if len(output) > 1 else output[0], indent=2, ensure_ascii=False)


def to_csv_output(results: list) -> str:
    """Convert results to CSV string."""
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "username", "name", "probability", "classification",
        "followers", "following", "tweets", "listed",
        "tweets_per_day", "age_days", "rt_pct", "dup_pct",
        "political_per_20", "total_score", "max_score",
        "s1_age_activity", "s2_ff_ratio", "s3_volume",
        "s4_engagement", "s5_rt_ratio", "s6_political",
        "s7_profile", "s8_repetition", "s9_listed",
    ])

    for r in results:
        if "error" in r and "signals" not in r:
            writer.writerow([r.get("username", "unknown"), "", "", "ERROR"] + [""] * 20)
            continue

        sig_scores = {s["key"]: s["score"] for s in r.get("signals", [])}
        writer.writerow([
            r.get("username", ""),
            r.get("name", ""),
            r.get("probability", 0),
            r.get("classification", ""),
            r.get("followers", 0),
            r.get("following", 0),
            r.get("tweet_count", 0),
            r.get("listed_count", 0),
            r.get("tweets_per_day", 0),
            r.get("age_days", 0),
            r.get("rt_pct", 0),
            r.get("dup_pct", 0),
            r.get("pol_per_20", 0),
            r.get("total_score", 0),
            r.get("max_score", 0),
            sig_scores.get("age_activity", 0),
            sig_scores.get("ff_ratio", 0),
            sig_scores.get("tweet_volume", 0),
            sig_scores.get("engagement", 0),
            sig_scores.get("rt_ratio", 0),
            sig_scores.get("pol_hashtags", 0),
            sig_scores.get("profile", 0),
            sig_scores.get("repetition", 0),
            sig_scores.get("listed", 0),
        ])

    return buf.getvalue()


# ─── Main CLI ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="🐝 Buzzer Score — Deteksi Akun Buzzer Twitter Indonesia",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python buzzer_score.py @username
  python buzzer_score.py @user1 @user2 @user3
  python buzzer_score.py --batch accounts.txt
  python buzzer_score.py @username --json
  python buzzer_score.py @username --csv

Environment:
  TWITTER_BEARER_TOKEN  Twitter API v2 Bearer Token
        """,
    )

    parser.add_argument(
        "usernames",
        nargs="*",
        help="Twitter usernames to analyze (with or without @)",
    )
    parser.add_argument(
        "--batch", "-b",
        metavar="FILE",
        help="File with one username per line",
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--csv", "-c",
        action="store_true",
        help="Output as CSV",
    )
    parser.add_argument(
        "--token", "-t",
        metavar="TOKEN",
        help="Twitter Bearer Token (overrides TWITTER_BEARER_TOKEN env var)",
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"buzzer-score {VERSION}",
    )

    args = parser.parse_args()

    # Collect usernames
    usernames = []
    for u in (args.usernames or []):
        usernames.append(u.lstrip("@"))

    if args.batch:
        try:
            with open(args.batch, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        usernames.append(line.lstrip("@"))
        except FileNotFoundError:
            print(f"{C_RED}Error: File '{args.batch}' not found{C_RESET}")
            sys.exit(1)

    if not usernames:
        parser.print_help()
        sys.exit(1)

    # Get bearer token
    bearer_token = args.token or os.environ.get("TWITTER_BEARER_TOKEN")
    if not bearer_token:
        print(f"{C_RED}Error: No Twitter Bearer Token provided.{C_RESET}")
        print(f"Set TWITTER_BEARER_TOKEN env var or use --token flag.")
        sys.exit(1)

    # Create client
    client = create_client(bearer_token)

    # Header
    if not args.json and not args.csv:
        print(f"\n  {C_BOLD}🐝 Buzzer Score v{VERSION}{C_RESET}")
        print(f"  {C_DIM}Analyzing {len(usernames)} account(s)...{C_RESET}")

    # Process each username
    results = []
    for i, username in enumerate(usernames):
        if not args.json and not args.csv:
            print(f"\n  {C_DIM}[{i+1}/{len(usernames)}] Fetching @{username}...{C_RESET}", end="", flush=True)

        data = fetch_user(client, username)
        result = score_account(data)
        results.append(result)

        if not args.json and not args.csv:
            print("\r" + " " * 60 + "\r", end="")  # Clear line
            print_result(result)

    # Output
    if args.json:
        print(to_json_output(results))
    elif args.csv:
        print(to_csv_output(results), end="")

    # Summary for multiple accounts (terminal mode)
    if not args.json and not args.csv and len(results) > 1:
        scored = [r for r in results if "probability" in r]
        if scored:
            avg = sum(r["probability"] for r in scored) / len(scored)
            buzzer_count = sum(1 for r in scored if r["probability"] >= 50)
            print(f"  {C_BOLD}Summary:{C_RESET}")
            print(f"  Analyzed: {len(scored)} accounts  |  "
                  f"Avg score: {avg:.0f}%  |  "
                  f"Probable buzzers: {C_RED}{buzzer_count}{C_RESET}")
            print()


if __name__ == "__main__":
    main()
