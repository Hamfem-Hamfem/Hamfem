import feedparser
import requests
import urllib.parse
import re
import json
import os
from datetime import datetime, timezone


# ============================================================
# CONFIGURATION
# ============================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL = "@hamfemalert"

MAX_POSTS_PER_RUN = 5
SEEN_FILE = "posted_jobs.json"


# ============================================================
# SEARCH TOPICS
# ============================================================

SEARCHES = [
    "graduate trainee Nigeria jobs",
    "graduate jobs Nigeria",
    "entry level jobs Nigeria",
    "surveying jobs Nigeria",
    "surveyor jobs Nigeria",
    "GIS jobs Nigeria",
    "geomatics jobs Nigeria",
    "remote sensing jobs Nigeria",
    "geospatial jobs Nigeria",
    "NYSC jobs Nigeria",
    "NYSC placement Nigeria",
    "graduate trainee Lagos",
    "graduate trainee Abuja",
    "graduate trainee Ogun",
]


# ============================================================
# INCLUDE KEYWORDS
# ============================================================

INCLUDE_KEYWORDS = [
    "graduate",
    "graduate trainee",
    "trainee",
    "entry level",
    "entry-level",
    "surveyor",
    "surveying",
    "geomatics",
    "gis",
    "geospatial",
    "remote sensing",
    "cartography",
    "mapping",
    "nysc",
    "internship",
    "intern",
    "engineering",
    "construction",
]


# ============================================================
# EXCLUDE KEYWORDS
# ============================================================

EXCLUDE_KEYWORDS = [
    "senior director",
    "chief executive",
    "professor",
    "politics",
    "celebrity",
]


# ============================================================
# GOOGLE NEWS RSS
# ============================================================

def get_rss_url(query):

    encoded_query = urllib.parse.quote(query)

    return (
        "https://news.google.com/rss/search?"
        f"q={encoded_query}"
        "&hl=en-NG"
        "&gl=NG"
        "&ceid=NG:en"
    )


# ============================================================
# RELEVANCE FILTER
# ============================================================

def is_relevant(title, description=""):

    text = f"{title} {description}".lower()

    if not any(keyword in text for keyword in INCLUDE_KEYWORDS):
        return False

    if any(keyword in text for keyword in EXCLUDE_KEYWORDS):
        return False

    return True


# ============================================================
# COLLECT JOBS
# ============================================================

def collect_jobs():

    jobs = []

    for query in SEARCHES:

        print(f"Searching: {query}")

        try:

            feed = feedparser.parse(get_rss_url(query))

            for entry in feed.entries:

                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                description = entry.get("summary", "").strip()

                if not title or not link:
                    continue

                if is_relevant(title, description):

                    jobs.append({
                        "title": title,
                        "link": link,
                        "description": description,
                        "source_query": query,
                        "published": entry.get("published", "")
                    })

        except Exception as e:

            print(f"Error searching '{query}': {e}")

    return jobs


# ============================================================
# REMOVE DUPLICATES FROM CURRENT SEARCH
# ============================================================

def remove_duplicates(jobs):

    unique_jobs = []
    seen = set()

    for job in jobs:

        identifier = (
            job["title"].lower().strip()
            + "|"
            + job["link"].lower().strip()
        )

        if identifier not in seen:

            seen.add(identifier)
            unique_jobs.append(job)

    return unique_jobs


# ============================================================
# LOAD PERSISTENT DATABASE
# ============================================================

def load_seen_jobs():

    if not os.path.exists(SEEN_FILE):
        return set()

    try:

        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))

    except Exception as e:

        print(f"Could not load database: {e}")
        return set()


# ============================================================
# SAVE DATABASE
# ============================================================

def save_seen_jobs(seen_jobs):

    with open(SEEN_FILE, "w", encoding="utf-8") as f:

        json.dump(
            sorted(list(seen_jobs)),
            f,
            indent=2
        )


# ============================================================
# CREATE JOB ID
# ============================================================

def job_id(job):

    return (
        job["title"].lower().strip()
        + "|"
        + job["link"].lower().strip()
    )


# ============================================================
# CLEAN DESCRIPTION
# ============================================================

def clean_description(description):

    description = re.sub(
        r"<[^>]+>",
        "",
        description
    )

    description = re.sub(
        r"\s+",
        " ",
        description
    )

    description = description.strip()

    if len(description) > 500:
        description = description[:500] + "..."

    return description


# ============================================================
# FORMAT TELEGRAM MESSAGE
# ============================================================

def format_job(job):

    title = job["title"]
    description = clean_description(
        job["description"]
    )

    published = job.get("published", "")

    message = f"""🚨 JOB OPPORTUNITY

📌 {title}

{description}

🔗 APPLY / VIEW:
{job["link"]}

🕒 Published:
{published if published else "Recently discovered"}

━━━━━━━━━━━━━━━━━━
📢 HAMFEM ALERT
👉 @hamfemalert

#NigeriaJobs #GraduateJobs #HamfemAlert
"""

    return message


# ============================================================
# SEND TO TELEGRAM
# ============================================================

def send_to_telegram(text):

    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    data = {
        "chat_id": CHANNEL,
        "text": text,
        "disable_web_page_preview": False
    }

    response = requests.post(
        url,
        data=data,
        timeout=30
    )

    return response.json()


# ============================================================
# PUBLISH NEW JOBS
# ============================================================

def publish_new_jobs(jobs, seen_jobs):

    posted = 0

    for job in jobs:

        identifier = job_id(job)

        # Already posted
        if identifier in seen_jobs:
            continue

        message = format_job(job)

        try:

            result = send_to_telegram(message)

            if result.get("ok"):

                seen_jobs.add(identifier)

                posted += 1

                print(
                    f"✅ Posted: {job['title']}"
                )

                if posted >= MAX_POSTS_PER_RUN:
                    break

            else:

                print(
                    f"❌ Telegram error: {result}"
                )

        except Exception as e:

            print(
                f"❌ Posting error: {e}"
            )

    return posted


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN:

        raise ValueError(
            "BOT_TOKEN environment variable is missing."
        )

    print("=" * 60)
    print("LABRIGHTBOT STARTED")
    print("=" * 60)

    print(
        "Time:",
        datetime.now(timezone.utc).isoformat()
    )

    # Load previous database

    seen_jobs = load_seen_jobs()

    print(
        f"Previously posted jobs: {len(seen_jobs)}"
    )

    # Collect

    jobs = collect_jobs()

    print(
        f"\nCollected: {len(jobs)}"
    )

    # Remove duplicates

    jobs = remove_duplicates(jobs)

    print(
        f"After duplicate removal: {len(jobs)}"
    )

    # Publish

    posted = publish_new_jobs(
        jobs,
        seen_jobs
    )

    # Save database

    save_seen_jobs(seen_jobs)

    print(
        f"\nPublished this run: {posted}"
    )

    print(
        f"Total database records: {len(seen_jobs)}"
    )

    print("=" * 60)
    print("LABRIGHTBOT FINISHED")
    print("=" * 60)


if __name__ == "__main__":
    main()
