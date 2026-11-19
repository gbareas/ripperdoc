"""Evaluate a checkpoint on the held-out test split. Saves its per-example predictions so the
metrics can be recomputed without a GPU: test_predictions.npz (y_true, y_pred), metrics.json."""
import json, numpy as np, torch
from model import SpectraCNN
from data import load_split

net = SpectraCNN().cuda()
net.load_state_dict(torch.load("checkpoints/epoch199.pt"))
y_true, y_pred = net.predict(load_split("test"))
np.savez("test_predictions.npz", y_true=y_true, y_pred=y_pred)

classes = np.unique(y_true)
recall = [float(np.mean(y_pred[y_true == c] == c)) for c in classes]
json.dump({"checkpoint": "epoch199", "test_acc": float(np.mean(y_pred == y_true)),
           "balanced_acc": float(np.mean(recall)), "n_test": int(len(y_true))}, open("metrics.json", "w"), indent=2)
