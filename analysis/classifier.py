"""
classifier.py -Классификация деструктивного контента
"""

import re
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
from enum import Enum

# Для тональности (установка: pip install dostoevsky)
try:
    from dostoevsky.tokenization import RegexTokenizer
    from dostoevsky.models import FastTextSocialNetworkModel

    DOSTOEVSKY_AVAILABLE = True
except ImportError:
    DOSTOEVSKY_AVAILABLE = False
    print("⚠️ Dostoevsky не установлен. Тональный анализ будет ограничен.")


class DestructiveCategory(Enum):
    """Категории деструктивного контента"""
    SAFE = "Безопастно"
    AGGRESSION = "Агрессия"
    SUICIDE = "Суецид"
    HATE_SPEECH = "Хейт спич"
    EXTREMISM = "Экстремизм"
    MISINFORMATION = "Дезинформация"
    MANIPULATION = "Манипуляции"
    NEGATIVE = "negative"  # сильный негатив без явных маркеров


class DestructiveLevel(Enum):
    """Уровни критичности"""
    NONE = 0  # безопасно
    LOW = 1  # низкий (дезинформация, манипуляция)
    MEDIUM = 2  # средний (агрессия, язык вражды)
    HIGH = 3  # высокий (экстремизм, суицид)


@dataclass
class ClassificationResult:
    """Результат классификации"""
    category: DestructiveCategory
    level: DestructiveLevel
    confidence: float
    reason: str
    matched_words: List[str]
    sentiment_score: float = 0.0


class DestructiveClassifier:
    """Классификатор деструктивного контента"""

    # Словари ключевых слов по категориям
    KEYWORDS = {
        DestructiveCategory.EXTREMISM: {
            'words': ['экстремизм', 'террор', 'взорвать', 'джихад', 'радикал',
                      'исламист', 'террорист', 'взрыв', 'оружие массового поражения'],
            'level': DestructiveLevel.HIGH
        },
        DestructiveCategory.SUICIDE: {
            'words': ['самоубийство', 'суицид', 'не хочу жить', 'сдохнуть',
                      'повеситься', 'прощай жизнь', 'хочу умереть', 'жизнь не имеет смысла',
                      'покончить с собой', 'убить себя', 'нет смысла жить'],
            'level': DestructiveLevel.HIGH
        },
        DestructiveCategory.AGGRESSION: {
            'words': ['убить', 'смерть', 'насилие', 'расправа', 'кровь', 'уничтожить',
                      'зарезать', 'застрелить', 'избить', 'смертный', 'убийство',
                      'жестокость', 'напасть', 'ликвидировать'],
            'level': DestructiveLevel.MEDIUM
        },
        DestructiveCategory.HATE_SPEECH: {
            'words': ['жиды', 'хачи', 'чурки', 'пиндосы', 'хохлы', 'нацики', 'фашисты',
                      'скинхед', 'черномазые', 'лимита', 'быдло', 'ватники', 'укропы'],
            'level': DestructiveLevel.MEDIUM
        },
        DestructiveCategory.MISINFORMATION: {
            'words': ['фейк', 'ложь', 'обман', 'неправда', 'заговор', 'скрывают правду',
                      'врут', 'обманывают', 'дезинформация', 'фейковый'],
            'level': DestructiveLevel.LOW
        },
        DestructiveCategory.MANIPULATION: {
            'words': ['кликбейт', 'шок', 'сенсация', 'невероятно', 'так вы не знали',
                      'все в шоке', 'обязательно к прочтению', 'срочно'],
            'level': DestructiveLevel.LOW
        }
    }

    # Паттерны для регулярных выражений
    PATTERNS = {
        'caps_rage': re.compile(r'[А-Я]{5,}'),  # много капса
        'exclamation_many': re.compile(r'!{3,}'),  # много восклицаний
        'question_many': re.compile(r'\?{3,}'),  # много вопросов
        'hate_patterns': re.compile(r'(ненавижу|ненависть|презираю|желаю смерти)', re.IGNORECASE)
    }

    def __init__(self, use_sentiment: bool = True):
        self.use_sentiment = use_sentiment and DOSTOEVSKY_AVAILABLE

        # Инициализация модели тональности
        if self.use_sentiment:
            try:
                tokenizer = RegexTokenizer()
                self.sentiment_model = FastTextSocialNetworkModel(tokenizer)
                print("✅ Модель тональности загружена")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки модели тональности: {e}")
                self.use_sentiment = False
        else:
            self.sentiment_model = None

    def _analyze_sentiment(self, text: str) -> Dict:
        """Анализ тональности текста"""
        if not self.use_sentiment or not text:
            return {'negative': 0.0, 'positive': 0.0, 'neutral': 1.0}

        try:
            result = self.sentiment_model.predict([text[:500]])[0]
            return {
                'negative': result.get('negative', 0.0),
                'positive': result.get('positive', 0.0),
                'neutral': result.get('neutral', 0.0)
            }
        except:
            return {'negative': 0.0, 'positive': 0.0, 'neutral': 1.0}

    def _text_statistics(self, text: str) -> Dict:
        """Статистический анализ текста"""
        stats = {
            'length': len(text),
            'words_count': len(text.split()),
            'exclamation_count': text.count('!'),
            'question_count': text.count('?'),
            'caps_ratio': 0.0,
            'has_rage_caps': False
        }

        # Доля капса
        caps_letters = sum(1 for c in text if c.isupper() and c.isalpha())
        total_letters = sum(1 for c in text if c.isalpha())
        if total_letters > 0:
            stats['caps_ratio'] = caps_letters / total_letters
            stats['has_rage_caps'] = stats['caps_ratio'] > 0.3

        return stats

    def _keyword_search(self, text: str) -> Tuple[Optional[DestructiveCategory], List[str], Optional[DestructiveLevel]]:
        """Поиск ключевых слов в тексте"""
        text_lower = text.lower()
        matched_words = []
        best_category = None
        best_level = DestructiveLevel.NONE

        for category, data in self.KEYWORDS.items():
            for word in data['words']:
                if word in text_lower:
                    matched_words.append(word)
                    if data['level'].value > best_level.value:
                        best_level = data['level']
                        best_category = category

        return best_category, matched_words, best_level

    def classify(self, text: str) -> ClassificationResult:
        """
        Основной метод классификации текста

        Args:
            text: Текст для анализа

        Returns:
            ClassificationResult с результатами
        """
        if not text or len(text) < 5:
            return ClassificationResult(
                category=DestructiveCategory.SAFE,
                level=DestructiveLevel.NONE,
                confidence=1.0,
                reason="текст слишком короткий",
                matched_words=[]
            )

        # 1. Словарный поиск
        keyword_category, matched_words, keyword_level = self._keyword_search(text)

        # 2. Анализ тональности
        sentiment = self._analyze_sentiment(text)
        neg_score = sentiment['negative']

        # 3. Статистический анализ
        stats = self._text_statistics(text)

        # 4. Принятие решения
        # Приоритет: экстремизм и суицид → сразу высокий уровень
        if keyword_category in [DestructiveCategory.EXTREMISM, DestructiveCategory.SUICIDE]:
            return ClassificationResult(
                category=keyword_category,
                level=DestructiveLevel.HIGH,
                confidence=min(0.8 + neg_score * 0.2, 0.95),
                reason=f"найдено ключевое слово: {matched_words[0] if matched_words else 'неизвестно'}",
                matched_words=matched_words,
                sentiment_score=neg_score
            )

        # 5. Комбинированная оценка
        # Если есть словарное совпадение
        if keyword_category and keyword_level:
            confidence = 0.6 + neg_score * 0.3
            # Усиление при наличии капс-ярости
            if stats['has_rage_caps']:
                confidence += 0.1

            return ClassificationResult(
                category=keyword_category,
                level=keyword_level,
                confidence=min(confidence, 0.95),
                reason=f"найдены маркеры: {', '.join(matched_words[:3])}",
                matched_words=matched_words,
                sentiment_score=neg_score
            )

        # 6. Сильный негатив без явных маркеров
        if neg_score > 0.75:
            return ClassificationResult(
                category=DestructiveCategory.NEGATIVE,
                level=DestructiveLevel.LOW,
                confidence=neg_score,
                reason=f"высокий уровень негатива ({neg_score:.2f})",
                matched_words=[],
                sentiment_score=neg_score
            )

        # 7. Безопасный текст
        return ClassificationResult(
            category=DestructiveCategory.SAFE,
            level=DestructiveLevel.NONE,
            confidence=1.0 - neg_score,
            reason="нет деструктивных маркеров",
            matched_words=[],
            sentiment_score=neg_score
        )


# Упрощённая функция для быстрого вызова
def classify_text(text: str) -> Tuple[str, int, float]:
    """
    Быстрая классификация текста

    Returns:
        (category, level, confidence)
    """
    classifier = DestructiveClassifier()
    result = classifier.classify(text)
    return (result.category.value, result.level.value, result.confidence)