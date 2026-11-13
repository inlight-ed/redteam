#!/usr/bin/env python3
# bootstrap.py — создаёт полный Red/Blue Team стенд
import os
from pathlib import Path

FILES = {}

# ══════════════════════════════════════════════════════════════════
# BLUE TEAM
# ══════════════════════════════════════════════════════════════════

FILES["twitch-antifraud/requirements.txt"] = """\
pandas>=2.0
numpy>=1.24
scikit-learn>=1.3
joblib>=1.3
torch>=2.1
"""

FILES["twitch-antifraud/data/__init__.py"] = ""
FILES["twitch-antifraud/features/__init__.py"] = ""
FILES["twitch-antifraud/models/__init__.py"] = ""
FILES["twitch-antifraud/evaluation/__init__.py"] = ""

FILES["twitch-antifraud/data/schema.py"] = '''\
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
'''

FILES["twitch-antifraud/data/synthetic_generator.py"] = '''\
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
        ip_asn_type=random.choices(
            ["residential", "mobile", "datacenter", "vpn"],
            weights=[75, 15, 5, 5])[0],
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
        watch_seconds=watch,
        rebuffer_events=random.randint(0, 5),
        quality_changes=random.randint(0, 4),
        fullscreen_events=random.randint(0, 3),
        mouse_events=random.randint(50, 800),
        keyboard_events=random.randint(0, 100),
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
        asn = random.choices(["datacenter", "vpn", "residential"],
                             weights=[50, 30, 20])[0]
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
'''

FILES["twitch-antifraud/features/pipeline.py"] = '''\
import numpy as np
import pandas as pd
from collections import Counter
from data.schema import ViewerSession


def _gini(values):
    if not values or sum(values) == 0:
        return 0.0
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
        "n_viewers": n,
        "chat_ratio": chat_ratio,
        "chat_ratio_anomaly": 1.0 if chat_ratio < 0.05 and n > 50 else 0.0,
        "watch_time_cv": float(np.std(watch) / max(np.mean(watch), 1)),
        "watch_time_gini": _gini(watch),
        "plateau_score": plateau,
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
        "mouse_zero_fraction": mouse_zero,
        "keyboard_zero_fraction": kbd_zero,
        "tab_blur_zero_fraction": blur_zero,
        "max_sync_entry_ratio": max_sync,
        "sync_burst_ratio": sync_burst,
        "return_rate": 1 - (unique / n) if n > 0 else 0,
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
        "datacenter_fraction": dc,
        "ja3_shared_ratio": ja3_shared,
        "canvas_shared_ratio": canvas_shared,
        "geo_entropy": geo_entropy,
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
'''

FILES["twitch-antifraud/models/isolation_forest.py"] = '''\
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib


class IFDetector:
    def __init__(self, contamination=0.1, random_state=42):
        self.scaler = StandardScaler()
        self.model = IsolationForest(n_estimators=300, contamination=contamination,
                                      random_state=random_state, n_jobs=-1)
        self.feature_names_ = None

    def fit(self, X):
        self.feature_names_ = list(X.columns)
        Xs = self.scaler.fit_transform(X)
        self.model.fit(Xs)
        return self

    def score(self, X):
        Xs = self.scaler.transform(X[self.feature_names_])
        return -self.model.decision_function(Xs)

    def predict(self, X, threshold=0.5):
        return (self.score(X) > threshold).astype(int)
'''

FILES["twitch-antifraud/models/autoencoder.py"] = '''\
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler


class Autoencoder(nn.Module):
    def __init__(self, input_dim, latent_dim=8):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 32), nn.ReLU(),
            nn.Linear(32, 16), nn.ReLU(),
            nn.Linear(16, latent_dim),
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 16), nn.ReLU(),
            nn.Linear(16, 32), nn.ReLU(),
            nn.Linear(32, input_dim),
        )

    def forward(self, x):
        return self.decoder(self.encoder(x))


class AEDetector:
    def __init__(self, latent_dim=8, epochs=80, lr=1e-3, batch_size=64,
                 random_state=42):
        torch.manual_seed(random_state)
        self.latent_dim = latent_dim
        self.epochs = epochs
        self.lr = lr
        self.batch_size = batch_size
        self.scaler = StandardScaler()
        self.model = None
        self.threshold = None
        self.feature_names_ = None

    def fit(self, X_clean):
        self.feature_names_ = list(X_clean.columns)
        Xs = self.scaler.fit_transform(X_clean)
        Xs_t = torch.tensor(Xs, dtype=torch.float32)
        loader = DataLoader(TensorDataset(Xs_t), batch_size=self.batch_size,
                            shuffle=True)

        self.model = Autoencoder(Xs.shape[1], self.latent_dim)
        opt = torch.optim.Adam(self.model.parameters(), lr=self.lr)
        loss_fn = nn.MSELoss()

        self.model.train()
        for _ in range(self.epochs):
            for (batch,) in loader:
                opt.zero_grad()
                out = self.model(batch)
                loss = loss_fn(out, batch)
                loss.backward()
                opt.step()

        self.model.eval()
        with torch.no_grad():
            recon = self.model(Xs_t)
            errors = ((recon - Xs_t) ** 2).mean(dim=1).numpy()
        self.threshold = float(np.percentile(errors, 95))
        return self

    def score(self, X):
        Xs = self.scaler.transform(X[self.feature_names_])
        Xs_t = torch.tensor(Xs, dtype=torch.float32)
        self.model.eval()
        with torch.no_grad():
            recon = self.model(Xs_t)
            errors = ((recon - Xs_t) ** 2).mean(dim=1).numpy()
        return errors

    def predict(self, X):
        return (self.score(X) > self.threshold).astype(int)
'''

FILES["twitch-antifraud/models/ensemble.py"] = '''\
import numpy as np


class EnsembleDetector:
    """
    Ансамбль: Isolation Forest + Autoencoder.
    Скоры нормализуются min-max и усредняются с весами.
    """
    def __init__(self, if_detector, ae_detector, w_if=0.5, w_ae=0.5):
        self.if_det = if_detector
        self.ae_det = ae_detector
        self.w_if = w_if
        self.w_ae = w_ae

    @staticmethod
    def _normalize(scores):
        s = np.asarray(scores, dtype=float)
        lo, hi = s.min(), s.max()
        if hi - lo < 1e-9:
            return np.zeros_like(s)
        return (s - lo) / (hi - lo)

    def score(self, X):
        s_if = self._normalize(self.if_det.score(X))
        s_ae = self._normalize(self.ae_det.score(X))
        return self.w_if * s_if + self.w_ae * s_ae

    def predict(self, X, threshold=0.5):
        return (self.score(X) > threshold).astype(int)
'''

FILES["twitch-antifraud/evaluation/metrics.py"] = '''\
import numpy as np
from sklearn.metrics import (roc_auc_score, precision_recall_curve,
                             average_precision_score, f1_score,
                             confusion_matrix)


def evaluate(y_true, scores, threshold=0.5):
    preds = (scores >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, preds).ravel()
    return {
        "roc_auc": float(roc_auc_score(y_true, scores)),
        "pr_auc": float(average_precision_score(y_true, scores)),
        "f1": float(f1_score(y_true, preds)),
        "precision": tp / max(tp + fp, 1),
        "recall": tp / max(tp + fn, 1),
        "fpr": fp / max(fp + tn, 1),
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
    }


def best_threshold(y_true, scores, target_fpr=0.01):
    _, _, thr = precision_recall_curve(y_true, scores)
    fprs = []
    for t in thr:
        preds = (scores >= t).astype(int)
        tn, fp, _, _ = confusion_matrix(y_true, preds).ravel()
        fprs.append(fp / max(fp + tn, 1))
    fprs = np.array(fprs)
    valid = np.where(fprs <= target_fpr)[0]
    if len(valid) == 0:
        return float(thr[0])
    return float(thr[valid[0]])
'''

FILES["twitch-antifraud/run_demo.py"] = '''\
import random
import numpy as np
import pandas as pd

from data.synthetic_generator import make_organic_session, make_bot_session
from features.pipeline import build_feature_matrix
from models.isolation_forest import IFDetector
from models.autoencoder import AEDetector
from models.ensemble import EnsembleDetector
from evaluation.metrics import evaluate, best_threshold

random.seed(42)
np.random.seed(42)


def generate_stream(n_organic, n_bots, bot_types=("naive", "ai_enhanced", "aged")):
    sessions = [make_organic_session("ch1", "st1") for _ in range(n_organic)]
    for _ in range(n_bots):
        sessions.append(make_bot_session("ch1", "st1", random.choice(bot_types)))
    random.shuffle(sessions)
    return sessions


def main():
    X_rows, y = [], []
    for _ in range(200):
        n_org = random.randint(50, 500)
        n_bot = random.randint(0, 200)
        sessions = generate_stream(n_org, n_bot)
        label = 1 if n_bot / max(n_org + n_bot, 1) > 0.1 else 0
        X_rows.append(build_feature_matrix(sessions).iloc[0])
        y.append(label)
    X = pd.DataFrame(X_rows).fillna(0)
    y = np.array(y)
    print(f"Dataset: {X.shape}, positives: {y.sum()}")

    print("\\n=== Isolation Forest ===")
    if_det = IFDetector(contamination=0.15).fit(X)
    s_if = if_det.score(X)
    thr = best_threshold(y, s_if, target_fpr=0.01)
    print(f"threshold={thr:.3f}")
    print(evaluate(y, s_if, threshold=thr))

    print("\\n=== Autoencoder (trained on clean) ===")
    ae_det = AEDetector(epochs=60).fit(X[y == 0])
    s_ae = ae_det.score(X)
    print(evaluate(y, s_ae))

    print("\\n=== Ensemble ===")
    ens = EnsembleDetector(if_det, ae_det, w_if=0.5, w_ae=0.5)
    s_ens = ens.score(X)
    print(evaluate(y, s_ens))


if __name__ == "__main__":
    main()
'''

# ══════════════════════════════════════════════════════════════════
# RED TEAM
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/requirements.txt"] = """\
playwright>=1.40
pyyaml>=6.0
"""

for mod in ["core", "behaviors", "humanizer", "telemetry", "workers"]:
    FILES[f"twitch-redteam/{mod}/__init__.py"] = ""

FILES["twitch-redteam/humanizer/mouse.py"] = '''\
import asyncio
import random
import math


def _cubic_bezier(p0, p1, p2, p3, t):
    u = 1 - t
    return (
        u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0],
        u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1],
    )


def _lognormal_delay(median_ms=10.0, sigma=0.4):
    return random.lognormvariate(math.log(median_ms), sigma) / 1000.0


async def human_move(page, target_x, target_y, steps=None, jitter=1.5):
    current = await page.evaluate(
        "() => ({x: window.__mouseX || 0, y: window.__mouseY || 0})"
    )
    p0 = (current["x"], current["y"])
    p3 = (target_x, target_y)
    dist = math.hypot(p3[0] - p0[0], p3[1] - p0[1])
    p1 = (p0[0] + (p3[0] - p0[0]) * 0.3 + random.uniform(-dist * 0.2, dist * 0.2),
          p0[1] + (p3[1] - p0[1]) * 0.3 + random.uniform(-dist * 0.2, dist * 0.2))
    p2 = (p0[0] + (p3[0] - p0[0]) * 0.7 + random.uniform(-dist * 0.2, dist * 0.2),
          p0[1] + (p3[1] - p0[1]) * 0.7 + random.uniform(-dist * 0.2, dist * 0.2))
    if steps is None:
        steps = max(8, int(dist / 30) + random.randint(-3, 3))
    for i in range(steps + 1):
        t = i / steps
        x, y = _cubic_bezier(p0, p1, p2, p3, t)
        x += random.gauss(0, jitter)
        y += random.gauss(0, jitter)
        await page.mouse.move(x, y)
        await page.evaluate(f"window.__mouseX = {x}; window.__mouseY = {y};")
        await asyncio.sleep(_lognormal_delay(median_ms=8, sigma=0.5))
    await asyncio.sleep(_lognormal_delay(median_ms=40, sigma=0.3))
    await page.mouse.move(target_x, target_y)


async def human_click(page, x, y):
    await human_move(page, x, y)
    await asyncio.sleep(_lognormal_delay(median_ms=60, sigma=0.3))
    await page.mouse.down()
    await asyncio.sleep(_lognormal_delay(median_ms=80, sigma=0.4))
    await page.mouse.up()
'''

FILES["twitch-redteam/humanizer/timing.py"] = '''\
import random
import math


def lognormal_seconds(median_sec, sigma=0.8):
    return random.lognormvariate(math.log(median_sec), sigma)


def poisson_events(rate_per_min, duration_min):
    n = max(1, int(rate_per_min * duration_min * 1.5))
    events = []
    t = 0.0
    for _ in range(n):
        t += random.expovariate(rate_per_min / 60.0)
        if t > duration_min * 60:
            break
        events.append(t)
    return events
'''

FILES["twitch-redteam/behaviors/base.py"] = '''\
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import asyncio
import random


@dataclass
class AgentProfile:
    agent_id: str
    archetype: str
    account_age_days: int
    account_follows: int
    account_subscriptions: int
    account_transactions: int
    timezone: str
    locale: str
    platform: str
    viewport: dict
    user_agent: str
    proxy: Optional[str] = None
    watch_time_target_sec: int = 1800
    chat_probability_per_min: float = 0.0
    leave_return_probability: float = 0.15
    tab_blur_probability_per_min: float = 0.05


@dataclass
class AgentState:
    entered_at: Optional[datetime] = None
    total_watch_sec: int = 0
    chat_sent: int = 0
    mouse_events: int = 0
    keyboard_events: int = 0
    tab_blur_events: int = 0
    event_log: list = field(default_factory=list)


class BaseAgent(ABC):
    def __init__(self, profile, page, logger):
        self.profile = profile
        self.page = page
        self.logger = logger
        self.state = AgentState()

    def _log(self, event, **kwargs):
        payload = {"ts": datetime.utcnow().isoformat(),
                   "agent_id": self.profile.agent_id,
                   "event": event, **kwargs}
        self.state.event_log.append(payload)
        if self.logger:
            self.logger.write(payload)

    @abstractmethod
    async def run(self, stream_url):
        ...

    async def _maybe_leave_and_return(self):
        if random.random() < self.profile.leave_return_probability:
            pause = random.randint(30, 300)
            self._log("leave", duration_sec=pause)
            await asyncio.sleep(pause)
            self._log("return")
            return True
        return False
'''

FILES["twitch-redteam/behaviors/lurker.py"] = '''\
import asyncio
import random
from behaviors.base import BaseAgent
from humanizer.mouse import human_move
from humanizer.timing import lognormal_seconds


class LurkerAgent(BaseAgent):
    async def run(self, stream_url):
        self._log("navigate", url=stream_url)
        await self.page.goto(stream_url, wait_until="domcontentloaded")
        elapsed = 0
        target = self.profile.watch_time_target_sec
        while elapsed < target:
            if random.random() < 0.4:
                x = random.randint(200, self.profile.viewport["width"] - 200)
                y = random.randint(100, self.profile.viewport["height"] - 100)
                try:
                    await human_move(self.page, x, y)
                    self.state.mouse_events += 1
                except Exception:
                    pass
            pause = min(lognormal_seconds(median_sec=20), target - elapsed)
            await asyncio.sleep(pause)
            elapsed += pause
            if await self._maybe_leave_and_return():
                elapsed += 30
        self._log("session_end", total_watch_sec=int(elapsed),
                  mouse_events=self.state.mouse_events)
'''

FILES["twitch-redteam/behaviors/chatter.py"] = '''\
import asyncio
import random
from behaviors.lurker import LurkerAgent
from humanizer.timing import poisson_events

CHAT_TEMPLATES = [
    "lol", "nice play", "gg", "pog", "let's go", "that was insane",
    "no way", "clutch", "wp", "how did he do that", "chat is this real",
    "first time here, love the stream", "the music is fire",
    "anyone else lagging?", "another one", "ez", "close one",
]


class ChatterAgent(LurkerAgent):
    async def run(self, stream_url):
        self._log("navigate", url=stream_url)
        await self.page.goto(stream_url, wait_until="domcontentloaded")
        target = self.profile.watch_time_target_sec
        chat_times = poisson_events(
            self.profile.chat_probability_per_min, target / 60.0
        )
        elapsed = 0
        for t in chat_times:
            wait = t - elapsed
            if wait > 0:
                await asyncio.sleep(wait)
            elapsed = t
            await self._send_chat()
        remaining = target - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)
        self._log("session_end", total_watch_sec=int(target),
                  chat_sent=self.state.chat_sent)

    async def _send_chat(self):
        try:
            await self.page.click("[data-a-target='chat-input']", timeout=3000)
            await asyncio.sleep(random.uniform(0.3, 1.2))
            text = random.choice(CHAT_TEMPLATES)
            if random.random() < 0.05 and len(text) > 3:
                pos = random.randint(0, len(text) - 1)
                text = text[:pos] + random.choice("qwerty") + text[pos:]
            for ch in text:
                await self.page.keyboard.type(ch, delay=0)
                await asyncio.sleep(random.lognormvariate(-2.6, 0.5))
            await asyncio.sleep(random.uniform(0.2, 0.8))
            await self.page.keyboard.press("Enter")
            self.state.chat_sent += 1
            self._log("chat_sent", text=text)
        except Exception as e:
            self._log("chat_error", error=str(e))
'''

FILES["twitch-redteam/behaviors/scanner.py"] = '''\
import asyncio
import random
from behaviors.base import BaseAgent
from humanizer.mouse import human_move
from humanizer.timing import lognormal_seconds


class ScannerAgent(BaseAgent):
    async def run(self, stream_url):
        channels = [stream_url, stream_url + "?alt=1", stream_url + "?alt=2"]
        random.shuffle(channels)
        for ch in channels:
            short_watch = random.randint(30, 180)
            self._log("navigate", url=ch, planned_sec=short_watch)
            try:
                await self.page.goto(ch, wait_until="domcontentloaded")
            except Exception:
                continue
            for _ in range(random.randint(1, 3)):
                x = random.randint(200, 1400)
                y = random.randint(100, 700)
                try:
                    await human_move(self.page, x, y)
                    self.state.mouse_events += 1
                except Exception:
                    pass
                await asyncio.sleep(lognormal_seconds(3, 0.7))
            await asyncio.sleep(max(0, short_watch - 10))
            r = random.random()
            if r < 0.6:
                continue
            elif r < 0.9:
                await asyncio.sleep(random.uniform(30, 120))
                continue
            else:
                await asyncio.sleep(random.uniform(300, 900))
                break
        self._log("session_end", total_watch_sec=self.state.total_watch_sec)
'''

FILES["twitch-redteam/behaviors/multi_tab.py"] = '''\
import asyncio
import random
from behaviors.lurker import LurkerAgent


class MultiTabAgent(LurkerAgent):
    async def run(self, stream_url):
        second = await self.page.context.new_page()
        await second.goto("about:blank")
        self._log("second_tab_opened")
        target = self.profile.watch_time_target_sec
        remaining = target
        while remaining > 0:
            chunk = min(random.randint(60, 300), remaining)
            await asyncio.sleep(chunk)
            remaining -= chunk
            await second.bring_to_front()
            await asyncio.sleep(random.uniform(5, 30))
            await self.page.bring_to_front()
            self.state.tab_blur_events += 1
        await second.close()
        self._log("session_end", total_watch_sec=target)
'''

FILES["twitch-redteam/core/browser_factory.py"] = '''\
from playwright.async_api import async_playwright
import asyncio


class BrowserFactory:
    def __init__(self, headless=True):
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._lock = asyncio.Lock()

    async def start(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

    async def create_context(self, profile):
        async with self._lock:
            context = await self._browser.new_context(
                viewport=profile.viewport,
                user_agent=profile.user_agent,
                locale=profile.locale,
                timezone_id=profile.timezone,
                proxy={"server": profile.proxy} if profile.proxy else None,
                has_touch=profile.platform == "mobile",
                is_mobile=profile.platform == "mobile",
            )
        await context.add_init_script(self._fp_script(profile))
        return context

    def _fp_script(self, profile):
        return f"""
        (() => {{
            Object.defineProperty(navigator, 'platform',
                {{ get: () => {profile.platform!r} }});
            Object.defineProperty(navigator, 'languages',
                {{ get: () => [{profile.locale!r}, 'en'] }});
            Object.defineProperty(navigator, 'webdriver',
                {{ get: () => undefined }});
            window.__mouseX = 0;
            window.__mouseY = 0;
        }})();
        """

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
'''

FILES["twitch-redteam/core/scheduler.py"] = '''\
import csv
import random
import yaml
from behaviors.base import AgentProfile


GEO_TZ = {
    "US": ("America/New_York", "en-US"),
    "DE": ("Europe/Berlin", "de-DE"),
    "BR": ("America/Sao_Paulo", "pt-BR"),
    "KR": ("Asia/Seoul", "ko-KR"),
    "IN": ("Asia/Kolkata", "en-IN"),
    "PH": ("Asia/Manila", "en-PH"),
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
        agent_id=agent_id,
        archetype=archetype,
        account_age_days=random.randint(30, 2000),
        account_follows=random.randint(0, 300),
        account_subscriptions=random.choice([0, 0, 0, 1]),
        account_transactions=0,
        timezone=tz,
        locale=locale,
        platform="Win32",
        viewport={"width": 1920, "height": 1080},
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/141.0.0.0 Safari/537.36"),
        proxy=proxy["url"],
        watch_time_target_sec=1800,
        chat_probability_per_min=(
            0.05 if archetype == "chatter" else 0.0
        ),
        leave_return_probability=0.15,
    )
'''

FILES["twitch-redteam/telemetry/event_logger.py"] = '''\
import json
import os


class EventLogger:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.f = open(path, "a", encoding="utf-8")

    def write(self, payload):
        self.f.write(json.dumps(payload, ensure_ascii=False) + "\\n")
        self.f.flush()

    def close(self):
        self.f.close()
'''

FILES["twitch-redteam/workers/task_runner.py"] = '''\
import asyncio
from behaviors.lurker import LurkerAgent
from behaviors.chatter import ChatterAgent
from behaviors.scanner import ScannerAgent
from behaviors.multi_tab import MultiTabAgent
from telemetry.event_logger import EventLogger

AGENT_MAP = {
    "lurker": LurkerAgent,
    "chatter": ChatterAgent,
    "scanner": ScannerAgent,
    "multi_tab": MultiTabAgent,
    "mobile_user": LurkerAgent,
}


async def run_agent(factory, profile, stream_url, logger, semaphore):
    async with semaphore:
        context = await factory.create_context(profile)
        try:
            page = await context.new_page()
            AgentClass = AGENT_MAP[profile.archetype]
            agent = AgentClass(profile, page, logger)
            await agent.run(stream_url)
        except Exception as e:
            logger.write({"agent_id": profile.agent_id,
                          "event": "error", "error": str(e)})
        finally:
            await context.close()
'''

FILES["twitch-redteam/workers/pod_entry.py"] = '''\
import asyncio
import os
import csv
import yaml
from core.browser_factory import BrowserFactory
from core.scheduler import generate_profile, pick_archetype
from workers.task_runner import run_agent
from telemetry.event_logger import EventLogger


async def main():
    with open("config/pool.yaml") as f:
        cfg = yaml.safe_load(f)
    with open("config/agents.yaml") as f:
        agents_cfg = yaml.safe_load(f)

    pod_index = int(os.environ.get("JOB_COMPLETION_INDEX", 0))
    agents_per_pod = cfg["agents_per_pod"]

    proxies = []
    if os.path.exists("config/proxies.csv"):
        with open("config/proxies.csv") as f:
            proxies = list(csv.DictReader(f))
    if not proxies:
        proxies = [{"url": "", "country": "US"}]

    profiles = []
    for i in range(agents_per_pod):
        idx = pod_index * agents_per_pod + i
        arch = pick_archetype(agents_cfg, idx)
        profiles.append(generate_profile(f"agent_{idx}", arch, proxies))

    factory = BrowserFactory(headless=True)
    await factory.start()
    logger = EventLogger(f"logs/pod_{pod_index}.jsonl")
    semaphore = asyncio.Semaphore(cfg["concurrency_per_pod"])
    stream_url = cfg["target_stream_url"]

    tasks = [run_agent(factory, p, stream_url, logger, semaphore)
             for p in profiles]
    await asyncio.gather(*tasks, return_exceptions=True)

    await factory.close()
    logger.close()


if __name__ == "__main__":
    asyncio.run(main())
'''

FILES["twitch-redteam/config/pool.yaml"] = """\
pods_total: 20
agents_per_pod: 25
concurrency_per_pod: 25
target_stream_url: "https://www.twitch.tv/YOUR_TEST_CHANNEL"
"""

FILES["twitch-redteam/config/agents.yaml"] = """\
templates:
  lurker:
    weight: 0.50
  chatter:
    weight: 0.20
  scanner:
    weight: 0.20
  multi_tab:
    weight: 0.05
  mobile_user:
    weight: 0.05
"""

FILES["twitch-redteam/config/proxies.csv"] = """\
url,country
,US
,DE
,BR
"""

FILES["twitch-redteam/templates/Dockerfile"] = """\
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install chromium

COPY . .

CMD ["python", "-m", "workers.pod_entry"]
"""

FILES["twitch-redteam/templates/kubernetes-indexed-job.yaml"] = """\
apiVersion: batch/v1
kind: Job
metadata:
  name: twitch-redteam
  namespace: redteam-lab
spec:
  completions: 20
  parallelism: 20
  completionMode: Indexed
  backoffLimit: 1
  template:
    metadata:
      labels:
        app: twitch-redteam
    spec:
      containers:
        - name: agent-worker
          image: twitch-redteam:latest
          imagePullPolicy: IfNotPresent
          env:
            - name: JOB_COMPLETION_INDEX
              valueFrom:
                fieldRef:
                  fieldPath: metadata.annotations['batch.kubernetes.io/job-completion-index']
          resources:
            requests:
              memory: "2Gi"
              cpu: "1"
            limits:
              memory: "4Gi"
              cpu: "2"
          volumeMounts:
            - name: config
              mountPath: /app/config
              readOnly: true
            - name: logs
              mountPath: /app/logs
      volumes:
        - name: config
          configMap:
            name: twitch-redteam-config
        - name: logs
          emptyDir: {}
      restartPolicy: Never
"""

FILES["twitch-redteam/templates/configmap.yaml"] = """\
apiVersion: v1
kind: ConfigMap
metadata:
  name: twitch-redteam-config
  namespace: redteam-lab
data:
  pool.yaml: |
    pods_total: 20
    agents_per_pod: 25
    concurrency_per_pod: 25
    target_stream_url: "https://www.twitch.tv/YOUR_TEST_CHANNEL"
  agents.yaml: |
    templates:
      lurker: {weight: 0.50}
      chatter: {weight: 0.20}
      scanner: {weight: 0.20}
      multi_tab: {weight: 0.05}
      mobile_user: {weight: 0.05}
  proxies.csv: |
    url,country
    ,US
"""

FILES["twitch-redteam/run_lab.py"] = '''\
import asyncio
import random
from core.browser_factory import BrowserFactory
from core.scheduler import generate_profile
from behaviors.lurker import LurkerAgent
from behaviors.chatter import ChatterAgent
from behaviors.scanner import ScannerAgent
from behaviors.multi_tab import MultiTabAgent
from telemetry.event_logger import EventLogger


AGENT_MAP = {
    "lurker": LurkerAgent,
    "chatter": ChatterAgent,
    "scanner": ScannerAgent,
    "multi_tab": MultiTabAgent,
}


async def run_one(factory, profile, stream_url, logger):
    context = await factory.create_context(profile)
    try:
        page = await context.new_page()
        agent = AGENT_MAP[profile.archetype](profile, page, logger)
        await agent.run(stream_url)
    finally:
        await context.close()


async def main():
    STREAM_URL = "https://www.twitch.tv/YOUR_TEST_CHANNEL"
    N_AGENTS = 10

    archetypes = ["lurker"] * 5 + ["chatter"] * 2 + ["scanner"] * 2 + ["multi_tab"]
    random.shuffle(archetypes)

    factory = BrowserFactory(headless=True)
    await factory.start()
    logger = EventLogger("logs/run_lab.jsonl")

    proxies = [{"url": "", "country": "US"}]
    profiles = [
        generate_profile(f"agent_{i}", archetypes[i], proxies)
        for i in range(N_AGENTS)
    ]
    for p in profiles:
        p.watch_time_target_sec = 60

    try:
        tasks = [run_one(factory, p, STREAM_URL, logger) for p in profiles]
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        await factory.close()
        logger.close()


if __name__ == "__main__":
    asyncio.run(main())
'''


def write_all():
    for rel, content in FILES.items():
        p = Path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        print(f"  ok {rel}")


if __name__ == "__main__":
    write_all()
    print()
    print("Done. Next steps:")
    print("  cd twitch-antifraud && pip install -r requirements.txt && python run_demo.py")
    print("  cd twitch-redteam && pip install -r requirements.txt && playwright install chromium")
    print("  cd twitch-redteam && python run_lab.py   # 10 агентов локально")
    print("  # Для 500 агентов в K8s:")
    print("  kubectl apply -f twitch-redteam/templates/configmap.yaml")
    print("  kubectl apply -f twitch-redteam/templates/kubernetes-indexed-job.yaml")