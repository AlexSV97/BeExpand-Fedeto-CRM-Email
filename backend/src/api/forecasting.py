"""
Módulo de forecasting — regresión lineal simple para predicciones.

Proyecta volúmenes de correos por categoría en los próximos N días
usando mínimos cuadrados ordinarios (OLS). Sin dependencias externas
(ni numpy, ni scikit-learn, ni Prophet).

Uso:
    predictions = forecast_category(daily_counts, days_ahead=30)
    direction = trend_direction(daily_counts)
"""

from datetime import date, timedelta
from typing import Sequence


class LinearRegression:
    """Regresión lineal univariante por mínimos cuadrados.

    y = slope * x + intercept

    Se usa en lugar de numpy.linalg.lstsq para evitar la dependencia
    de numpy y mantener el proyecto ligero.
    """

    def __init__(self) -> None:
        self.slope: float = 0.0
        self.intercept: float = 0.0

    def fit(self, x: Sequence[float], y: Sequence[float]) -> None:
        """Ajusta el modelo con OLS.

        Args:
            x: Variable independiente (ej. días desde el inicio).
            y: Variable dependiente (ej. recuento de correos).
        """
        n = len(x)
        if n < 2:
            self.slope = 0.0
            self.intercept = float(y[0]) if y else 0.0
            return

        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(a * b for a, b in zip(x, y))
        sum_x2 = sum(a * a for a in x)

        denom = n * sum_x2 - sum_x * sum_x
        if abs(denom) < 1e-12:
            self.slope = 0.0
            self.intercept = sum_y / n
        else:
            self.slope = (n * sum_xy - sum_x * sum_y) / denom
            self.intercept = (sum_y - self.slope * sum_x) / n

    def predict(self, x: float) -> float:
        """Predice y para un valor de x."""
        return self.slope * x + self.intercept


def forecast_category(
    daily_counts: list[tuple[date, int]],
    days_ahead: int = 30,
    min_days: int = 3,
) -> list[tuple[date, float]]:
    """Proyecta daily_counts `days_ahead` días hacia adelante.

    Args:
        daily_counts: Lista de (date, count) ordenada por fecha ascendente.
        days_ahead: Número de días a proyectar.
        min_days: Mínimo de puntos históricos para ajustar regresión.
                  Por debajo se usa la media simple.

    Returns:
        Lista de (date, predicted_count) para cada día futuro.
    """
    if not daily_counts:
        today = date.today()
        return [(today + timedelta(days=i + 1), 0.0) for i in range(days_ahead)]

    if len(daily_counts) < min_days:
        avg = sum(c for _, c in daily_counts) / len(daily_counts)
        last_date = daily_counts[-1][0]
        return [
            (last_date + timedelta(days=i + 1), avg)
            for i in range(days_ahead)
        ]

    x = [float(i) for i in range(len(daily_counts))]
    y = [float(c) for _, c in daily_counts]

    model = LinearRegression()
    model.fit(x, y)

    last_date = daily_counts[-1][0]
    predictions: list[tuple[date, float]] = []
    for i in range(1, days_ahead + 1):
        pred_x = float(len(daily_counts) - 1 + i)
        pred_val = max(0.0, round(model.predict(pred_x), 2))
        predictions.append((last_date + timedelta(days=i), pred_val))

    return predictions


def trend_direction(daily_counts: list[tuple[date, int]]) -> str:
    """Determina la dirección de la tendencia.

    Returns:
        "increasing" | "decreasing" | "stable"
    """
    if len(daily_counts) < 3:
        return "stable"

    x = [float(i) for i in range(len(daily_counts))]
    y = [float(c) for _, c in daily_counts]

    model = LinearRegression()
    model.fit(x, y)

    if model.slope > 0.05:
        return "increasing"
    elif model.slope < -0.05:
        return "decreasing"
    else:
        return "stable"
