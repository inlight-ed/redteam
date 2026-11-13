import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

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
