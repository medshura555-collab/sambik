import numpy as np
from scipy.stats import skew


def skewness(x: np.ndarray) -> float:
    """Асимметрия с поправкой на смещение (совпадает с pandas Series.skew)."""
    return float(skew(x, bias=False))


def bootstrap_median_ci(x: np.ndarray, n_boot: int = 2000, sample_size: int = 50_000,
                        alpha: float = 0.05, random_state: int = 42) -> dict:
    """Бутстрап-интервал медианы по случайной выборке из x."""
    rng = np.random.default_rng(random_state)
    sample = rng.choice(x, size=sample_size, replace=False)
    boot = np.empty(n_boot)
    for i in range(n_boot):
        boot[i] = np.median(rng.choice(sample, size=sample_size, replace=True))
    lo, hi = np.percentile(boot, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {
        "median_sample": float(np.median(sample)),
        "ci_low": float(lo),
        "ci_high": float(hi),
        "n_boot": n_boot,
        "sample_size": sample_size,
        "boot": boot,
    }

from scipy.stats import mannwhitneyu, kruskal
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportions_ztest


def compare_two(a, b):
    """Манн–Уитни: U, p и rank-biserial r (r > 0 — значения в a больше)."""
    u, p = mannwhitneyu(a, b, alternative="two-sided", method="asymptotic")
    r = 2 * u / (len(a) * len(b)) - 1
    return float(u), float(p), float(r)


def kruskal_eta2(groups):
    """Краскел–Уоллис: H, p и eta² = (H - k + 1) / (n - k)."""
    h, p = kruskal(*groups)
    n = sum(len(g) for g in groups)
    k = len(groups)
    return float(h), float(p), float((h - k + 1) / (n - k))


def pairwise_holm(groups: dict):
    """Попарные Манн–Уитни с поправкой Холма. Список кортежей (a, b, p, p_holm, r)."""
    rows = []
    keys = list(groups)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = groups[keys[i]], groups[keys[j]]
            u, p = mannwhitneyu(a, b, alternative="two-sided", method="asymptotic")
            rows.append((keys[i], keys[j], p, 2 * u / (len(a) * len(b)) - 1))
    _, p_holm, _, _ = multipletests([r[2] for r in rows], alpha=0.05, method="holm")
    return [(a, b, p, ph, r) for (a, b, p, r), ph in zip(rows, p_holm)]


def share_ztest(k1, n1, k2, n2):
    """Z-тест долей и h Кохена."""
    z, p = proportions_ztest([k1, k2], [n1, n2])
    p1, p2 = k1 / n1, k2 / n2
    h = 2 * np.arcsin(np.sqrt(p1)) - 2 * np.arcsin(np.sqrt(p2))
    return float(z), float(p), float(h), p1, p2

def bootstrap_median_diff(a, b, n_boot=2000, random_state=42):
    """Разность медиан (b − a) и 95% бутстрап-интервал."""
    rng = np.random.default_rng(random_state)
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        diffs[i] = (np.median(rng.choice(b, size=b.size, replace=True))
                    - np.median(rng.choice(a, size=a.size, replace=True)))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return float(np.median(b) - np.median(a)), float(lo), float(hi)

def corr_matrices(df, cols):
    """Матрицы Пирсона и Спирмена по указанным столбцам (попарно полные наблюдения)."""
    sub = df[cols]
    return sub.corr(method="pearson"), sub.corr(method="spearman")

def simpson_check(df, flag, target, group):
    """Разность медиан target по бинарному флагу: общая и внутри каждой группы."""
    overall = df.groupby(flag)[target].median()
    inside = df.groupby([group, flag])[target].median().unstack()
    overall_diff = overall[True] - overall[False]
    inside_diff = inside[True] - inside[False]
    return overall_diff, inside_diff