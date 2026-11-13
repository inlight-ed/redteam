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

    print("\n=== Isolation Forest ===")
    if_det = IFDetector(contamination=0.15).fit(X)
    s_if = if_det.score(X)
    thr = best_threshold(y, s_if, target_fpr=0.01)
    print(f"threshold={thr:.3f}")
    print(evaluate(y, s_if, threshold=thr))

    print("\n=== Autoencoder (trained on clean) ===")
    ae_det = AEDetector(epochs=60).fit(X[y == 0])
    s_ae = ae_det.score(X)
    print(evaluate(y, s_ae))

    print("\n=== Ensemble ===")
    ens = EnsembleDetector(if_det, ae_det, w_if=0.5, w_ae=0.5)
    s_ens = ens.score(X)
    print(evaluate(y, s_ens))

if __name__ == "__main__":
    main()
