"""
nlp_ai.py - дополнительный NLP/ИИ-слой для анализа деструктивного контента.

Модуль работает опционально и не ломает основной классификатор:
- если ENABLE_NLP_AI = False, AI-слой не вызывается;
- если локальная модель/Ollama/API недоступны, система возвращается к scoring-модели;
- AI вызывается только для спорных случаев, чтобы не перегружать проект.

Поддерживаемый режим по умолчанию: Ollama local API.
Пример модели для русского текста: qwen2.5:7b-instruct, llama3.1:8b, mistral.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

try:
    import config
except Exception:  # pragma: no cover
    config = None


ALLOWED_CATEGORIES = {
    "safe",
    "aggression",
    "suicide",
    "suicide_calls",
    "hate_speech",
    "extremism",
    "misinformation",
    "manipulation",
    "drugs",
    "violence_calls",
    "bullying",
    "negative",
}


@dataclass
class AIClassificationResult:
    """Результат дополнительной AI-классификации."""

    enabled: bool = False
    used: bool = False
    available: bool = False
    category: str = "safe"
    level: int = 0
    confidence: float = 0.0
    reason: str = "AI-модуль не использовался"
    matched_words: List[str] = field(default_factory=list)
    raw_response: str = ""
    error: Optional[str] = None


class RussianNLPAIAnalyzer:
    """
    Дополнительный NLP/ИИ-анализатор.

    По умолчанию рассчитан на локальный Ollama API, поэтому в Python-проекте
    не нужны PyTorch/transformers. Это удобно для Python 3.13.
    """

    def __init__(self):
        self.enabled = bool(getattr(config, "ENABLE_NLP_AI", False)) if config else False
        self.provider = getattr(config, "NLP_AI_PROVIDER", "ollama") if config else "ollama"
        self.model = getattr(config, "NLP_AI_MODEL", "qwen2.5:7b-instruct") if config else "qwen2.5:7b-instruct"
        self.url = getattr(config, "NLP_AI_URL", "http://localhost:11434/api/generate") if config else "http://localhost:11434/api/generate"
        self.timeout = int(getattr(config, "NLP_AI_TIMEOUT", 30)) if config else 30
        self.temperature = float(getattr(config, "NLP_AI_TEMPERATURE", 0.0)) if config else 0.0
        self.max_text_length = int(getattr(config, "NLP_AI_MAX_TEXT_LENGTH", 1200)) if config else 1200
        self.always_analyze = bool(getattr(config, "NLP_AI_ALWAYS_ANALYZE", False)) if config else True

    def should_analyze(self, base_score: int, base_confidence: float, base_category: str, text: str) -> bool:
        """
        Если NLP_AI_ALWAYS_ANALYZE = False, AI вызывается для каждого текста достаточной длины.
        Если False — только для спорных случаев.
        """
        if not self.enabled:
            return False
        if not text or len(text.strip()) < 8:
            return False

        if self.always_analyze:
            return True

        suspicious_categories = {
            "aggression",
            "suicide",
            "suicide_calls",
            "hate_speech",
            "extremism",
            "drugs",
            "violence_calls",
            "bullying",
            "negative",
        }

        if 2 <= base_score <= 6:
            return True

        if base_confidence < 0.75 and base_category in suspicious_categories:
            return True

        if base_category in {"suicide", "violence_calls", "extremism"} and base_score >= 4:
            return True

        return False

    def analyze(self, text: str, base_result: Dict[str, Any]) -> AIClassificationResult:
        """Запускает AI-анализ и возвращает структурированный результат."""
        result = AIClassificationResult(enabled=self.enabled)
        if not self.enabled:
            return result

        result.used = True

        try:
            if self.provider.lower() == "ollama":
                return self._analyze_ollama(text=text, base_result=base_result)

            result.error = f"Неизвестный NLP_AI_PROVIDER: {self.provider}"
            result.reason = result.error
            return result
        except Exception as exc:  # защита основного пайплайна
            result.error = str(exc)
            result.reason = f"AI-модуль недоступен: {exc}"
            return result

    def _build_prompt(self, text: str, base_result: Dict[str, Any]) -> str:
        text = text[: self.max_text_length]

        return f"""
Ты — модуль анализа русскоязычного контента на деструктивность.
Проанализируй текст строго по смыслу и контексту, не завышай риск из-за бытовых или шуточных выражений.

Категории:
- safe: безопасный текст
- aggression: агрессия, оскорбления, угрозы человеку
- suicide: самоповреждение или суицидальные намерения автора
- suicide_calls: призывы к суициду другого человека
- hate_speech: язык вражды к группе людей
- extremism: экстремизм, терроризм, радикальные призывы
- misinformation: дезинформация
- manipulation: манипулятивный/кликбейтный текст
- drugs: наркотики, покупка/продажа/употребление
- violence_calls: призывы к массовому насилию, стрельбе, нападению
- bullying: травля, буллинг, доксинг, шантаж
- negative: сильный негатив без явной угрозы

Уровни:
0 = безопасно
1 = низкий риск
2 = средний риск
3 = высокий риск

Базовый алгоритм уже дал результат:
category={base_result.get('category')}
level={base_result.get('level')}
score={base_result.get('score')}
confidence={base_result.get('confidence')}
reason={base_result.get('reason')}

Текст для анализа:
<<<TEXT>>>
{text}
<<<END_TEXT>>>

Верни только JSON без markdown и пояснений вокруг:
{{
  "category": "safe|aggression|suicide|suicide_calls|hate_speech|extremism|misinformation|manipulation|drugs|violence_calls|bullying|negative",
  "level": 0,
  "confidence": 0.0,
  "reason": "краткое объяснение на русском",
  "matched_words": ["слово или фраза"]
}}
""".strip()

    def _analyze_ollama(self, text: str, base_result: Dict[str, Any]) -> AIClassificationResult:
        prompt = self._build_prompt(text, base_result)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
            },
        }

        response = requests.post(self.url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        raw = data.get("response", "") if isinstance(data, dict) else str(data)

        parsed = self._parse_json_response(raw)
        return self._validate_result(parsed, raw)

    def _parse_json_response(self, raw: str) -> Dict[str, Any]:
        """Достаёт JSON даже если модель добавила лишний текст."""
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            raise ValueError("AI не вернул JSON")

        return json.loads(match.group(0))

    def _validate_result(self, parsed: Dict[str, Any], raw: str) -> AIClassificationResult:
        category = str(parsed.get("category", "safe")).strip()
        if category not in ALLOWED_CATEGORIES:
            category = "safe"

        try:
            level = int(parsed.get("level", 0))
        except Exception:
            level = 0
        level = max(0, min(level, 3))

        try:
            confidence = float(parsed.get("confidence", 0.0))
        except Exception:
            confidence = 0.0
        confidence = max(0.0, min(confidence, 1.0))

        reason = str(parsed.get("reason", "AI-анализ выполнен"))[:500]
        matched_words = parsed.get("matched_words", [])
        if not isinstance(matched_words, list):
            matched_words = []
        matched_words = [str(x)[:80] for x in matched_words[:8]]

        return AIClassificationResult(
            enabled=self.enabled,
            used=True,
            available=True,
            category=category,
            level=level,
            confidence=confidence,
            reason=reason,
            matched_words=matched_words,
            raw_response=raw[:1000],
        )


_ai_instance: Optional[RussianNLPAIAnalyzer] = None


def get_ai_analyzer() -> RussianNLPAIAnalyzer:
    """Singleton, чтобы не создавать AI-анализатор на каждый текст."""
    global _ai_instance
    if _ai_instance is None:
        _ai_instance = RussianNLPAIAnalyzer()
    return _ai_instance
