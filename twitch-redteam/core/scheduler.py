import csv
import random
import yaml
from behaviors.base import AgentProfile

GEO_TZ = {
    "US": ("America/New_York", "en-US"), "DE": ("Europe/Berlin", "de-DE"),
    "BR": ("America/Sao_Paulo", "pt-BR"), "KR": ("Asia/Seoul", "ko-KR"),
    "IN": ("Asia/Kolkata", "en-IN"), "PH": ("Asia/Manila", "en-PH"),
}

def load_proxies(path):
    with open(path) as f:
        return list(csv.DictReader(f))

def pick_archetype(agents_cfg, idx):
    templates = agents_cfg["templates"]
    names = list(templates.keys())
    weights = [templates[n]["weight"] for n in names]
    return random.choices(names, weights=weights)[0]

def generate_profile(agent_id, archetype, proxies):
    proxy = random.choice(proxies)
    country = proxy.get("country", "US")
    tz, locale = GEO_TZ.get(country, ("UTC", "en-US"))
    return AgentProfile(
        agent_id=agent_id, archetype=archetype,
        account_age_days=random.randint(30, 2000), account_follows=random.randint(0, 300),
        account_subscriptions=random.choice([0, 0, 0, 1]), account_transactions=0,
        timezone=tz, locale=locale, platform="Win32",
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
        proxy=proxy["url"], watch_time_target_sec=1800,
        chat_probability_per_min=0.05 if archetype == "chatter" else 0.0,
        leave_return_probability=0.15,
    )
