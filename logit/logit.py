# %% [markdown]
# # Minimalist critic: logistic regression (torch) — P(win) from relative resources
#
# For each replay (one JSON per replay) and for EACH frame, we keep a **single
# observation**, always from **player 0's point of view** (`players[0]`, index 0 of
# `features`):
#   - X = player 0's resources **relative** to the opponent's (player 1)
#   - y = 1 if player 0 won the match, else 0
#
# No duplication (no mirror of player 1). 1 frame = 1 datapoint.
# The model is a simple `Linear` + sigmoid = logistic regression.

# %%
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import torch
import torch.nn as nn

FEATURES_DIR = Path("../analyze/features")
RS = 42
torch.manual_seed(RS)
np.random.seed(RS)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print("device:", DEVICE)

# %% [markdown]
# ## 0) Dataset construction
# Each frame of a replay yields one point (player-0 perspective). We build
# **relative** features: `log(1+x) - log(1+x_opp)` (symmetric log-ratio) for
# minerals, gas, cumulative minerals, cumulative gas, workers and used supply.

# %%
REL_KEY = ["minerals", "gas", "cum_minerals", "cum_gas", "workers", "supply_used"]


def logratio(p0, p1, key):
    return float(np.log1p(p0[key]) - np.log1p(p1[key]))


def build_dataset():
    rows = []
    for path in sorted(FEATURES_DIR.glob("*.json")):
        d = json.loads(path.read_text())
        winner = d["winner"]
        pid0 = d["players"][0]["id"]
        for frame in d["frames"]:
            f0, f1 = frame["features"][0], frame["features"][1]
            x = {k: logratio(f0, f1, k) for k in REL_KEY}
            x["frame"] = frame["frame"]
            x["label"] = 1 if pid0 == winner else 0
            rows.append(x)
    return pd.DataFrame(rows)


df = build_dataset()
print(f"replays analyzed: {len(set(FEATURES_DIR.glob('*.json')))}")
print(f"datapoints (1 per frame): {len(df)}")
print("player-0 win distribution:\n", df["label"].value_counts().sort_index().to_dict())
print(df.head())

# %%
# Standardize features (Z-score) for learning stability.
X = df[REL_KEY].astype(float).values
mu, sd = X.mean(axis=0), X.std(axis=0) + 1e-9
Xs = (X - mu) / sd
y = df["label"].values.astype(np.float32)
n_feat = Xs.shape[1]
print("X matrix:", Xs.shape, "| y:", y.shape)

# %% [markdown]
# ## 1) torch logistic regression (1 linear layer + sigmoid)

# %%
class LogReg(nn.Module):
    def __init__(self, d):
        super().__init__()
        self.linear = nn.Linear(d, 1)

    def forward(self, x):
        return torch.sigmoid(self.linear(x))


def train(model, Xt, yt, epochs=2000, lr=0.1):
    opt = torch.optim.SGD(model.parameters(), lr=lr)
    crit = nn.BCELoss()
    Xt = torch.from_numpy(Xt).float().to(DEVICE)
    yt = torch.from_numpy(yt).float().unsqueeze(1).to(DEVICE)
    hist = []
    model.train()
    for _ in range(epochs):
        opt.zero_grad()
        loss = crit(model(Xt), yt)
        loss.backward()
        opt.step()
        hist.append(loss.item())
    return hist


model = LogReg(n_feat).to(DEVICE)
hist = train(model, Xs, y, epochs=3000)
print("final loss:", round(hist[-1], 4))

# %% [markdown]
# ## 2) Learning curve (BCE loss)

# %%
plt.figure(figsize=(7, 3))
plt.plot(hist)
plt.xlabel("epoch"); plt.ylabel("BCE loss"); plt.title("Logistic regression training")
plt.grid(alpha=.3); plt.tight_layout(); plt.show()

# %% [markdown]
# ## 3) Feature weights (relative importance on P(win))
# Weights are on **standardized** inputs, so they are comparable with each other.

# %%
w = model.linear.weight.detach().cpu().numpy().ravel()
b = model.linear.bias.detach().cpu().numpy().ravel()[0]
plt.figure(figsize=(8, 3.5))
plt.bar(REL_KEY, w, color="steelblue")
plt.axhline(0, color="k", lw=.8)
plt.title(f"Logistic regression weights (bias = {b:.3f})")
plt.ylabel("weight (standardized X)")
plt.xticks(rotation=20)
plt.grid(alpha=.3); plt.tight_layout(); plt.show()

# %% [markdown]
# ## 4) Sigmoid overlaid on real data
# We project every point onto `z = X·w + b` (the logit) and compare the predicted
# probability (sigmoid) with the real observations (0/1, jittered to show density).

# %%
with torch.no_grad():
    z = model(torch.from_numpy(Xs).float().to(DEVICE)).cpu().numpy().ravel()
    logit = model.linear(torch.from_numpy(Xs).float().to(DEVICE)).cpu().numpy().ravel()

fig, axes = plt.subplots(1, 3, figsize=(16, 4))
# (a) real data: label vs relative cumulative resources
axes[0].scatter(X[:, 2], X[:, 3], c=y, cmap="bwr", s=10, alpha=.5, edgecolors="none")
axes[0].set_xlabel("log-ratio cum_minerals (p0 / p1)"); axes[0].set_ylabel("log-ratio cum_gas (p0 / p1)")
axes[0].set_title("Real data: 0=loss 1=win")
# (b) observations (jittered) vs logit
axes[1].scatter(logit, y, s=8, alpha=.25, edgecolors="none", color="gray")
axes[1].set_xlabel("logit z = X·w+b"); axes[1].set_ylabel("actual outcome (0/1)")
axes[1].set_title("Real observations vs logit")
# (c) predicted sigmoid vs logit
zz = np.linspace(logit.min(), logit.max(), 300)
axes[2].plot(zz, 1 / (1 + np.exp(-zz)), color="crimson", lw=2)
axes[2].scatter(logit, y + np.random.uniform(-.04, .04, size=len(y)), s=8, alpha=.2, edgecolors="none", color="gray")
axes[2].set_xlabel("logit z"); axes[2].set_ylabel("P(win)")
axes[2].set_title("Logistic regression sigmoid")
for ax in axes:
    ax.grid(alpha=.3)
plt.tight_layout(); plt.show()

# %% [markdown]
# ## 5) Accuracy by literal frame
# Replays are analyzed at the same frames (7200, 14400, ..., 43200). We therefore
# look at the accuracy for EACH frame as-is, plus the number of real observations
# available (logically decreasing: short games do not have the last frames).

# %%
df_t = df.copy()
df_t["pred"] = z
df_t["acc"] = ((df_t["pred"] > 0.5).astype(int) == df_t["label"])

ordered = sorted(df_t["frame"].unique())
cats = pd.Categorical(df_t["frame"].astype(int), categories=ordered, ordered=True)
df_t["frame_cat"] = cats
summary = (df_t.groupby("frame_cat", observed=True)
             .agg(n=("acc", "size"), acc=("acc", "mean"))
             .round(3))
print("Literal frames present in the JSONs:", ordered)
print(summary)

fig, ax = plt.subplots(figsize=(8, 4))
summary["acc"].plot(kind="bar", color="teal", ax=ax)
for i, (acc, n) in enumerate(zip(summary["acc"], summary["n"])):
    ax.text(i, acc + 0.01, f"n={n}", ha="center", fontsize=8)
ax.axhline(.5, color="k", ls="--", lw=.8)
ax.set_ylabel("accuracy (0.5 threshold)")
ax.set_xlabel("frame (game seconds × 24)")
ax.set_title("Critic accuracy per frame; n = number of real observations")
plt.grid(alpha=.3); plt.tight_layout(); plt.show()

# %% [markdown]
# ## 6) Detailed 2D view: relative workers and cumulative minerals
# Scatter of the real points colored by outcome.

# %%
plt.figure(figsize=(7, 5))
sc = plt.scatter(X[:, 4], X[:, 2], c=y, cmap="bwr", s=14, alpha=.6, edgecolors="none")
plt.colorbar(sc, label="outcome (p0)")
plt.xlabel("log-ratio workers (p0/p1)"); plt.ylabel("log-ratio cum_minerals (p0/p1)")
plt.title("Real data: relative resources vs outcome")
plt.grid(alpha=.3); plt.tight_layout(); plt.show()

# %%
print("Global accuracy (0.5 threshold):",
      round(((z > 0.5).astype(int) == y).mean(), 4))
print("Weights (ordered):", dict(sorted(zip(REL_KEY, w), key=lambda kv: -abs(kv[1]))))
