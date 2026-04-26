"""Модуль анализа деструктивного контента"""

from .classifier import DestructiveClassifier, classify_text
from .lemmatizer import RussianLemmatizer, lemmatize, get_lemmatizer
from .nlp_ai import RussianNLPAIAnalyzer, get_ai_analyzer

try:
    from .analyzer import DataAnalyzer
except Exception:
    DataAnalyzer = None

__all__ = [
    'DestructiveClassifier',
    'classify_text',
    'DataAnalyzer',
    'RussianLemmatizer',
    'lemmatize',
    'get_lemmatizer',
    'RussianNLPAIAnalyzer',
    'get_ai_analyzer',
]
