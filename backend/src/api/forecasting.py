"""
Módulo de forecasting — regresión lineal con estacionalidad semanal y ruido realista.

Proyecta volúmenes de correos por categoría en los próximos N días usando:

1. **Tendencia** (LinearRegression sobre datos padded)
2. **Estacionalidad semanal** (factores aditivos por día de la semana)
3. **Ruido realista** (re-muestreo de residuos históricos)

Sin dependencias externas (ni numpy, ni scikit-learn, ni Prophet).

Uso:
    predictions = forecast_category(daily_counts, days_ahead=30)
    direction = trend_direction(daily_counts)
"""

import random
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


# ── Seasonal decomposition helpers ──


def _compute_trend_values(
    daily_counts: list[tuple[date, int]],
) -> tuple[LinearRegression, list[float]]:
    """Ajusta una regresión lineal y devuelve los valores de tendencia."""
    x = [float(i) for i in range(len(daily_counts))]
    y = [float(c) for _, c in daily_counts]
    model = LinearRegression()
    model.fit(x, y)
    trend_values = [model.predict(xi) for xi in x]
    return model, trend_values


def _compute_seasonal_effects(
    daily_counts: list[tuple[date, int]],
    trend_values: list[float],
) -> dict[int, float]:
    """Calcula efectos estacionales aditivos por día de la semana.

    Para cada día histórico: efecto = real - tendencia
    Promedia por día de la semana (0=lunes .. 6=domingo).
    Centra los efectos para que sumen ~0.
    """
    dow_effects: dict[int, list[float]] = {i: [] for i in range(7)}

    for (d, actual), trend_val in zip(daily_counts, trend_values):
        dow = d.weekday()
        effect = float(actual) - trend_val
        dow_effects[dow].append(effect)

    effects: dict[int, float] = {}
    for dow, values in dow_effects.items():
        effects[dow] = sum(values) / len(values) if values else 0.0

    # Centrar: que los efectos sumen ~0 para que no sesguen la tendencia
    avg = sum(effects.values()) / 7
    for dow in effects:
        effects[dow] -= avg

    return effects


def _build_noise_library(
    daily_counts: list[tuple[date, int]],
    trend_values: list[float],
    seasonal_effects: dict[int, float],
) -> list[float]:
    """Construye una librería de ruido a partir de los residuos históricos.

    residuo = real - tendencia - efecto_estacional

    Estos residuos se re-muestrearán durante el forecast para dar
    una variación realista (no aleatoria pura, sino basada en patrones reales).
    """
    residuals: list[float] = []
    for (d, actual), trend_val in zip(daily_counts, trend_values):
        dow = d.weekday()
        expected = trend_val + seasonal_effects.get(dow, 0.0)
        residuals.append(float(actual) - expected)
    return residuals


# ── New enhanced forecast ──


def forecast_category(
    daily_counts: list[tuple[date, int]],
    days_ahead: int = 30,
    min_days: int = 7,
) -> list[tuple[date, float]]:
    """Proyecta daily_counts `days_ahead` días hacia adelante.

    Usa un modelo de tendencia + estacionalidad semanal + ruido realista
    cuando hay suficientes datos históricos (>= min_days días únicos).

    Con pocos datos (< min_days) usa la media simple con algo de ruido
    para evitar líneas perfectamente planas.

    Args:
        daily_counts: Lista de (date, count) ordenada por fecha ascendente.
        days_ahead: Número de días a proyectar.
        min_days: Mínimo de puntos históricos para usar el modelo completo.
                  Por debajo se usa la media simple con ruido.

    Returns:
        Lista de (date, predicted_count) para cada día futuro.
    """
    if not daily_counts:
        today = date.today()
        return [(today + timedelta(days=i + 1), 0.0) for i in range(days_ahead)]

    # ═══ POCOS DATOS: media simple con algo de ruido ═══
    if len(daily_counts) < min_days:
        avg = sum(c for _, c in daily_counts) / len(daily_counts)
        last_date = daily_counts[-1][0]

        # Calculamos desviación típica para el ruido
        std = (
            (sum((c - avg) ** 2 for _, c in daily_counts) / len(daily_counts)) ** 0.5
            if len(daily_counts) > 1
            else avg * 0.2
        )

        predictions: list[tuple[date, float]] = []
        for i in range(days_ahead):
            pred_date = last_date + timedelta(days=i + 1)
            dow = pred_date.weekday()
            # Ruido determinista basado en fecha + día de la semana
            seasonal_pulse = _day_pulse(dow, avg)
            noise = _deterministic_noise(pred_date, std * 0.3)
            val = max(0.0, round(avg + seasonal_pulse + noise, 2))
            predictions.append((pred_date, val))

        return predictions

    # ═══ DATOS SUFICIENTES: tendencia + estacionalidad + ruido ═══
    model, trend_values = _compute_trend_values(daily_counts)
    seasonal_effects = _compute_seasonal_effects(daily_counts, trend_values)
    noise_library = _build_noise_library(daily_counts, trend_values, seasonal_effects)

    last_date = daily_counts[-1][0]
    predictions: list[tuple[date, float]] = []

    for i in range(1, days_ahead + 1):
        pred_x = float(len(daily_counts) - 1 + i)
        trend_val = model.predict(pred_x)

        pred_date = last_date + timedelta(days=i)
        dow = pred_date.weekday()

        # Componente estacional
        seasonal = seasonal_effects.get(dow, 0.0)

        # Ruido: muestreo circular de los residuos históricos
        noise_idx = (i - 1) % len(noise_library) if noise_library else 0
        noise = noise_library[noise_idx] if noise_library else 0.0

        val = max(0.0, round(trend_val + seasonal + noise, 2))
        predictions.append((pred_date, val))

    return predictions


# ── Helpers ──


def _day_pulse(dow: int, scale: float) -> float:
    """Pequeño pulso estacional para cuando no hay datos suficientes.

    Lunes ligeramente alto, fin de semana bajo.
    """
    pulses = {
        0: 0.15,   # lunes   → +15%
        1: 0.05,   # martes
        2: 0.10,   # miércoles
        3: 0.05,   # jueves
        4: -0.05,  # viernes
        5: -0.20,  # sábado  → -20%
        6: -0.15,  # domingo → -15%
    }
    return pulses.get(dow, 0.0) * scale


def _deterministic_noise(d: date, std: float) -> float:
    """Ruido determinista basado en la fecha (mismo resultado siempre)."""
    if std <= 0:
        return 0.0
    rng = random.Random(d.toordinal())
    return rng.gauss(0, std)


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
