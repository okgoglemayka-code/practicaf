"""
classifier.py - Классификация деструктивного контента
"""

import re
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
from enum import Enum

# Импорт словарей
from .dictionaries import (
    DESTRUCTIVE_DICTIONARIES,
    SYMBOL_REPLACEMENTS,
    COMPLEX_PATTERNS,
    get_categories_levels
)


class DestructiveCategory(Enum):
    SAFE = "safe"
    AGGRESSION = "aggression"
    SUICIDE = "suicide"
    SUICIDE_CALLS = "suicide_calls"
    HATE_SPEECH = "hate_speech"
    EXTREMISM = "extremism"
    MISINFORMATION = "misinformation"
    MANIPULATION = "manipulation"
    DRUGS = "drugs"
    VIOLENCE_CALLS = "violence_calls"
    BULLYING = "bullying"
    NEGATIVE = "negative"


class DestructiveLevel(Enum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass
class ClassificationResult:
    category: DestructiveCategory
    level: DestructiveLevel
    confidence: float
    reason: str
    matched_words: List[str]
    sentiment_score: float = 0.0


def normalize_text(text: str) -> str:
    """Нормализация текста: замена символов на буквы"""
    text_lower = text.lower()
    for symbol, replacement in SYMBOL_REPLACEMENTS.items():
        text_lower = text_lower.replace(symbol, replacement)
    return text_lower


class DestructiveClassifier:
    """Классификатор деструктивного контента"""

    def __init__(self):
        self.use_transformers = False
        self._prepare_dictionaries()
        print("✅ Классификатор загружен (расширенный словарь)")

    def _prepare_dictionaries(self):
        """Подготовка словарей из внешнего файла"""
        self.keywords = {}
        self.category_levels = {}

        for category_name, data in DESTRUCTIVE_DICTIONARIES.items():
            # Преобразуем строку в enum
            cat_enum = getattr(DestructiveCategory, category_name.upper(), None)
            if cat_enum:
                self.keywords[cat_enum] = data['keywords']
                self.category_levels[cat_enum] = DestructiveLevel(data['level'])

    def _analyze_sentiment_simple(self, text: str) -> Dict:
        """Упрощённый анализ тональности"""
        negative_words = ['плохо', 'ужасно', 'ненавижу', 'бесит', 'кошмар', 'ужас', 'отвратительно']
        positive_words = ['хорошо', 'отлично', 'прекрасно', 'спасибо', 'круто', 'нравится']

        text_lower = text.lower()
        neg_count = sum(1 for w in negative_words if w in text_lower)
        pos_count = sum(1 for w in positive_words if w in text_lower)
        total = neg_count + pos_count

        if total == 0:
            return {'negative': 0.0, 'positive': 0.0, 'neutral': 1.0}
        return {
            'negative': neg_count / total,
            'positive': pos_count / total,
            'neutral': 0.0
        }

    def _keyword_search(self, text: str) -> Tuple[Optional[DestructiveCategory], List[str], Optional[DestructiveLevel]]:
        """Поиск ключевых слов в тексте"""
        text_lower = text.lower()
        matched_words = []
        best_category = None
        best_level = DestructiveLevel.NONE

        # Прямой поиск по словарям
        for category, words in self.keywords.items():
            for word in words:
                if word in text_lower:
                    matched_words.append(word)
                    level = self.category_levels.get(category, DestructiveLevel.MEDIUM)
                    if level.value > best_level.value:
                        best_level = level
                        best_category = category

        # Поиск по сложным паттернам (регулярные выражения)
        for category_name, patterns in COMPLEX_PATTERNS.items():
            cat_enum = getattr(DestructiveCategory, category_name.upper(), None)
            if cat_enum:
                for pattern in patterns:
                    if re.search(pattern, text_lower):
                        matched_words.append(f"regex:{category_name}")
                        level = self.category_levels.get(cat_enum, DestructiveLevel.MEDIUM)
                        if level.value > best_level.value:
                            best_level = level
                            best_category = cat_enum

        return best_category, matched_words, best_level

    def _text_statistics(self, text: str) -> Dict:
        """Статистический анализ текста"""
        caps_count = sum(1 for c in text if c.isupper())
        total_letters = sum(1 for c in text if c.isalpha())
        caps_ratio = caps_count / total_letters if total_letters > 0 else 0

        return {
            'length': len(text),
            'exclamation_count': text.count('!'),
            'question_count': text.count('?'),
            'caps_ratio': caps_ratio,
            'has_rage_caps': caps_ratio > 0.3
        }

    def classify(self, text: str) -> ClassificationResult:
        """Основной метод классификации"""
        if not text or len(text) < 3:
            return ClassificationResult(
                category=DestructiveCategory.SAFE,
                level=DestructiveLevel.NONE,
                confidence=1.0,
                reason="текст слишком короткий",
                matched_words=[]
            )

        # Нормализация текста
        normalized_text = normalize_text(text)

        # 1. Словарный поиск
        keyword_category, matched_words, keyword_level = self._keyword_search(normalized_text)

        # 2. Анализ тональности
        sentiment = self._analyze_sentiment_simple(text)
        neg_score = sentiment['negative']

        # 3. Статистический анализ
        stats = self._text_statistics(text)

        # 4. Принятие решения с приоритетами
        # Высокий приоритет: экстремизм, призывы к суициду других, прямые угрозы
        if keyword_category in [DestructiveCategory.EXTREMISM,
                                 DestructiveCategory.SUICIDE_CALLS,
                                 DestructiveCategory.VIOLENCE_CALLS]:
            return ClassificationResult(
                category=keyword_category,
                level=DestructiveLevel.HIGH,
                confidence=0.95,
                reason=f"найдена критическая угроза: {matched_words[0] if matched_words else '?'}",
                matched_words=matched_words[:5],
                sentiment_score=neg_score
            )

        # Средний приоритет: суицид, агрессия, язык вражды, наркотики, буллинг
        if keyword_category and keyword_level and keyword_level.value >= 2:
            confidence = 0.6 + neg_score * 0.3
            if stats['has_rage_caps']:
                confidence += 0.1
            if len(matched_words) > 2:
                confidence += 0.05

            return ClassificationResult(
                category=keyword_category,
                level=keyword_level,
                confidence=min(confidence, 0.95),
                reason=f"найдены маркеры: {', '.join(matched_words[:3])}",
                matched_words=matched_words[:5],
                sentiment_score=neg_score
            )

        # Низкий приоритет: дезинформация, манипуляция
        if keyword_category:
            confidence = 0.5 + neg_score * 0.2
            return ClassificationResult(
                category=keyword_category,
                level=keyword_level,
                confidence=min(confidence, 0.85),
                reason=f"найдены маркеры: {', '.join(matched_words[:3])}",
                matched_words=matched_words[:5],
                sentiment_score=neg_score
            )

        # Сильный негатив без явных маркеров
        if neg_score > 0.7:
            return ClassificationResult(
                category=DestructiveCategory.NEGATIVE,
                level=DestructiveLevel.LOW,
                confidence=neg_score,
                reason=f"высокий уровень негатива ({neg_score:.2f})",
                matched_words=[],
                sentiment_score=neg_score
            )

        return ClassificationResult(
            category=DestructiveCategory.SAFE,
            level=DestructiveLevel.NONE,
            confidence=1.0 - neg_score,
            reason="нет деструктивных маркеров",
            matched_words=[],
            sentiment_score=neg_score
        )


def classify_text(text: str) -> Tuple[str, int, float]:
    """Быстрая классификация текста"""
    classifier = DestructiveClassifier()
    result = classifier.classify(text)
    return (result.category.value, result.level.value, result.confidence)