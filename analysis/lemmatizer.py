"""
lemmatizer.py - Production-ready NLP preprocessing for Russian text
(optimized for toxic / destructive content detection)
"""

import re
import unicodedata

# =========================
# NATASHA IMPORT
# =========================

try:
    from natasha import (
        Segmenter,
        MorphVocab,
        NewsEmbedding,
        NewsMorphTagger,
        Doc
    )
    NATASHA_AVAILABLE = True
except ImportError:
    NATASHA_AVAILABLE = False
    print("⚠️ Natasha не установлена. pip install natasha razdel")

# =========================
# OPTIONAL TOKENIZER
# =========================

try:
    from razdel import tokenize
    RAZDEL_AVAILABLE = True
except ImportError:
    RAZDEL_AVAILABLE = False


# =========================
# TEXT NORMALIZATION
# =========================

LEET_MAP = {
    "0": "о",
    "1": "и",
    "3": "з",
    "4": "ч",
    "5": "с",
    "6": "б",
    "7": "т",
    "8": "в",
    "@": "а",
    "$": "с"
}

LAT_TO_CYR = {
    "a": "а",
    "e": "е",
    "o": "о",
    "p": "р",
    "c": "с",
    "x": "х",
    "y": "у",
    "k": "к",
    "m": "м",
    "t": "т"
}


class TextNormalizer:
    """
    Normalization for adversarial / toxic text:
    - leetspeak
    - latin-to-cyrillic substitution
    - unicode cleanup
    """

    def normalize(self, text: str) -> str:
        if not text:
            return ""

        text = text.lower()

        # Unicode normalize
        text = unicodedata.normalize("NFKC", text)

        # Replace leetspeak
        for k, v in LEET_MAP.items():
            text = text.replace(k, v)

        # Replace latin chars that mimic cyrillic
        text = "".join(LAT_TO_CYR.get(ch, ch) for ch in text)

        # Remove excessive noise but keep punctuation minimal
        text = re.sub(r"\s+", " ", text)

        return text.strip()


# =========================
# TOKENIZER
# =========================

class Tokenizer:
    def tokenize(self, text: str):
        if RAZDEL_AVAILABLE:
            return [t.text for t in tokenize(text)]
        else:
            return re.findall(r"[а-яёa-z0-9]+", text.lower())


# =========================
# LEMMATIZER
# =========================

class RussianLemmatizer:

    def __init__(self):
        self.use_natasha = NATASHA_AVAILABLE

        self.normalizer = TextNormalizer()
        self.tokenizer = Tokenizer()

        if self.use_natasha:
            try:
                self.segmenter = Segmenter()
                self.emb = NewsEmbedding()
                self.morph_tagger = NewsMorphTagger(self.emb)
                self.morph_vocab = MorphVocab()
                print("✅ Natasha лемматизатор активирован")
            except Exception as e:
                print(f"⚠️ Natasha error: {e}")
                self.use_natasha = False

    # =========================
    # SAFE FALLBACK (NO RULES)
    # =========================

    def _lemmatize_fallback(self, tokens):
        # ВАЖНО: НЕ искажаем слова
        return tokens

    # =========================
    # NATASHA LEMMATIZATION
    # =========================

    def _lemmatize_natasha(self, text: str):
        doc = Doc(text)
        doc.segment(self.segmenter)
        doc.tag_morph(self.morph_tagger)

        lemmas = []

        for token in doc.tokens:
            token.lemmatize(self.morph_vocab)

            if token.lemma:
                lemmas.append(token.lemma)
            else:
                lemmas.append(token.text.lower())

        return lemmas

    # =========================
    # MAIN PIPELINE
    # =========================

    def preprocess(self, text: str):
        """
        Full preprocessing pipeline:
        normalize → tokenize → lemmatize
        """

        if not text or len(text) < 2:
            return []

        # 1. normalize adversarial text
        text = self.normalizer.normalize(text)

        # 2. tokenize
        tokens = self.tokenizer.tokenize(text)

        # 3. lemmatize
        if self.use_natasha:
            try:
                return self._lemmatize_natasha(" ".join(tokens))
            except Exception:
                return self._lemmatize_fallback(tokens)

        return self._lemmatize_fallback(tokens)

    def lemmatize(self, text: str) -> str:
        return " ".join(self.preprocess(text))


# =========================
# SINGLETON
# =========================

_instance = None


def get_lemmatizer():
    global _instance
    if _instance is None:
        _instance = RussianLemmatizer()
    return _instance


def lemmatize(text: str) -> str:
    return get_lemmatizer().lemmatize(text)


# =========================
# TEST
# =========================

if __name__ == "__main__":

    test_texts = [
        "убиваю убивал убивает убить",
        "я ненавижу эту жизнь",
        "сyка sука сука",
        "bлядь бляdь",
        "повешусь застрелюсь",
        "он убил его а потом сдох"
    ]

    lemm = get_lemmatizer()

    for t in test_texts:
        print("INPUT :", t)
        print("OUTPUT:", lemm.lemmatize(t))
        print("-" * 40)