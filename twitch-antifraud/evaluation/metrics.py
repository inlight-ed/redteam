import numpy as np
from sklearn.metrics import roc_auc_score, precision_recall_curve, average_precision_score, f1_score, confusion_matrix

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
    if len(valid) == 0: return float(thr[0])
    return float(thr[valid[0]])
