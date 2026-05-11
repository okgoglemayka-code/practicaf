"""
train_confidence.py - обучение весов для расчёта уверенности.

Запуск:
python train_confidence.py
"""

from analysis.confidence_model import ConfidenceModel, load_training_samples


def main():
    csv_path = "training_confidence.csv"

    samples = load_training_samples(csv_path)

    model = ConfidenceModel()
    model.train(
        samples=samples,
        epochs=500,
        learning_rate=0.03
    )

    print("✅ Обучение завершено")
    print("Новые веса:")
    print(model.weights)


if __name__ == "__main__":
    main()