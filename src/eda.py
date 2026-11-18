import pandas as pd


def iqr_outliers(s: pd.Series, k: float = 1.5) -> tuple[pd.Series, int]:
    """Маска выбросов по правилу межквартильного размаха и число отмеченных строк."""
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    low, high = q1 - k * iqr, q3 + k * iqr
    mask = (s < low) | (s > high)
    return mask, int(mask.sum())


def domain_outliers(s: pd.Series, low: float = 0.0, high: float = 200.0) -> tuple[pd.Series, int]:
    """Маска нарушений предметного ограничения (стоимость должна быть в интервале (low, high]) и число строк."""
    mask = (s <= low) | (s > high)
    return mask, int(mask.sum())