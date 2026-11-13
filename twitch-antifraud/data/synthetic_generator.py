import random
import uuid
from datetime import datetime, timedelta
from data.schema import ViewerSession

def lognormal_watch_time(mu=4.0, sigma=1.0):
    return int(random.lognormvariate(mu, sigma))

def make_organic_session(channel_id, stream_id):
    watch = lognormal_watch_time(mu=4.2, sigma=1.1)
    enter = datetime.utcnow() - timedelta(seconds=watch + random.randint(0, 3600))
    return ViewerSession(
        session_id=str(uuid.uuid4()), channel_id=channel_id,
        stream_id=stream_id, viewer_id=f"user_{uuid.uuid4().hex[:12]}",
        account_age_days=random.randint(30, 3000),
        account_follows=random.randint(1, 500),
        account_subscriptions=random.choices([0, 1, 2, 3], weights=[60, 25, 10, 5])[0],
        account_transactions=random.choices([0, 1, 2, 5], weights=[70, 15, 10, 5])[0],
        ip_hash=uuid.uuid4().hex,
        ip_asn_type=random.choices(["residential", "mobile", "datacenter", "vpn"], weights=[75, 15, 5, 5])[0],
        geo_country=random.choice(["US", "DE", "BR", "KR", "RU", "IN"]),
        geo_region=random.choice(["A", "B", "C", "D"]),
        timezone=random.choice(["America/New_York", "Europe/Berlin"]),
        locale=random.choice(["en-US", "de-DE"]),
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        ja3_fingerprint=uuid.uuid4().hex[:32],
        canvas_hash=uuid.uuid4().hex[:16],
        webgl_vendor=random.choice(["Intel Inc.", "NVIDIA Corporation"]),
        platform=random.choice(["Win32", "MacIntel", "Linux x86_64"]),
        enter_ts=enter, exit_ts=enter + timedelta(seconds=watch),
        watch_seconds=watch, rebuffer_events=random.randint(0, 5),
        quality_changes=random.randint(0, 4), fullscreen_events=random.randint(0, 3),
        mouse_events=random.randint(50, 800), keyboard_events=random.randint(0, 100),
        tab_blur_events=random.randint(0, 8),
        chat_messages=random.choices([0, 1, 2, 5, 10], weights=[50, 25, 15, 8, 2])[0],
    )

def make_bot_session(channel_id, stream_id, bot_type="naive"):
    if bot_type == "naive":
        watch = random.randint(1800, 2400)
        mouse, keyboard, blur = 0, 0, 0
        asn = "datacenter"
        age = random.randint(0, 30); follows = 0
    elif bot_type == "ai_enhanced":
        watch = random.randint(600, 3600)
        mouse = random.randint(10, 100); keyboard = 0
        blur = random.randint(0, 1)
        asn = random.choices(["datacenter", "vpn", "residential"], weights=[50, 30, 20])[0]
        age = random.randint(0, 60); follows = random.randint(0, 5)
    else:
        watch = random.randint(1200, 5400)
        mouse = random.randint(30, 200); keyboard = random.randint(0, 20)
        blur = random.randint(0, 3)
        asn = random.choice(["residential", "vpn"])
        age = random.randint(90, 800); follows = random.randint(1, 20)
        
    enter = datetime.utcnow() - timedelta(seconds=watch + random.randint(0, 60))
    return ViewerSession(
        session_id=str(uuid.uuid4()), channel_id=channel_id,
        stream_id=stream_id, viewer_id=f"bot_{uuid.uuid4().hex[:12]}",
        account_age_days=age, account_follows=follows,
        account_subscriptions=0, account_transactions=0,
        ip_hash=uuid.uuid4().hex, ip_asn_type=asn,
        geo_country=random.choice(["US", "DE", "IN", "PH", "RO"]),
        geo_region="X", timezone="America/New_York", locale="en-US",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        ja3_fingerprint="shared_" + uuid.uuid4().hex[:8],
        canvas_hash="shared_" + uuid.uuid4().hex[:8],
        webgl_vendor="Google Inc.", platform="Win32",
        enter_ts=enter, exit_ts=enter + timedelta(seconds=watch),
        watch_seconds=watch, rebuffer_events=random.randint(0, 1),
        quality_changes=random.randint(0, 1), fullscreen_events=0,
        mouse_events=mouse, keyboard_events=keyboard,
        tab_blur_events=blur, chat_messages=0,
    )
