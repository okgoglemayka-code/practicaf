"""
classifier.py - Классификация деструктивного контента

Новая версия: балльная модель по нескольким методам.
Каждый метод добавляет или снижает итоговый риск:
1) критические фразы;
2) лемматизированные маркеры;
3) regex-паттерны;
4) контекстные сочетания;
5) тональность;
6) статистика текста;
7) безопасные исключения.
"""

import re
from typing import Dict, Tuple, Optional, List, Set
from dataclasses import dataclass, field
from enum import Enum

from .dictionaries import (
    DESTRUCTIVE_DICTIONARIES,
    LEMMATIZED_DICTIONARIES,
    SYMBOL_REPLACEMENTS,
    COMPLEX_PATTERNS,
    SCORING_RULES,
    SAFE_CONTEXTS,
    NEGATIVE_SENTIMENT_WORDS,
    POSITIVE_SENTIMENT_WORDS,
    SCORE_THRESHOLDS,
)
from .lemmatizer import lemmatize, get_lemmatizer


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
    score: int = 0
    score_details: List[str] = field(default_factory=list)


def normalize_text(text: str) -> str:
    """Нормализация текста: нижний регистр + замена похожих символов."""
    if not text:
        return ""

    text_lower = text.lower()
    for symbol, replacement in SYMBOL_REPLACEMENTS.items():
        text_lower = text_lower.replace(symbol, replacement)

    text_lower = re.sub(r"\s+", " ", text_lower)
    return text_lower.strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    """Поиск фразы с нормализацией пробелов."""
    phrase_norm = re.sub(r"\s+", " ", phrase.lower()).strip()
    return phrase_norm in text


class DestructiveClassifier:
    """Классификатор деструктивного контента с балльной моделью."""

    def __init__(self, use_lemmatization: bool = True):
        self.use_lemmatization = use_lemmatization
        self.use_transformers = False

        if use_lemmatization:
            self.lemmatizer = get_lemmatizer()
            self.keywords = {}
            self.category_levels = {}
            for category_name, data in LEMMATIZED_DICTIONARIES.items():
                cat_enum = getattr(DestructiveCategory, category_name.upper(), None)
                if cat_enum:
                    self.keywords[cat_enum] = data['lemmas']
                    self.category_levels[cat_enum] = DestructiveLevel(data['level'])
            print("✅ Классификатор загружен (scoring + лемматизация)")
        else:
            self._prepare_dictionaries()
            print("✅ Классификатор загружен (scoring без лемматизации)")

    def _prepare_dictionaries(self):
        """Подготовка обычных словарей без лемматизации."""
        self.keywords = {}
        self.category_levels = {}
        for category_name, data in DESTRUCTIVE_DICTIONARIES.items():
            cat_enum = getattr(DestructiveCategory, category_name.upper(), None)
            if cat_enum:
                self.keywords[cat_enum] = data['keywords']
                self.category_levels[cat_enum] = DestructiveLevel(data['level'])

    def _get_search_forms(self, text: str) -> Tuple[str, str, Set[str]]:
        """
        Возвращает:
        - normalized_text: текст после замены символов;
        - lemma_text: строка лемм;
        - lemma_set: множество лемм для точного поиска слов.
        """
        normalized_text = normalize_text(text)

        if self.use_lemmatization:
            lemma_text = lemmatize(normalized_text)
        else:
            lemma_text = normalized_text

        lemma_set = set(re.findall(r"[а-яёa-z0-9]+", lemma_text.lower()))
        return normalized_text, lemma_text, lemma_set

    def _analyze_sentiment_simple(self, text: str, lemma_set: Optional[Set[str]] = None) -> Dict:
        """Упрощённый анализ тональности с учётом лемм."""
        text_lower = normalize_text(text)
        lemmas = lemma_set or set()

        neg_count = 0
        pos_count = 0

        for word in NEGATIVE_SENTIMENT_WORDS:
            if word in text_lower or word in lemmas:
                neg_count += 1

        for word in POSITIVE_SENTIMENT_WORDS:
            if word in text_lower or word in lemmas:
                pos_count += 1

        total = neg_count + pos_count
        if total == 0:
            return {'negative': 0.0, 'positive': 0.0, 'neutral': 1.0}

        return {
            'negative': neg_count / total,
            'positive': pos_count / total,
            'neutral': 0.0,
        }

    def _text_statistics(self, text: str) -> Dict:
        """Статистический анализ текста."""
        caps_count = sum(1 for c in text if c.isupper())
        total_letters = sum(1 for c in text if c.isalpha())
        caps_ratio = caps_count / total_letters if total_letters > 0 else 0

        return {
            'length': len(text),
            'exclamation_count': text.count('!'),
            'question_count': text.count('?'),
            'caps_ratio': caps_ratio,
            'has_rage_caps': caps_ratio > 0.35 and total_letters >= 8,
        }

    def _keyword_search(self, text: str) -> Tuple[Optional[DestructiveCategory], List[str], Optional[DestructiveLevel]]:
        """
        Старый интерфейс оставлен для совместимости.
        Теперь используется точный поиск по леммам, а не простое `word in text`.
        """
        normalized_text, lemma_text, lemma_set = self._get_search_forms(text)
        matched_words = []
        best_category = None
        best_level = DestructiveLevel.NONE

        for category, words in self.keywords.items():
            for word in words:
                word_norm = normalize_text(word)
                if " " in word_norm:
                    found = _contains_phrase(normalized_text, word_norm)
                else:
                    found = word_norm in lemma_set or word_norm in lemma_text.split()

                if found:
                    matched_words.append(word)
                    level = self.category_levels.get(category, DestructiveLevel.MEDIUM)
                    if level.value > best_level.value:
                        best_level = level
                        best_category = category

        return best_category, matched_words, best_level

    def _safe_context_penalty(self, normalized_text: str) -> Tuple[int, List[str]]:
        """Ищет безопасные/ироничные контексты и снижает риск."""
        penalty = 0
        details = []

        for phrase in SAFE_CONTEXTS:
            if _contains_phrase(normalized_text, normalize_text(phrase)):
                penalty -= 4
                details.append(f"исключение: '{phrase}' (-4)")

        return penalty, details

    def _score_regex_patterns(self, normalized_text: str) -> Dict[DestructiveCategory, Dict]:
        """Баллы за регулярные выражения для замаскированных слов."""
        scores: Dict[DestructiveCategory, Dict] = {}

        for category_name, patterns in COMPLEX_PATTERNS.items():
            cat_enum = getattr(DestructiveCategory, category_name.upper(), None)
            if not cat_enum:
                continue

            for pattern in patterns:
                if re.search(pattern, normalized_text, flags=re.IGNORECASE):
                    entry = scores.setdefault(cat_enum, {'score': 0, 'matches': [], 'details': []})
                    entry['score'] += 3
                    entry['matches'].append(f"regex:{category_name}")
                    entry['details'].append(f"regex-паттерн {category_name} (+3)")

        return scores

    def _score_category(
        self,
        category_name: str,
        rules: Dict,
        normalized_text: str,
        lemma_set: Set[str],
        neg_score: float,
        stats: Dict,
    ) -> Dict:
        """Считает баллы для одной категории."""
        score = 0
        matches: List[str] = []
        details: List[str] = []

        # 1. Критические фразы: самый сильный сигнал.
        for phrase in rules.get('critical_phrases', []):
            phrase_norm = normalize_text(phrase)
            if _contains_phrase(normalized_text, phrase_norm):
                score += 7
                matches.append(phrase)
                details.append(f"критическая фраза: '{phrase}' (+7)")

        # 2. Сильные маркеры.
        strong_found = []
        for lemma in rules.get('strong_lemmas', []):
            if lemma in lemma_set:
                strong_found.append(lemma)
        if strong_found:
            add = min(6, 3 * len(strong_found))
            score += add
            matches.extend(strong_found)
            details.append(f"сильные маркеры: {', '.join(strong_found[:5])} (+{add})")

        # 3. Средние маркеры.
        medium_found = []
        for lemma in rules.get('medium_lemmas', []):
            if lemma in lemma_set:
                medium_found.append(lemma)
        if medium_found:
            add = min(4, 2 * len(medium_found))
            score += add
            matches.extend(medium_found)
            details.append(f"средние маркеры: {', '.join(medium_found[:5])} (+{add})")

        # 4. Слабые маркеры: не должны сами делать высокий риск.
        weak_found = []
        for lemma in rules.get('weak_lemmas', []):
            if lemma in lemma_set:
                weak_found.append(lemma)
        if weak_found:
            add = min(2, len(weak_found))
            score += add
            matches.extend(weak_found)
            details.append(f"слабые маркеры: {', '.join(weak_found[:5])} (+{add})")

        # 5. Контекст. Сам по себе почти не опасен, но усиливает сильные маркеры.
        context_found = [lemma for lemma in rules.get('context_lemmas', []) if lemma in lemma_set]
        if context_found and (strong_found or medium_found or matches):
            score += 2
            matches.extend(context_found)
            details.append(f"опасный контекст: {', '.join(context_found[:5])} (+2)")

        # 6. Специальное правило: violence_calls нельзя поднимать из-за одной 'школы'.
        if category_name == 'violence_calls':
            has_weapon_or_attack = bool(strong_found) or any('расстрел' in m or 'взорв' in m for m in matches)
            has_school_context = bool(context_found)
            if has_weapon_or_attack and has_school_context:
                score += 3
                details.append("сочетание угрозы и учебного контекста (+3)")
            elif has_school_context and not has_weapon_or_attack:
                score = min(score, 1)
                details.append("учебный контекст без угрозы: риск ограничен")

        # 7. Специальное правило: drugs требует вещества + контекст продажи/поиска для medium/high.
        if category_name == 'drugs':
            has_trade_context = any(w in lemma_set for w in rules.get('context_lemmas', []))
            if strong_found or medium_found:
                if has_trade_context:
                    score += 2
                    details.append("контекст покупки/продажи наркотиков (+2)")
                else:
                    score = min(score, 4)
                    details.append("нет контекста покупки/продажи: риск ограничен")

        # 8. Тональность добавляет немного, но не решает сама.
        if neg_score >= 0.75 and score > 0:
            score += 1
            details.append(f"высокая негативная тональность {neg_score:.2f} (+1)")

        # 9. Статистика текста.
        if stats.get('has_rage_caps') and score > 0:
            score += 1
            details.append("много заглавных букв / капс (+1)")
        if stats.get('exclamation_count', 0) >= 3 and score > 0:
            score += 1
            details.append("много восклицательных знаков (+1)")

        return {
            'category': category_name,
            'score': max(score, 0),
            'matches': list(dict.fromkeys(matches)),
            'details': details,
        }

    def _score_to_level(self, score: int, category: DestructiveCategory) -> DestructiveLevel:
        """Перевод итогового балла в уровень критичности."""
        if score <= SCORE_THRESHOLDS['safe_max']:
            return DestructiveLevel.NONE
        if score <= SCORE_THRESHOLDS['low_max']:
            return DestructiveLevel.LOW
        if score <= SCORE_THRESHOLDS['medium_max']:
            return DestructiveLevel.MEDIUM
        return DestructiveLevel.HIGH

    def _confidence_from_score(self, score: int, neg_score: float) -> float:
        """Уверенность на основе итогового балла и тональности."""
        if score <= 0:
            return round(max(0.5, 1.0 - neg_score), 2)
        confidence = 0.45 + min(score, 10) * 0.05 + neg_score * 0.10
        return round(min(confidence, 0.95), 2)

    def classify(self, text: str) -> ClassificationResult:
        """Основной метод классификации по балльной модели."""
        if not text or len(text.strip()) < 3:
            return ClassificationResult(
                category=DestructiveCategory.SAFE,
                level=DestructiveLevel.NONE,
                confidence=1.0,
                reason="текст слишком короткий",
                matched_words=[],
                score=0,
                score_details=[]
            )

        normalized_text, lemma_text, lemma_set = self._get_search_forms(text)
        sentiment = self._analyze_sentiment_simple(text, lemma_set)
        neg_score = sentiment['negative']
        stats = self._text_statistics(text)

        category_scores: Dict[DestructiveCategory, Dict] = {}

        # 1. Баллы по словарям и контекстам.
        for category_name, rules in SCORING_RULES.items():
            cat_enum = getattr(DestructiveCategory, category_name.upper(), None)
            if not cat_enum:
                continue
            category_scores[cat_enum] = self._score_category(
                category_name=category_name,
                rules=rules,
                normalized_text=normalized_text,
                lemma_set=lemma_set,
                neg_score=neg_score,
                stats=stats,
            )

        # 2. Баллы за regex-паттерны.
        regex_scores = self._score_regex_patterns(normalized_text)
        for cat_enum, regex_data in regex_scores.items():
            entry = category_scores.setdefault(cat_enum, {
                'category': cat_enum.value,
                'score': 0,
                'matches': [],
                'details': [],
            })
            entry['score'] += regex_data['score']
            entry['matches'].extend(regex_data['matches'])
            entry['details'].extend(regex_data['details'])

        # 3. Безопасные исключения применяются к общей оценке.
        penalty, penalty_details = self._safe_context_penalty(normalized_text)
        if penalty < 0:
            for entry in category_scores.values():
                if entry['score'] > 0:
                    entry['score'] = max(0, entry['score'] + penalty)
                    entry['details'].extend(penalty_details)

        # 4. Если нет словарных признаков, но есть сильный негатив — LOW negative.
        best_cat = None
        best_data = None
        for cat_enum, data in category_scores.items():
            if best_data is None or data['score'] > best_data['score']:
                best_cat = cat_enum
                best_data = data

        if not best_data or best_data['score'] <= 1:
            if neg_score > 0.75:
                return ClassificationResult(
                    category=DestructiveCategory.NEGATIVE,
                    level=DestructiveLevel.LOW,
                    confidence=round(neg_score, 2),
                    reason=f"высокая негативная тональность ({neg_score:.2f}), но нет критических маркеров",
                    matched_words=[],
                    sentiment_score=neg_score,
                    score=2,
                    score_details=[f"негативная тональность (+2): {neg_score:.2f}"]
                )

            return ClassificationResult(
                category=DestructiveCategory.SAFE,
                level=DestructiveLevel.NONE,
                confidence=round(max(0.7, 1.0 - neg_score), 2),
                reason="нет достаточных деструктивных маркеров",
                matched_words=[],
                sentiment_score=neg_score,
                score=0,
                score_details=penalty_details
            )

        final_score = int(best_data['score'])
        final_level = self._score_to_level(final_score, best_cat)
        confidence = self._confidence_from_score(final_score, neg_score)

        if final_level == DestructiveLevel.NONE:
            return ClassificationResult(
                category=DestructiveCategory.SAFE,
                level=DestructiveLevel.NONE,
                confidence=round(max(0.7, 1.0 - neg_score), 2),
                reason="балл риска ниже порога",
                matched_words=best_data['matches'][:5],
                sentiment_score=neg_score,
                score=final_score,
                score_details=best_data['details']
            )

        reason = f"итоговый балл риска: {final_score}; " + "; ".join(best_data['details'][:3])

        return ClassificationResult(
            category=best_cat,
            level=final_level,
            confidence=confidence,
            reason=reason[:500],
            matched_words=best_data['matches'][:8],
            sentiment_score=neg_score,
            score=final_score,
            score_details=best_data['details']
        )


def classify_text(text: str, use_lemmatization: bool = True) -> Tuple[str, int, float]:
    """Быстрая классификация текста."""
    classifier = DestructiveClassifier(use_lemmatization=use_lemmatization)
    result = classifier.classify(text)
    return (result.category.value, result.level.value, result.confidence)
