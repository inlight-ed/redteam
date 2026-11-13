import numpy as np
import pandas as pd
from collections import Counter
from data.schema import ViewerSession

def _gini(values):
    if not values or sum(values) == 0: return 0.0
    arr = np.sort(np.array(values, dtype=float))
    n = len(arr); cum = np.cumsum(arr)
    return float((n + 1 - 2 * (cum / cum[-1]).sum()) / n)

def statistical_features(sessions):
    n = len(sessions)
    if n == 0: return {}
    watch = [s.watch_seconds for s in sessions]
    chat = [s.chat_messages for s in sessions]
    chat_ratio = sum(chat) / max(n, 1)
    rounded = Counter([w // 300 for w in watch])
    plateau = max(rounded.values()) / n if n > 0 else 0
    return {
        "n_viewers": n, "chat_ratio": chat_ratio,
        "chat_ratio_anomaly": 1.0 if chat_ratio < 0.05 and n > 50 else 0.0,
        "watch_time_cv": float(np.std(watch) / max(np.mean(watch), 1)),
        "watch_time_gini": _gini(watch), "plateau_score": plateau,
        "zero_chat_fraction": sum(1 for c in chat if c == 0) / n,
    }

def behavioral_features(sessions):
    n = len(sessions)
    if n == 0: return {}
    mouse_zero = sum(1 for s in sessions if s.mouse_events == 0) / n
    kbd_zero = sum(1 for s in sessions if s.keyboard_events == 0) / n
    blur_zero = sum(1 for s in sessions if s.tab_blur_events == 0) / n
    minutes = [s.enter_ts.replace(second=0, microsecond=0) for s in sessions]
    counter = Counter(minutes)
    max_sync = max(counter.values()) / n if n > 0 else 0
    sync_burst = sum(v for v in counter.values() if v > 5) / n
    unique = len(set(s.viewer_id for s in sessions))
    return {
        "mouse_zero_fraction": mouse_zero, "keyboard_zero_fraction": kbd_zero,
        "tab_blur_zero_fraction": blur_zero, "max_sync_entry_ratio": max_sync,
        "sync_burst_ratio": sync_burst, "return_rate": 1 - (unique / n) if n > 0 else 0,
    }

def network_features(sessions):
    n = len(sessions)
    if n == 0: return {}
    dc = sum(1 for s in sessions if s.ip_asn_type in ("datacenter", "vpn")) / n
    ja3 = Counter([s.ja3_fingerprint for s in sessions])
    ja3_shared = sum(v for v in ja3.values() if v > 3) / n
    canvas = Counter([s.canvas_hash for s in sessions])
    canvas_shared = sum(v for v in canvas.values() if v > 3) / n
    geo = Counter([s.geo_country for s in sessions])
    geo_entropy = -sum((v / n) * np.log(v / n + 1e-9) for v in geo.values())
    return {
        "datacenter_fraction": dc, "ja3_shared_ratio": ja3_shared,
        "canvas_shared_ratio": canvas_shared, "geo_entropy": geo_entropy,
    }

def account_features(sessions):
    n = len(sessions)
    if n == 0: return {}
    ages = [s.account_age_days for s in sessions]
    return {
        "new_account_fraction": sum(1 for s in sessions if s.account_age_days < 30) / n,
        "no_follows_fraction": sum(1 for s in sessions if s.account_follows == 0) / n,
        "no_transactions_fraction": sum(1 for s in sessions if s.account_transactions == 0) / n,
        "median_account_age_days": float(np.median(ages)),
    }

def build_feature_matrix(sessions):
    row = {}
    row.update(statistical_features(sessions))
    row.update(behavioral_features(sessions))
    row.update(network_features(sessions))
    row.update(account_features(sessions))
    return pd.DataFrame([row])
