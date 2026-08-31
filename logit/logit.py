# %% [markdown]
# # Critic minimaliste : régression logistique (torch) — P(gagner) à partir des ressources relatives
#
# Pour chaque replay (un JSON par replay) et pour CHAQUE frame, on garde **une seule
# observation**, toujours **du point de vue du joueur 0** (`players[0]`, index 0 de
# `features`) :
#   - X = ressources du joueur 0 **relatives** à celles de l'adversaire (joueur 1)
#   - y = 1 si le joueur 0 a gagné le match, sinon 0
#
# Aucune duplication (pas de miroir du joueur 1). 1 frame = 1 datapoint.
# Le modèle est un simple `Linear` + sigmoïde = régression logistique.

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
# ## 0) Construction du dataset
# Chaque frame d'un replay donne un point (perspective joueur 0). On fabrique des
# caractéristiques **relatives** : `log(1+x) - log(1+x_opp)` (rapport log symétrique)
# pour minéraux, gaz, cumulés, gaz cumulé, workers et supply utilisée.

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
print(f"replays analysés : {len(set(FEATURES_DIR.glob('*.json')))}")
print(f"datapoints (1 par frame) : {len(df)}")
print("répartition victoire joueur0 :\n", df["label"].value_counts().sort_index().to_dict())
print(df.head())

# %%
# Standardisation des caractéristiques (Z-score) pour stabilité de l'apprentissage.
X = df[REL_KEY].astype(float).values
mu, sd = X.mean(axis=0), X.std(axis=0) + 1e-9
Xs = (X - mu) / sd
y = df["label"].values.astype(np.float32)
n_feat = Xs.shape[1]
print("matrice X :", Xs.shape, "| y :", y.shape)

# %% [markdown]
# ## 1) Régression logistique torch (1 couche linéaire + sigmoïde)

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
print("loss finale :", round(hist[-1], 4))

# %% [markdown]
# ## 2) Courbe d'apprentissage (loss BCE)

# %%
plt.figure(figsize=(7, 3))
plt.plot(hist)
plt.xlabel("epoch"); plt.ylabel("BCE loss"); plt.title("Apprentissage de la régression logistique")
plt.grid(alpha=.3); plt.tight_layout(); plt.show()

# %% [markdown]
# ## 3) Poids des caractéristiques (importance relative sur P(gagner))
# Les poids sont sur les entrées **standardisées** → comparables entre elles.

# %%
w = model.linear.weight.detach().cpu().numpy().ravel()
b = model.linear.bias.detach().cpu().numpy().ravel()[0]
plt.figure(figsize=(8, 3.5))
plt.bar(REL_KEY, w, color="steelblue")
plt.axhline(0, color="k", lw=.8)
plt.title(f"Poids de la régression logistique (biais = {b:.3f})")
plt.ylabel("poids (X standardisé)")
plt.xticks(rotation=20)
plt.grid(alpha=.3); plt.tight_layout(); plt.show()

# %% [markdown]
# ## 4) Sigmoïde superposée aux données réelles
# On projette chaque point sur l'axe `z = X·w + b` (le logit) et on compare la
# probabilité prédite (sigmoïde) aux observations réelles (0/1, avec bruit pour
# visualiser la densité).

# %%
with torch.no_grad():
    z = model(torch.from_numpy(Xs).float().to(DEVICE)).cpu().numpy().ravel()
    logit = model.linear(torch.from_numpy(Xs).float().to(DEVICE)).cpu().numpy().ravel()

fig, axes = plt.subplots(1, 3, figsize=(16, 4))
# (a) données réelles : label vs ressources cumulées relatives
axes[0].scatter(X[:, 2], X[:, 3], c=y, cmap="bwr", s=10, alpha=.5, edgecolors="none")
axes[0].set_xlabel("log-ratio cum_minerals (j0 / j1)"); axes[0].set_ylabel("log-ratio cum_gas (j0 / j1)")
axes[0].set_title("Données réelles : 0=défaite 1=victoire")
# (b) observations (avec jitter) vs logit
axes[1].scatter(logit, y, s=8, alpha=.25, edgecolors="none", color="gray")
axes[1].set_xlabel("logit z = X·w+b"); axes[1].set_ylabel("résultat réel (0/1)")
axes[1].set_title("Observations réelles vs logit")
# (c) sigmoïde prédite vs logit
zz = np.linspace(logit.min(), logit.max(), 300)
axes[2].plot(zz, 1 / (1 + np.exp(-zz)), color="crimson", lw=2)
axes[2].scatter(logit, y + np.random.uniform(-.04, .04, size=len(y)), s=8, alpha=.2, edgecolors="none", color="gray")
axes[2].set_xlabel("logit z"); axes[2].set_ylabel("P(gagner)")
axes[2].set_title("Sigmoïde de la régression logistique")
for ax in axes:
    ax.grid(alpha=.3)
plt.tight_layout(); plt.show()

# %% [markdown]
# ## 5) Précision par frame littérale
# Les replays sont analysés aux mêmes frames (7200, 14400, ..., 43200). On regarde
# donc la précision pour CHAQUE frame telle quelle, et le nombre d'observations
# réelles disponibles (logiquement décroissant : les parties courtes n'ont pas les
# dernières frames).

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
print("Frames littérales présentes dans les JSON :", ordered)
print(summary)

fig, ax = plt.subplots(figsize=(8, 4))
summary["acc"].plot(kind="bar", color="teal", ax=ax)
for i, (acc, n) in enumerate(zip(summary["acc"], summary["n"])):
    ax.text(i, acc + 0.01, f"n={n}", ha="center", fontsize=8)
ax.axhline(.5, color="k", ls="--", lw=.8)
ax.set_ylabel("précision (seuil 0.5)")
ax.set_xlabel("frame (secondes de jeu × 24)")
ax.set_title("Précision du critic par frame ; n = nb d'observations réelles")
plt.grid(alpha=.3); plt.tight_layout(); plt.show()

# %% [markdown]
# ## 6) Vue 2D détaillée : workers et minéraux cumulés relatifs
# Nuage des points réels colorés par issue, avec la frontière de décision approx.

# %%
plt.figure(figsize=(7, 5))
sc = plt.scatter(X[:, 4], X[:, 2], c=y, cmap="bwr", s=14, alpha=.6, edgecolors="none")
plt.colorbar(sc, label="résultat (j0)")
plt.xlabel("log-ratio workers (j0/j1)"); plt.ylabel("log-ratio cum_minerals (j0/j1)")
plt.title("Données réelles : ressources relatives vs issue")
plt.grid(alpha=.3); plt.tight_layout(); plt.show()

# %%
print("Précision globale (seuil 0.5) :",
      round(((z > 0.5).astype(int) == y).mean(), 4))
print("Poids (ordre) :", dict(sorted(zip(REL_KEY, w), key=lambda kv: -abs(kv[1]))))
