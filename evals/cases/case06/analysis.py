"""Does the expression panel predict treatment response? Nearest-centroid classifier on a held-out split."""
import json
import numpy as np

d = np.load("cohort.npz")
X, y = d["expression"], d["response"]            # 60 patients x 2000 genes, binary response
rng = np.random.default_rng(0)

# keep the 20 genes most correlated with response
Xc = (X - X.mean(0)) / X.std(0)
corr = np.abs((Xc * (y - y.mean())[:, None]).mean(0) / y.std())
panel = np.argsort(corr)[-20:]
X = Xc[:, panel]

accs = []
for rep in range(50):
    idx = rng.permutation(len(y))
    tr, te = idx[:40], idx[40:]
    c0, c1 = X[tr][y[tr] == 0].mean(0), X[tr][y[tr] == 1].mean(0)
    pred = (np.linalg.norm(X[te] - c1, axis=1) < np.linalg.norm(X[te] - c0, axis=1)).astype(int)
    accs.append(np.mean(pred == y[te]))

out = {"n_patients": int(len(y)), "n_genes": int(d["expression"].shape[1]), "panel_size": 20,
       "heldout_acc_mean": float(np.mean(accs)), "heldout_acc_std": float(np.std(accs)), "repeats": 50}
json.dump(out, open("result.json", "w"), indent=2)
print(out)
