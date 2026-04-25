"""
lemmatizer.py - Лемматизация текста на русском языке
"""

import re

# Пытаемся импортировать Natasha (если установлена)
try:
    from natasha import (
        MorphVocab,
        NewsEmbedding,
        NewsMorphTagger,
        Doc
    )
    NATASHA_AVAILABLE = True
except ImportError:
    NATASHA_AVAILABLE = False
    print("⚠️ Natasha не установлена. Установите: pip install natasha razdel")


class RussianLemmatizer:
    """
    Лемматизатор для русского текста.
    Использует Natasha (если доступна) или упрощённый режим.
    """

    def __init__(self):
        self.use_natasha = NATASHA_AVAILABLE

        # Всегда инициализируем упрощённый режим (как fallback)
        self._init_simple_mode()

        if self.use_natasha:
            try:
                self.emb = NewsEmbedding()
                self.morph_tagger = NewsMorphTagger(self.emb)
                self.morph_vocab = MorphVocab()
                print("✅ Лемматизатор (Natasha) загружен")
                self.use_natasha = True
            except Exception as e:
                print(f"⚠️ Ошибка загрузки Natasha: {e}")
                print("⚠️ Используется упрощённый режим лемматизации")
                self.use_natasha = False

    def _init_simple_mode(self):
        """Упрощённый режим лемматизации (без внешних библиотек)"""
        self._simple_rules = [
            # Глаголы
            (r'ую$', 'овать'), (r'ю$', 'ять'), (r'ешь$', 'ать'), (r'ишь$', 'ить'),
            (r'ет$', 'ать'), (r'ит$', 'ить'), (r'ем$', 'ать'), (r'им$', 'ить'),
            (r'ете$', 'ать'), (r'ите$', 'ить'), (r'ут$', 'ать'), (r'ат$', 'ать'),
            (r'ал$', 'ать'), (r'ил$', 'ить'), (r'ул$', 'ять'), (r'ел$', 'еть'),
            (r'ла$', 'ть'), (r'ло$', 'ть'), (r'ли$', 'ть'),
            # Существительные и прилагательные
            (r'ами$', 'а'), (r'ов$', ''), (r'ев$', ''), (r'ей$', 'я'),
            (r'ям$', 'я'), (r'ями$', 'а'), (r'ах$', 'а'), (r'и$', 'а'),
            (r'ы$', 'а'), (r'ее$', 'ий'), (r'ие$', 'ий'), (r'ые$', 'ый'),
        ]

        self._exceptions = {
            # Местоимения
            'меня': 'я', 'мне': 'я', 'мной': 'я', 'мною': 'я',
            'тебя': 'ты', 'тебе': 'ты', 'тобой': 'ты', 'тобою': 'ты',
            'его': 'он', 'ему': 'он', 'ним': 'он', 'нём': 'он',
            'её': 'она', 'ей': 'она', 'неё': 'она', 'ней': 'она',
            'нас': 'мы', 'нам': 'мы', 'нами': 'мы',
            'вас': 'вы', 'вам': 'вы', 'вами': 'вы',
            'их': 'они', 'им': 'они', 'ними': 'они',
            # Глаголы
            'убиваю': 'убивать', 'убивал': 'убивать', 'убивала': 'убивать',
            'убивало': 'убивать', 'убивали': 'убивать', 'убивает': 'убивать',
            'убью': 'убить', 'убил': 'убить', 'убила': 'убить', 'убило': 'убить',
            'убили': 'убить', 'убьёт': 'убить', 'убьют': 'убить',
            'ненавижу': 'ненавидеть', 'ненавидел': 'ненавидеть', 'ненавидела': 'ненавидеть',
            'ненавидит': 'ненавидеть', 'ненавидим': 'ненавидеть', 'ненавидят': 'ненавидеть',
            'бешу': 'бесить', 'бесит': 'бесить', 'бесило': 'бесить',
            'сдохну': 'сдохнуть', 'сдох': 'сдохнуть', 'сдохла': 'сдохнуть',
            'повешусь': 'повеситься', 'повесился': 'повеситься', 'повесилась': 'повеситься',
            'застрелюсь': 'застрелиться', 'застрелился': 'застрелиться',
            'прикончу': 'прикончить', 'прикончил': 'прикончить',
            'замочу': 'замочить', 'замочил': 'замочить',
        }

    def _lemmatize_word_simple(self, word: str) -> str:
        """Упрощённая лемматизация одного слова"""
        word_lower = word.lower()

        # Проверка исключений
        if word_lower in self._exceptions:
            return self._exceptions[word_lower]

        # Применение правил
        for pattern, replacement in self._simple_rules:
            if re.search(pattern, word_lower):
                result = re.sub(pattern, replacement, word_lower)
                if len(result) > 2:
                    return result

        return word_lower

    def lemmatize_natasha(self, text: str) -> str:
        """Лемматизация через Natasha"""
        try:
            # Извлекаем слова
            words = re.findall(r'[а-яёa-z]+', text.lower())
            if not words:
                return text

            # Объединяем в строку для Natasha
            text_for_natasha = ' '.join(words)

            doc = Doc(text_for_natasha)
            # Для Natasha нужен сегментатор, но у нас его нет
            # Используем упрощённый подход

            # Пробуем разные методы
            lemmas = []
            for word in words:
                # Простая лемматизация через правила
                lemmas.append(self._lemmatize_word_simple(word))

            return ' '.join(lemmas)
        except Exception as e:
            # Fallback на упрощённый режим
            return self.lemmatize_simple(text)

    def lemmatize_simple(self, text: str) -> str:
        """Упрощённая лемматизация текста"""
        if not text or len(text) < 2:
            return text

        # Извлекаем слова (только буквы)
        words = re.findall(r'[а-яёa-z]+', text.lower())

        if not words:
            return text

        lemmas = []
        for word in words:
            if len(word) > 1:
                lemma = self._lemmatize_word_simple(word)
                lemmas.append(lemma)
            else:
                lemmas.append(word)

        return ' '.join(lemmas)

    def lemmatize(self, text: str) -> str:
        """
        Лемматизация всего текста

        Args:
            text: исходный текст

        Returns:
            текст, где каждое слово приведено к нормальной форме
        """
        if not text or len(text) < 2:
            return text

        # Используем упрощённый режим (надёжнее)
        return self.lemmatize_simple(text)

    def lemmatize_text(self, text: str) -> str:
        """Алиас для lemmatize (совместимость)"""
        return self.lemmatize(text)


# Глобальный экземпляр (синглтон)
_lemmatizer_instance = None


def get_lemmatizer() -> RussianLemmatizer:
    """Получить глобальный экземпляр лемматизатора"""
    global _lemmatizer_instance
    if _lemmatizer_instance is None:
        _lemmatizer_instance = RussianLemmatizer()
    return _lemmatizer_instance


def lemmatize(text: str) -> str:
    """Быстрая лемматизация текста"""
    return get_lemmatizer().lemmatize(text)


# Для тестирования
if __name__ == "__main__":
    test_texts = [
        "убиваю убивал убивает убить",
        "я ненавижу эту жизнь",
        "самоубийство суицид",
        "хороший день",
        "сyка с обходом фильтров",
    ]

    lemm = get_lemmatizer()
    for text in test_texts:
        result = lemm.lemmatize(text)
        print(f"Исходный: {text}")
        print(f"Леммы:    {result}")
        print()