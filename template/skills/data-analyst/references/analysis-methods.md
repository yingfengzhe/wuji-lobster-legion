# Méthodes d'Analyse Statistique

## Statistiques Descriptives

### Mesures de Tendance Centrale

**Moyenne arithmétique**
```
μ = Σxi / n
```
- Sensible aux valeurs extrêmes
- Appropriée pour distributions symétriques

**Médiane**
- Valeur qui divise la distribution en deux parties égales
- Robuste aux outliers
- Préférer pour distributions asymétriques

**Mode**
- Valeur la plus fréquente
- Utile pour données catégorielles

### Mesures de Dispersion

**Variance**
```
σ² = Σ(xi - μ)² / (n-1)  [échantillon]
σ² = Σ(xi - μ)² / n      [population]
```

**Écart-type**
```
σ = √variance
```
- Même unité que les données
- ~68% des données dans [μ-σ, μ+σ] si distribution normale

**Coefficient de variation**
```
CV = σ / μ × 100%
```
- Permet de comparer la dispersion de variables d'échelles différentes

**Intervalle interquartile (IQR)**
```
IQR = Q3 - Q1
```
- Robuste aux outliers
- Contient 50% des données centrales

### Mesures de Forme

**Skewness (asymétrie)**
```
γ1 = E[(X-μ)³] / σ³
```
| Valeur | Interprétation |
|--------|----------------|
| γ1 ≈ 0 | Distribution symétrique |
| γ1 > 0 | Queue à droite (positif) |
| γ1 < 0 | Queue à gauche (négatif) |

**Kurtosis (aplatissement)**
```
γ2 = E[(X-μ)⁴] / σ⁴ - 3
```
| Valeur | Interprétation |
|--------|----------------|
| γ2 ≈ 0 | Mésokurtique (normale) |
| γ2 > 0 | Leptokurtique (queues épaisses) |
| γ2 < 0 | Platykurtique (queues fines) |

## Tests Statistiques

### Test t de Student

**Hypothèses**
- H0 : μ1 = μ2 (pas de différence)
- H1 : μ1 ≠ μ2 (différence significative)

**Conditions d'application**
- Données continues
- Distribution approximativement normale (ou n > 30)
- Variances similaires (ou utiliser Welch's t-test)

**Interprétation**
- p < 0.05 : Rejeter H0 (différence significative)
- p ≥ 0.05 : Ne pas rejeter H0

### ANOVA (Analysis of Variance)

**Usage** : Comparer les moyennes de 3+ groupes

**Hypothèses**
- H0 : μ1 = μ2 = ... = μk
- H1 : Au moins une moyenne diffère

**Statistique F**
```
F = Variance inter-groupes / Variance intra-groupes
```

### Test du Chi-carré

**Usage** : Association entre variables catégorielles

**Statistique**
```
χ² = Σ (Observé - Attendu)² / Attendu
```

**Degrés de liberté**
```
df = (lignes - 1) × (colonnes - 1)
```

## Corrélations

### Corrélation de Pearson

```
r = Σ(xi - x̄)(yi - ȳ) / √[Σ(xi - x̄)² × Σ(yi - ȳ)²]
```

**Conditions**
- Relation linéaire
- Variables continues
- Pas d'outliers majeurs

### Corrélation de Spearman

```
ρ = 1 - (6 × Σdi²) / (n(n²-1))
```
où di = différence des rangs

**Avantages**
- Ne suppose pas de linéarité
- Robuste aux outliers
- Fonctionne avec données ordinales

### Corrélation de Kendall

```
τ = (concordants - discordants) / (n(n-1)/2)
```

**Avantages**
- Plus robuste que Spearman
- Meilleur pour petits échantillons

## Analyse de Séries Temporelles

### Moyenne Mobile

**Simple (SMA)**
```
SMA_t = (1/k) × Σ(x_{t-i}), i=0 to k-1
```

**Exponentielle (EMA)**
```
EMA_t = α × x_t + (1-α) × EMA_{t-1}
```
où α = 2/(k+1)

### Croissance

**CAGR (Compound Annual Growth Rate)**
```
CAGR = (V_final / V_initial)^(1/n) - 1
```

**Year-over-Year (YoY)**
```
YoY = (V_t - V_{t-12}) / V_{t-12} × 100%
```

### Saisonnalité

**Indices saisonniers**
```
IS_m = moyenne(mois_m) / moyenne_globale
```

## Détection d'Anomalies

### Méthode Z-score

```
z = (x - μ) / σ
```
- Anomalie si |z| > 3 (99.7% des données)
- Suppose distribution normale

### Méthode Z-score Modifié (MAD)

```
MAD = median(|xi - median(X)|)
M = 0.6745 × (xi - median(X)) / MAD
```
- Anomalie si |M| > 3.5
- Robuste aux outliers existants

### Méthode IQR (Tukey)

```
Borne inférieure = Q1 - 1.5 × IQR
Borne supérieure = Q3 + 1.5 × IQR
```
- Anomalie si hors de [borne_inf, borne_sup]
- Simple et robuste

## Taille d'Effet

### Cohen's d

```
d = (μ1 - μ2) / σ_pooled
```

| d | Interprétation |
|---|----------------|
| 0.2 | Petit effet |
| 0.5 | Effet moyen |
| 0.8 | Grand effet |

### R² (Coefficient de détermination)

```
R² = 1 - (SS_residual / SS_total)
```
- Proportion de variance expliquée
- 0 à 1 (1 = parfait)

## Intervalles de Confiance

### IC pour la moyenne

```
IC = x̄ ± t_{α/2,df} × (s/√n)
```

### IC pour une proportion

```
IC = p̂ ± z_{α/2} × √(p̂(1-p̂)/n)
```

## Règles Pratiques

### Taille d'Échantillon Minimale

| Analyse | n minimum recommandé |
|---------|---------------------|
| Statistiques descriptives | 30 |
| Corrélations | 50-100 |
| Régression (par variable) | 10-20 |
| Test t | 30 par groupe |
| ANOVA | 20 par groupe |

### Seuils de Significativité

| Domaine | α typique |
|---------|-----------|
| Sciences sociales | 0.05 |
| Médecine | 0.01 |
| Physique | 0.001 (5σ) |
| Exploratoire | 0.10 |
