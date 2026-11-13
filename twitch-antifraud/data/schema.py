from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ViewerSession:
    session_id: str
    channel_id: str
    stream_id: str
    viewer_id: str
    account_age_days: int
    account_follows: int
    account_subscriptions: int
    account_transactions: int
    ip_hash: str
    ip_asn_type: str
    geo_country: str
    geo_region: str
    timezone: str
    locale: str
    user_agent: str
    ja3_fingerprint: str
    canvas_hash: str
    webgl_vendor: str
    platform: str
    enter_ts: datetime
    exit_ts: datetime
    watch_seconds: int
    rebuffer_events: int
    quality_changes: int
    fullscreen_events: int
    mouse_events: int
    keyboard_events: int
    tab_blur_events: int
    chat_messages: int
    chat_message_texts: list = field(default_factory=list)
