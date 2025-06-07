import requests
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()

region = "na1"
platform_routing = "americas"

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
            continue
        elif res.status_code != 200:
            print(f"Request failed with status {res.status_code}: {url}")
            return None
        return res.json()

def fetch_players(url):
    data = riot_get(url)
    return data.get("entries", []) if data else []

def enrich_player(entry):
    summoner_id = entry.get("summonerId")
    summoner_url = f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/{summoner_id}"
    summoner_data = riot_get(summoner_url)
    if not summoner_data:
        return None
    puuid = summoner_data.get("puuid")
    if not puuid:
        return None
    account_url = f"https://{platform_routing}.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}"
    account_data = riot_get(account_url)
    if not account_data:
        return None
    print(f"Saved {account_data.get('gameName')}#{account_data.get('tagLine')} - LP: {entry.get('leaguePoints')}")
    return {
        "summonerName": entry.get("summonerName"),
        "leaguePoints": entry.get("leaguePoints"),
        "puuid": puuid,
        "gameName": account_data.get("gameName"),
        "tagLine": account_data.get("tagLine")
    }

tier_urls = {
    "challenger": f"https://{region}.api.riotgames.com/lol/league/v4/challengerleagues/by-queue/RANKED_SOLO_5x5",
    "grandmaster": f"https://{region}.api.riotgames.com/lol/league/v4/grandmasterleagues/by-queue/RANKED_SOLO_5x5",
    "master": f"https://{region}.api.riotgames.com/lol/league/v4/masterleagues/by-queue/RANKED_SOLO_5x5"
}

all_players = []

for tier, url in tier_urls.items():
    print(f"\n🔍 Fetching {tier.capitalize()} players...")
    entries = fetch_players(url)
    print(f"Found {len(entries)} {tier} players.")
    for i, entry in enumerate(entries):
        player_data = enrich_player(entry)
        if player_data:
            all_players.append(player_data)
        time.sleep(0.1)

with open("players.json", "w") as f:
    json.dump(all_players, f, indent=2)
