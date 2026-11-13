import numpy as np

class EnsembleDetector:
    def __init__(self, if_detector, ae_detector, w_if=0.5, w_ae=0.5):
        self.if_det = if_detector
        self.ae_det = ae_detector
        self.w_if = w_if
        self.w_ae = w_ae

    @staticmethod
    def _normalize(scores):
        s = np.asarray(scores, dtype=float)
        lo, hi = s.min(), s.max()
        if hi - lo < 1e-9: return np.zeros_like(s)
        return (s - lo) / (hi - lo)

    def score(self, X):
        s_if = self._normalize(self.if_det.score(X))
        s_ae = self._normalize(self.ae_det.score(X))
        return self.w_if * s_if + self.w_ae * s_ae

    def predict(self, X, threshold=0.5):
        return (self.score(X) > threshold).astype(int)
