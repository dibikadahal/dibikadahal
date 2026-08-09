#!/usr/bin/env python3
"""
Generates assets/snake.svg -- an animated snake that pathfinds through your
real contribution calendar, eating every filled square once.

Standard library only. Requires GITHUB_TOKEN and GH_LOGIN env vars, same as
generate_streak.py (both are provided automatically inside the Actions workflow).
"""
import json
import os
import urllib.request
from datetime import datetime, timezone, timedelta

TOKEN = os.environ["GITHUB_TOKEN"]
LOGIN = os.environ["GH_LOGIN"]

now = datetime.now(timezone.utc)
to_dt = now.replace(hour=23, minute=59, second=59, microsecond=0)
from_dt = (to_dt - timedelta(days=364)).replace(hour=0, minute=0, second=0)

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
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


def fetch_calendar():
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
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def nearest_neighbor_tour(apples, start):
    remaining = set(apples)
    current = min(remaining, key=lambda p: manhattan(start, p))
    tour = [current]
    remaining.discard(current)
    while remaining:
        nxt = min(remaining, key=lambda p: manhattan(current, p))
        tour.append(nxt)
        remaining.discard(nxt)
        current = nxt
    return tour


def step_path(a, b):
    path = []
    x, y = a
    tx, ty = b
    while x != tx:
        x += 1 if tx > x else -1
        path.append((x, y))
    while y != ty:
        y += 1 if ty > y else -1
        path.append((x, y))
    return path


def build_path(apples, start=(0, 0)):
    tour = nearest_neighbor_tour(apples, start)
    full_path = [start]
    eat_index = {}
    cur = start
    for target in tour:
        seg = step_path(cur, target)
        full_path.extend(seg)
        cur = target
        eat_index[target] = len(full_path) - 1
    return full_path, eat_index


def level_color(count):
    EMPTY = "#161b22"
    LEVELS = ["#0e4429", "#006d32", "#26a641", "#39d353"]
    if count == 0:
        return EMPTY
    if count <= 1:
        return LEVELS[0]
    if count <= 3:
        return LEVELS[1]
    if count <= 6:
        return LEVELS[2]
    return LEVELS[3]


def render_svg(weeks_data, full_path, eat_index):
    WEEKS = len(weeks_data)
    DAYS = 7
    grid_count = {}
    for w, week in enumerate(weeks_data):
        for d, day in enumerate(week["contributionDays"]):
            grid_count[(w, d)] = day["contributionCount"]

    CELL, GAP = 10, 3
    PITCH = CELL + GAP
    PAD = 24
    TITLEBAR_H = 34
    grid_w = WEEKS * PITCH - GAP
    grid_h = DAYS * PITCH - GAP
    W = grid_w + PAD * 2
    H = TITLEBAR_H + grid_h + PAD * 2

    BG, TITLEBAR, BORDER = "#0d1117", "#161b22", "#30363d"
    EMPTY = "#161b22"
    SNAKE_COLOR = "#58a6ff"
    SEGMENTS = 4
    TOTAL_DUR = 18.0
    STEP_DUR = TOTAL_DUR / max(len(full_path) - 1, 1)

    def cell_xy(w, d):
        return PAD + w * PITCH, TITLEBAR_H + PAD + d * PITCH

    svg = []
    svg.append(f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="Helvetica, Arial, sans-serif">')
    svg.append(f'<defs><clipPath id="snakeRound"><rect x="0" y="0" width="{W}" height="{H}" rx="10" ry="10"/></clipPath></defs>')
    svg.append('<g clip-path="url(#snakeRound)">')
    svg.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{BG}"/>')
    svg.append(f'<rect x="0" y="0" width="{W}" height="{TITLEBAR_H}" fill="{TITLEBAR}"/>')
    svg.append(f'<line x1="0" y1="{TITLEBAR_H}" x2="{W}" y2="{TITLEBAR_H}" stroke="{BORDER}"/>')
    for cx in [20, 38, 56]:
        svg.append(f'<circle cx="{cx}" cy="{TITLEBAR_H/2}" r="5.5" fill="#6e7681"/>')
    svg.append(f'<text x="{W/2}" y="{TITLEBAR_H/2+4}" text-anchor="middle" fill="#8b949e" font-size="11">contribution snake</text>')
    svg.append(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="10" ry="10" fill="none" stroke="{BORDER}"/>')

    for w in range(WEEKS):
        for d in range(DAYS):
            count = grid_count.get((w, d), 0)
            x, y = cell_xy(w, d)
            color = level_color(count)
            if count > 0 and (w, d) in eat_index:
                eat_t = eat_index[(w, d)] * STEP_DUR
                svg.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{color}">'
                           f'<animate attributeName="fill" to="{EMPTY}" begin="{eat_t:.2f}s" dur="0.3s" fill="freeze"/></rect>')
            else:
                svg.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{color}"/>')

    for i in range(SEGMENTS):
        xs = ';'.join(str(cell_xy(w, d)[0]) for (w, d) in full_path)
        ys = ';'.join(str(cell_xy(w, d)[1]) for (w, d) in full_path)
        keytimes = ';'.join(f'{j/(len(full_path)-1):.5f}' for j in range(len(full_path)))
        begin = i * STEP_DUR
        opacity = 1 - i * 0.12
        x0, y0 = cell_xy(*full_path[0])
        svg.append(f'<rect x="{x0}" y="{y0}" width="{CELL}" height="{CELL}" rx="3" fill="{SNAKE_COLOR}" opacity="{opacity:.2f}">'
                   f'<animate attributeName="x" values="{xs}" keyTimes="{keytimes}" dur="{TOTAL_DUR}s" begin="{begin:.2f}s" calcMode="discrete" fill="freeze"/>'
                   f'<animate attributeName="y" values="{ys}" keyTimes="{keytimes}" dur="{TOTAL_DUR}s" begin="{begin:.2f}s" calcMode="discrete" fill="freeze"/>'
                   f'</rect>')

    svg.append('</g></svg>')
    return ''.join(svg)


def main():
    weeks_data = fetch_calendar()
    apples = []
    for w, week in enumerate(weeks_data):
        for d, day in enumerate(week["contributionDays"]):
            if day["contributionCount"] > 0:
                apples.append((w, d))

    if not apples:
        print("no contributions in range, skipping snake generation")
        return

    full_path, eat_index = build_path(apples, start=(0, 0))
    svg = render_svg(weeks_data, full_path, eat_index)

    os.makedirs("assets", exist_ok=True)
    with open("assets/snake.svg", "w") as f:
        f.write(svg)
    print(f"apples={len(apples)} path_steps={len(full_path)}")


if __name__ == "__main__":
    main()
