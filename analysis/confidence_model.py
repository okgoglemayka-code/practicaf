"""
confidence_model.py - обучаемая модель расчёта уверенности.

Модель рассчитывает уверенность по формуле:

confidence = sigmoid(b + w1*M + w2*T + w3*S)

где:
M - словарный вклад;
T - вклад тональности;
S - статистический вклад;
b - свободный коэффициент;
w1, w2, w3 - обучаемые коэффициенты.
"""

import csv
import json
import math
import os
from typing import Dict, List


MODEL_PATH = os.path.join(os.path.dirname(__file__), "confidence_weights.json")


DEFAULT_WEIGHTS = {
    "bias": -1.0,
    "w_m": 3.0,
    "w_t": 1.2,
    "w_s": 0.8
}


def sigmoid(x: float) -> float:
    """Сигмоидальная функция для перевода значения в диапазон от 0 до 1."""
    return 1 / (1 + math.exp(-x))


class ConfidenceModel:
    """
    Обучаемая модель расчёта уверенности.

    Если файл с обученными весами уже существует, модель использует его.
    Если файла нет, используются базовые экспертные веса.
    """

    def __init__(self):
        self.weights = self.load_weights()

    def load_weights(self) -> Dict[str, float]:
        """Загрузка весов из JSON-файла."""
        if os.path.exists(MODEL_PATH):
            try:
                with open(MODEL_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return DEFAULT_WEIGHTS.copy()

        return DEFAULT_WEIGHTS.copy()

    def save_weights(self):
        """Сохранение весов после обучения."""
        with open(MODEL_PATH, "w", encoding="utf-8") as f:
            json.dump(self.weights, f, ensure_ascii=False, indent=2)

    def predict(self, m: float, t: float, s: float) -> float:
        """
        Расчёт уверенности.

        Args:
            m: словарный вклад от 0 до 1;
            t: тональность от 0 до 1;
            s: статистический вклад от 0 до 1.

        Returns:
            confidence: уверенность от 0.01 до 0.99.
        """

        m = max(0.0, min(m, 1.0))
        t = max(0.0, min(t, 1.0))
        s = max(0.0, min(s, 1.0))

        z = (
            self.weights["bias"]
            + self.weights["w_m"] * m
            + self.weights["w_t"] * t
            + self.weights["w_s"] * s
        )

        confidence = sigmoid(z)
        return round(max(0.01, min(confidence, 0.99)), 2)

    def train(
        self,
        samples: List[Dict[str, float]],
        epochs: int = 1000,
        learning_rate: float = 0.1
    ):
        """
        Обучение весов W1, W2, W3.

        Формат одного примера:

        {
            "m": 0.7,
            "t": 0.9,
            "s": 0.3,
            "label": 1
        }

        label:
        0 - безопасный текст;
        1 - деструктивный текст.
        """

        if not samples:
            print("⚠️ Нет обучающих примеров. Веса не изменены.")
            return

        bias = self.weights["bias"]
        w_m = self.weights["w_m"]
        w_t = self.weights["w_t"]
        w_s = self.weights["w_s"]

        for _ in range(epochs):
            for sample in samples:
                m = float(sample["m"])
                t = float(sample["t"])
                s = float(sample["s"])
                y = int(sample["label"])

                prediction = sigmoid(bias + w_m * m + w_t * t + w_s * s)
                error = prediction - y

                bias -= learning_rate * error
                w_m -= learning_rate * error * m
                w_t -= learning_rate * error * t
                w_s -= learning_rate * error * s

        self.weights = {
            "bias": round(bias, 4),
            "w_m": round(w_m, 4),
            "w_t": round(w_t, 4),
            "w_s": round(w_s, 4)
        }

        self.save_weights()


def load_training_samples(csv_path: str) -> List[Dict[str, float]]:
    """
    Загрузка обучающей выборки из CSV.

    CSV должен иметь столбцы:
    m,t,s,label
    """

    samples = []

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            samples.append({
                "m": float(row["m"]),
                "t": float(row["t"]),
                "s": float(row["s"]),
                "label": int(row["label"])
            })

    return samples