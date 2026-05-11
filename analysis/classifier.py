"""
classifier.py - Классификация деструктивного контента

Версия с обучаемым расчётом уверенности.

Основная классификация выполняется балльной моделью:
1) критические фразы;
2) лемматизированные маркеры;
3) regex-паттерны;
4) контекстные сочетания;
5) тональность;
6) статистика текста;
7) безопасные исключения.

Уверенность рассчитывается по обучаемой формуле:

confidence = sigmoid(b + w1*M + w2*T + w3*S)

где:
M - словарный вклад;
T - вклад тональности;
S - статистический вклад;
w1, w2, w3 - обучаемые коэффициенты.
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
from .nlp_ai import get_ai_analyzer
from .confidence_model import ConfidenceModel


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

        # Дополнительный NLP/AI-анализатор.
        self.ai_analyzer = get_ai_analyzer()

        # Новая обучаемая модель уверенности.
        self.confidence_model = ConfidenceModel()

        if use_lemmatization:
            self.lemmatizer = get_lemmatizer()
            self.keywords = {}
            self.category_levels = {}

            for category_name, data in LEMMATIZED_DICTIONARIES.items():
                cat_enum = getattr(DestructiveCategory, category_name.upper(), None)

                if cat_enum:
                    self.keywords[cat_enum] = data["lemmas"]
                    self.category_levels[cat_enum] = DestructiveLevel(data["level"])

            print("✅ Классификатор загружен (scoring + лемматизация + обучаемая уверенность)")
        else:
            self._prepare_dictionaries()
            print("✅ Классификатор загружен (scoring без лемматизации + обучаемая уверенность)")

    def _prepare_dictionaries(self):
        """Подготовка обычных словарей без лемматизации."""
        self.keywords = {}
        self.category_levels = {}

        for category_name, data in DESTRUCTIVE_DICTIONARIES.items():
            cat_enum = getattr(DestructiveCategory, category_name.upper(), None)

            if cat_enum:
                self.keywords[cat_enum] = data["keywords"]
                self.category_levels[cat_enum] = DestructiveLevel(data["level"])

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
            return {
                "negative": 0.0,
                "positive": 0.0,
                "neutral": 1.0
            }

        return {
            "negative": neg_count / total,
            "positive": pos_count / total,
            "neutral": 0.0
        }

    def _text_statistics(self, text: str) -> Dict:
        """Статистический анализ текста."""
        caps_count = sum(1 for c in text if c.isupper())
        total_letters = sum(1 for c in text if c.isalpha())

        caps_ratio = caps_count / total_letters if total_letters > 0 else 0

        return {
            "length": len(text),
            "exclamation_count": text.count("!"),
            "question_count": text.count("?"),
            "caps_ratio": caps_ratio,
            "has_rage_caps": caps_ratio > 0.35 and total_letters >= 8
        }

    def _keyword_search(self, text: str) -> Tuple[Optional[DestructiveCategory], List[str], Optional[DestructiveLevel]]:
        """
        Старый интерфейс оставлен для совместимости.
        Теперь используется точный поиск по леммам.
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
                    entry = scores.setdefault(cat_enum, {
                        "score": 0,
                        "matches": [],
                        "details": []
                    })

                    entry["score"] += 3
                    entry["matches"].append(f"regex:{category_name}")
                    entry["details"].append(f"regex-паттерн {category_name} (+3)")

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

        # 1. Критические фразы.
        for phrase in rules.get("critical_phrases", []):
            phrase_norm = normalize_text(phrase)

            if _contains_phrase(normalized_text, phrase_norm):
                score += 7
                matches.append(phrase)
                details.append(f"критическая фраза: '{phrase}' (+7)")

        # 2. Сильные маркеры.
        strong_found = []

        for lemma in rules.get("strong_lemmas", []):
            if lemma in lemma_set:
                strong_found.append(lemma)

        if strong_found:
            add = min(6, 3 * len(strong_found))
            score += add
            matches.extend(strong_found)
            details.append(f"сильные маркеры: {', '.join(strong_found[:5])} (+{add})")

        # 3. Средние маркеры.
        medium_found = []

        for lemma in rules.get("medium_lemmas", []):
            if lemma in lemma_set:
                medium_found.append(lemma)

        if medium_found:
            add = min(4, 2 * len(medium_found))
            score += add
            matches.extend(medium_found)
            details.append(f"средние маркеры: {', '.join(medium_found[:5])} (+{add})")

        # 4. Слабые маркеры.
        weak_found = []

        for lemma in rules.get("weak_lemmas", []):
            if lemma in lemma_set:
                weak_found.append(lemma)

        if weak_found:
            add = min(2, len(weak_found))
            score += add
            matches.extend(weak_found)
            details.append(f"слабые маркеры: {', '.join(weak_found[:5])} (+{add})")

        # 5. Контекст.
        context_found = [
            lemma for lemma in rules.get("context_lemmas", [])
            if lemma in lemma_set
        ]

        if context_found and (strong_found or medium_found or matches):
            score += 2
            matches.extend(context_found)
            details.append(f"опасный контекст: {', '.join(context_found[:5])} (+2)")

        # 6. Специальное правило для violence_calls.
        if category_name == "violence_calls":
            has_weapon_or_attack = bool(strong_found) or any(
                "расстрел" in m or "взорв" in m for m in matches
            )
            has_school_context = bool(context_found)

            if has_weapon_or_attack and has_school_context:
                score += 3
                details.append("сочетание угрозы и учебного контекста (+3)")
            elif has_school_context and not has_weapon_or_attack:
                score = min(score, 1)
                details.append("учебный контекст без угрозы: риск ограничен")

        # 7. Специальное правило для drugs.
        if category_name == "drugs":
            has_trade_context = any(
                w in lemma_set for w in rules.get("context_lemmas", [])
            )

            if strong_found or medium_found:
                if has_trade_context:
                    score += 2
                    details.append("контекст покупки/продажи наркотиков (+2)")
                else:
                    score = min(score, 4)
                    details.append("нет контекста покупки/продажи: риск ограничен")

        # 8. Тональность усиливает уже найденные признаки.
        if neg_score >= 0.75 and score > 0:
            score += 1
            details.append(f"высокая негативная тональность {neg_score:.2f} (+1)")

        # 9. Статистика текста.
        if stats.get("has_rage_caps") and score > 0:
            score += 1
            details.append("много заглавных букв / капс (+1)")

        if stats.get("exclamation_count", 0) >= 3 and score > 0:
            score += 1
            details.append("много восклицательных знаков (+1)")

        return {
            "category": category_name,
            "score": max(score, 0),
            "matches": list(dict.fromkeys(matches)),
            "details": details
        }

    def _score_to_level(self, score: int, category: DestructiveCategory) -> DestructiveLevel:
        """Перевод итогового балла в уровень критичности."""
        if score <= SCORE_THRESHOLDS["safe_max"]:
            return DestructiveLevel.NONE

        if score <= SCORE_THRESHOLDS["low_max"]:
            return DestructiveLevel.LOW

        if score <= SCORE_THRESHOLDS["medium_max"]:
            return DestructiveLevel.MEDIUM

        return DestructiveLevel.HIGH

    def _confidence_from_components(self, score: int, neg_score: float, stats: Dict) -> float:
        """
        Расчёт уверенности по обучаемой модели.

        M - словарный вклад;
        T - тональность;
        S - статистические признаки.
        """

        # M: словарный вклад.
        # Итоговый score может быть больше 10, поэтому ограничиваем его
        # и переводим в диапазон 0..1.
        m = min(score, 10) / 10

        # T: тональность.
        # Чем выше негативность, тем выше вклад.
        t = max(0.0, min(neg_score, 1.0))

        # S: статистический вклад.
        # Капс и множественные восклицания усиливают уверенность.
        s = 0.0

        if stats.get("has_rage_caps"):
            s += 0.5

        if stats.get("exclamation_count", 0) >= 3:
            s += 0.5

        s = min(s, 1.0)

        return self.confidence_model.predict(m, t, s)

    def _category_from_value(self, value: str) -> DestructiveCategory:
        """Безопасное преобразование строки категории в Enum."""
        for category in DestructiveCategory:
            if category.value == value:
                return category

        return DestructiveCategory.SAFE

    def _combine_with_ai(
        self,
        base_result: ClassificationResult,
        text: str,
    ) -> ClassificationResult:
        """
        Объединяет результат scoring-модели с дополнительной NLP/AI-моделью.

        AI не заменяет базовую модель полностью:
        - если AI уверен и видит более высокий риск, итоговый уровень повышается;
        - если AI уверен, что контекст безопасный, риск может быть снижен;
        - при ошибке AI возвращается исходный результат.
        """

        base_payload = {
            "category": base_result.category.value,
            "level": base_result.level.value,
            "score": base_result.score,
            "confidence": base_result.confidence,
            "reason": base_result.reason,
            "matched_words": base_result.matched_words,
        }

        if not self.ai_analyzer.should_analyze(
            base_score=base_result.score,
            base_confidence=base_result.confidence,
            base_category=base_result.category.value,
            text=text,
        ):
            return base_result

        ai = self.ai_analyzer.analyze(text=text, base_result=base_payload)
        details = list(base_result.score_details)

        if not ai.available:
            details.append(f"AI/NLP слой не применён: {ai.reason}")
            base_result.score_details = details
            return base_result

        ai_category = self._category_from_value(ai.category)
        ai_level = DestructiveLevel(ai.level)

        # Случай 1: AI уверенно повышает опасность.
        if ai.confidence >= 0.70 and ai_level.value > base_result.level.value:
            new_score = max(base_result.score, ai.level * 3)
            new_confidence = round(
                min(0.97, (base_result.confidence + ai.confidence) / 2 + 0.08),
                2
            )

            details.append(f"AI/NLP повысил риск: {ai.reason} (conf={ai.confidence:.2f})")

            return ClassificationResult(
                category=ai_category,
                level=ai_level,
                confidence=new_confidence,
                reason=(base_result.reason + f"; AI/NLP: {ai.reason}")[:500],
                matched_words=list(dict.fromkeys(base_result.matched_words + ai.matched_words))[:10],
                sentiment_score=base_result.sentiment_score,
                score=new_score,
                score_details=details,
            )

        # Случай 2: AI уверенно видит безопасный контекст.
        if (
            ai.confidence >= 0.80
            and ai_level == DestructiveLevel.NONE
            and base_result.level in {DestructiveLevel.LOW, DestructiveLevel.MEDIUM}
        ):
            lowered_level = (
                DestructiveLevel.LOW
                if base_result.level == DestructiveLevel.MEDIUM
                else DestructiveLevel.NONE
            )

            lowered_category = (
                DestructiveCategory.NEGATIVE
                if lowered_level == DestructiveLevel.LOW
                else DestructiveCategory.SAFE
            )

            lowered_score = min(
                base_result.score,
                3 if lowered_level == DestructiveLevel.LOW else 1
            )

            details.append(
                f"AI/NLP снизил риск как безопасный контекст: {ai.reason} "
                f"(conf={ai.confidence:.2f})"
            )

            return ClassificationResult(
                category=lowered_category,
                level=lowered_level,
                confidence=round(max(base_result.confidence, ai.confidence), 2),
                reason=(base_result.reason + f"; AI/NLP снизил риск: {ai.reason}")[:500],
                matched_words=base_result.matched_words,
                sentiment_score=base_result.sentiment_score,
                score=lowered_score,
                score_details=details,
            )

        # Случай 3: AI подтверждает решение.
        if (
            ai.confidence >= 0.70
            and ai_category == base_result.category
            and ai_level == base_result.level
        ):
            details.append(f"AI/NLP подтвердил решение: {ai.reason} (conf={ai.confidence:.2f})")

            base_result.confidence = round(
                min(0.97, max(base_result.confidence, ai.confidence)),
                2
            )
            base_result.reason = (
                base_result.reason + f"; AI/NLP подтвердил: {ai.reason}"
            )[:500]
            base_result.matched_words = list(
                dict.fromkeys(base_result.matched_words + ai.matched_words)
            )[:10]
            base_result.score_details = details

            return base_result

        # Случай 4: AI дал другое мнение, но не меняет итог.
        details.append(
            f"AI/NLP мнение без изменения решения: category={ai.category}, "
            f"level={ai.level}, conf={ai.confidence:.2f}, reason={ai.reason}"
        )

        base_result.score_details = details
        return base_result

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
        neg_score = sentiment["negative"]
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
                "category": cat_enum.value,
                "score": 0,
                "matches": [],
                "details": [],
            })

            entry["score"] += regex_data["score"]
            entry["matches"].extend(regex_data["matches"])
            entry["details"].extend(regex_data["details"])

        # 3. Безопасные исключения.
        penalty, penalty_details = self._safe_context_penalty(normalized_text)

        if penalty < 0:
            for entry in category_scores.values():
                if entry["score"] > 0:
                    entry["score"] = max(0, entry["score"] + penalty)
                    entry["details"].extend(penalty_details)

        # 4. Выбираем категорию с максимальным баллом.
        best_cat = None
        best_data = None

        for cat_enum, data in category_scores.items():
            if best_data is None or data["score"] > best_data["score"]:
                best_cat = cat_enum
                best_data = data

        # 5. Если балл слишком низкий, но есть сильная негативность.
        if not best_data or best_data["score"] <= 1:
            if neg_score > 0.75:
                confidence = self._confidence_from_components(
                    score=2,
                    neg_score=neg_score,
                    stats=stats
                )

                base_result = ClassificationResult(
                    category=DestructiveCategory.NEGATIVE,
                    level=DestructiveLevel.LOW,
                    confidence=confidence,
                    reason=f"высокая негативная тональность ({neg_score:.2f}), но нет критических маркеров",
                    matched_words=[],
                    sentiment_score=neg_score,
                    score=2,
                    score_details=[f"негативная тональность (+2): {neg_score:.2f}"]
                )

                return self._combine_with_ai(base_result, text)

            base_result = ClassificationResult(
                category=DestructiveCategory.SAFE,
                level=DestructiveLevel.NONE,
                confidence=round(max(0.7, 1.0 - neg_score), 2),
                reason="нет достаточных деструктивных маркеров",
                matched_words=[],
                sentiment_score=neg_score,
                score=0,
                score_details=penalty_details
            )

            return self._combine_with_ai(base_result, text)

        # 6. Формируем итоговый результат.
        final_score = int(best_data["score"])
        final_level = self._score_to_level(final_score, best_cat)

        confidence = self._confidence_from_components(
            score=final_score,
            neg_score=neg_score,
            stats=stats
        )

        if final_level == DestructiveLevel.NONE:
            base_result = ClassificationResult(
                category=DestructiveCategory.SAFE,
                level=DestructiveLevel.NONE,
                confidence=round(max(0.7, 1.0 - neg_score), 2),
                reason="балл риска ниже порога",
                matched_words=best_data["matches"][:5],
                sentiment_score=neg_score,
                score=final_score,
                score_details=best_data["details"]
            )

            return self._combine_with_ai(base_result, text)

        reason = f"итоговый балл риска: {final_score}; " + "; ".join(best_data["details"][:3])

        base_result = ClassificationResult(
            category=best_cat,
            level=final_level,
            confidence=confidence,
            reason=reason[:500],
            matched_words=best_data["matches"][:8],
            sentiment_score=neg_score,
            score=final_score,
            score_details=best_data["details"]
        )

        return self._combine_with_ai(base_result, text)


def classify_text(text: str, use_lemmatization: bool = True) -> Tuple[str, int, float]:
    """Быстрая классификация текста."""
    classifier = DestructiveClassifier(use_lemmatization=use_lemmatization)
    result = classifier.classify(text)

    return result.category.value, result.level.value, result.confidence