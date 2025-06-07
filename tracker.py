import requests
import json
import time
import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv
from collections import Counter, defaultdict

if len(sys.argv) < 3:
    print("Usage: python tracker.py <LP_MIN> <LP_MAX>")
    sys.exit(1)

LP_MIN = int(sys.argv[1])
LP_MAX = int(sys.argv[2])

load_dotenv()

platform_routing = "americas"
MATCH_COUNT = 20

API_KEYS = [
    os.getenv("RIOT_API_KEY1"),
    os.getenv("RIOT_API_KEY2"),
    os.getenv("RIOT_API_KEY3"),
    os.getenv("RIOT_API_KEY4")
]

rate_limited_until = [0, 0, 0, 0]
current_key_index = 0

def get_active_key():
    global current_key_index
    now = time.time()
    for i in range(len(API_KEYS)):
        idx = (current_key_index + i) % len(API_KEYS)
        if now >= rate_limited_until[idx]:
            current_key_index = idx
            return API_KEYS[idx]
    soonest = min(rate_limited_until)
    wait_time = max(1, soonest - now)
    print(f"🔄 All keys rate-limited. Waiting {round(wait_time)}s...")
    time.sleep(wait_time)
    return get_active_key()

def riot_get(url):
    while True:
        key = get_active_key()
        headers = {"X-Riot-Token": key}
        res = requests.get(url, headers=headers)
        if res.status_code == 429:
            retry = int(res.headers.get("Retry-After", 10))
            rate_limited_until[current_key_index] = time.time() + retry
            print(f"⛔ Key {current_key_index + 1} rate-limited. Switching (retry after {retry}s)")
            continue
        elif res.status_code != 200:
            return None
        return res.json()

with open("players.json", "r") as f:
    players = json.load(f)

for player in players:
    lp = player.get("leaguePoints")
    puuid = player.get("puuid")
    name = f'{player.get("gameName")}#{player.get("tagLine")}'

    if not (LP_MIN <= lp <= LP_MAX):
        continue

    match_ids_url = f"https://{platform_routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count={MATCH_COUNT}"
    match_ids = riot_get(match_ids_url)
    if not match_ids:
        continue

    champ_counter = Counter()
    win_counter = defaultdict(int)
    recent_game_minutes = None
    valid = False

    for i, match_id in enumerate(match_ids):
        match_url = f"https://{platform_routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        match_data = riot_get(match_url)
        if not match_data:
            continue

        info = match_data.get("info", {})
        participants = info.get("participants", [])
        player_data = next((p for p in participants if p["puuid"] == puuid), None)
        if not player_data:
            continue

        end_timestamp = info.get("gameEndTimestamp")
        if i == 0:
            now = datetime.now(timezone.utc).timestamp() * 1000
            recent_game_minutes = round((now - end_timestamp) / (1000 * 60), 1)
            if recent_game_minutes > 10:
                break
            valid = True

        champ = player_data.get("championName")
        win = player_data.get("win")

        champ_counter[champ] += 1
        if win:
            win_counter[champ] += 1

        time.sleep(0.1)

    if valid:
        print(f"\n{name} | {lp} LP")
        print(f"Last game ended {recent_game_minutes} minutes ago")
        for champ, count in champ_counter.most_common():
            wins = win_counter[champ]
            winrate = round((wins / count) * 100, 1)
            print(f"{champ}: {count}/{MATCH_COUNT} games, {winrate}% winrate")
