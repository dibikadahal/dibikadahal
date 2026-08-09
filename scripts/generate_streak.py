#!/usr/bin/env python3
"""
Generates assets/streak.svg from live GitHub contribution data.
Uses only the Python standard library (urllib) -- no pip installs needed in CI.

Requires two environment variables (both provided automatically inside the
GitHub Actions workflow -- see .github/workflows/refresh-stats.yml):
    GITHUB_TOKEN  - the built-in Actions token, no personal token needed
    GH_LOGIN      - the repository owner's username (github.repository_owner)
"""
import json
import os
import urllib.request
from datetime import datetime, timezone, timedelta

TOKEN = os.environ["GITHUB_TOKEN"]
LOGIN = os.environ["GH_LOGIN"]

# --- window: pin to whole UTC days so two runs don't bucket differently ---
now = datetime.now(timezone.utc)
to_dt = now.replace(hour=23, minute=59, second=59, microsecond=0)
from_dt = (to_dt - timedelta(days=364)).replace(hour=0, minute=0, second=0)

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""

def fetch_contributions():
    body = json.dumps({
        "query": QUERY,
        "variables": {
            "login": LOGIN,
            "from": from_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": to_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": LOGIN,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def compute_streaks(calendar):
    days = []
    for week in calendar["weeks"]:
        for d in week["contributionDays"]:
            days.append((d["date"], d["contributionCount"]))
    days.sort(key=lambda x: x[0])

    # longest streak: sliding window over the whole fetched range
    longest = 0
    longest_start = longest_end = None
    run_start = None
    run_len = 0
    for date, count in days:
        if count > 0:
            if run_len == 0:
                run_start = date
            run_len += 1
            if run_len > longest:
                longest = run_len
                longest_start = run_start
                longest_end = date
        else:
            run_len = 0

    # current streak: walk backward from the most recent day.
    # if today has 0 contributions yet, still count the streak ending yesterday.
    current = 0
    current_start = current_end = None
    idx = len(days) - 1
    # skip a trailing "today with 0" without breaking the streak
    if days and days[idx][1] == 0:
        idx -= 1
    while idx >= 0 and days[idx][1] > 0:
        if current == 0:
            current_end = days[idx][0]
        current_start = days[idx][0]
        current += 1
        idx -= 1

    return {
        "current": current,
        "current_start": current_start,
        "current_end": current_end,
        "longest": longest,
        "longest_start": longest_start,
        "longest_end": longest_end,
    }


def fmt_date(iso_date, with_year=False):
    dt = datetime.strptime(iso_date, "%Y-%m-%d")
    return dt.strftime("%b %-d, %Y") if with_year else dt.strftime("%b %-d")


def render_svg(total, streaks):
    W, H = 700, 220
    BG, BORDER = "#0d1117", "#30363d"
    TEXT, DIM, ACCENT = "#f0f6fc", "#8b949e", "#f0883e"

    col_w = W / 3
    flame_cx, flame_cy, flame_r = W / 2, 95, 42

    current_range = ""
    if streaks["current"] > 0:
        current_range = fmt_date(streaks["current_end"] or streaks["current_start"])
    else:
        current_range = "No active streak"

    longest_range = ""
    if streaks["longest_start"]:
        longest_range = f'{fmt_date(streaks["longest_start"])} - {fmt_date(streaks["longest_end"])}'

    total_range = f'{fmt_date(from_dt.strftime("%Y-%m-%d"), with_year=True)} - Present'

    svg = f'''<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="Helvetica, Arial, sans-serif">
<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="14" ry="14" fill="{BG}" stroke="{BORDER}" stroke-width="1.5"/>
<line x1="{col_w:.1f}" y1="30" x2="{col_w:.1f}" y2="{H-30}" stroke="{BORDER}" stroke-width="1"/>
<line x1="{2*col_w:.1f}" y1="30" x2="{2*col_w:.1f}" y2="{H-30}" stroke="{BORDER}" stroke-width="1"/>

<text x="{col_w/2:.1f}" y="72" text-anchor="middle" fill="{TEXT}" font-size="34" font-weight="700">{total}</text>
<text x="{col_w/2:.1f}" y="150" text-anchor="middle" fill="{TEXT}" font-size="15">Total Contributions</text>
<text x="{col_w/2:.1f}" y="172" text-anchor="middle" fill="{DIM}" font-size="12">{total_range}</text>

<circle cx="{flame_cx:.1f}" cy="{flame_cy:.1f}" r="{flame_r}" fill="none" stroke="{ACCENT}" stroke-width="3"/>
<path d="M {flame_cx-6:.1f} {flame_cy-24:.1f}
         c 4 6 -4 10 -3 17
         c 1 5 5 7 8 4
         c 2 5 -1 9 -5 10
         c -8 2 -14 -5 -13 -13
         c 1 -8 8 -10 7 -18 z"
      fill="{ACCENT}" transform="translate(0,-6) scale(0.9)" />
<text x="{flame_cx:.1f}" y="{flame_cy+8:.1f}" text-anchor="middle" fill="{TEXT}" font-size="26" font-weight="700">{streaks['current']}</text>
<text x="{flame_cx:.1f}" y="150" text-anchor="middle" fill="{ACCENT}" font-size="15" font-weight="700">Current Streak</text>
<text x="{flame_cx:.1f}" y="172" text-anchor="middle" fill="{DIM}" font-size="12">{current_range}</text>

<text x="{2*col_w + col_w/2:.1f}" y="72" text-anchor="middle" fill="{TEXT}" font-size="34" font-weight="700">{streaks['longest']}</text>
<text x="{2*col_w + col_w/2:.1f}" y="150" text-anchor="middle" fill="{TEXT}" font-size="15">Longest Streak</text>
<text x="{2*col_w + col_w/2:.1f}" y="172" text-anchor="middle" fill="{DIM}" font-size="12">{longest_range}</text>
</svg>'''
    return svg


def main():
    calendar = fetch_contributions()
    total = calendar["totalContributions"]
    streaks = compute_streaks(calendar)
    svg = render_svg(total, streaks)
    os.makedirs("assets", exist_ok=True)
    with open("assets/streak.svg", "w") as f:
        f.write(svg)
    print(f"total={total} current={streaks['current']} longest={streaks['longest']}")


if __name__ == "__main__":
    main()
