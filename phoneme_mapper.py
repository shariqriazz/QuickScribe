"""Phoneme mapping utilities for converting IPA symbols to alphanumeric representations."""

# Comprehensive IPA to alphanumeric mapping for Wav2Vec2 phoneme processing
IPA_TO_ALPHA_MAP = {
    # Vowels - Front
    'i': 'IY',      # /i/
    'ɪ': 'IH',      # /ɪ/
    'e': 'EY',      # /e/
    'ɛ': 'EH',      # /ɛ/
    'æ': 'AE',      # /æ/

    # Vowels - Central
    'ə': 'AH',      # /ə/ schwa
    'ɜ': 'ER',      # /ɜ/ open-mid central unrounded
    'ɚ': 'ERR',     # /ɚ/ r-colored schwa
    'ʌ': 'UH',      # /ʌ/ open-mid back unrounded
    'ɐ': 'AA',      # /ɐ/ near-open central
    'a': 'AX',      # /a/ open front
    'ᵻ': 'IX',      # /ᵻ/ near-close central

    # Vowels - Back
    'ɑ': 'AO',      # /ɑ/ open back unrounded
    'ɑː': 'AAR',    # /ɑː/ long open back
    'ɔ': 'OR',      # /ɔ/ open-mid back rounded
    'o': 'OW',      # /o/ close-mid back rounded
    'ʊ': 'UU',      # /ʊ/ near-close back rounded
    'u': 'UW',      # /u/ close back rounded

    # Diphthongs
    'aɪ': 'AY',     # /aɪ/
    'aʊ': 'AW',     # /aʊ/
    'ɔɪ': 'OY',     # /ɔɪ/
    'eɪ': 'EY',     # /eɪ/
    'oʊ': 'OW',     # /oʊ/
    'ɪə': 'IHR',    # /ɪə/
    'ɛə': 'EHR',    # /ɛə/
    'ʊə': 'UHR',    # /ʊə/

    # Consonants - Stops
    'p': 'P',       # pat
    'b': 'B',       # bat
    't': 'T',       # tap
    'd': 'D',       # day
    'k': 'K',       # key
    'g': 'G',       # gay
    'ʔ': 'Q',       # glottal stop

    # Consonants - Fricatives
    'f': 'F',       # fat
    'v': 'V',       # vat
    'θ': 'TH',      # think
    'ð': 'DH',      # this
    's': 'S',       # sat
    'z': 'Z',       # zap
    'ʃ': 'SH',      # ship
    'ʒ': 'ZH',      # measure
    'h': 'H',       # hat
    'x': 'KH',      # loch

    # Consonants - Affricates
    'tʃ': 'CH',     # chat
    'dʒ': 'JH',     # joy

    # Consonants - Nasals
    'm': 'M',       # mat
    'n': 'N',       # nat
    'ŋ': 'NG',      # hang
    'ɲ': 'NY',      # canyon

    # Consonants - Liquids
    'l': 'L',       # lap
    'r': 'R',       # rap
    'ɹ': 'RR',      # American r
    'ɾ': 'T',       # flap (tap)

    # Consonants - Glides
    'j': 'Y',       # /j/
    'w': 'W',       # /w/
    'ɥ': 'WY',      # /ɥ/

    # Additional vowels
    'ɨ': 'IU',      # /ɨ/ close central unrounded
    'ɵ': 'EU',      # /ɵ/ close-mid central rounded
    'ɤ': 'UU',      # /ɤ/ close-mid back unrounded

    # Additional consonants
    'ʔ': 'Q',       # /ʔ/ glottal stop
    'ɭ': 'LL',      # /ɭ/ retroflex lateral
    'ɳ': 'NN',      # /ɳ/ retroflex nasal
    'ɽ': 'RD',      # /ɽ/ retroflex flap

    # Symbols and markers
    'ː': 'LONG',    # /ː/ length marker
    'ˈ': 'STRESS1', # /ˈ/ primary stress
    'ˌ': 'STRESS2', # /ˌ/ secondary stress
    '.': 'SYLDIV',  # /./ syllable boundary
    ' ': 'SPACE',   # word boundary
    '-': 'MORPH',   # morpheme boundary

    # Special tokens (common in Wav2Vec2)
    '<pad>': 'PAD',
    '<s>': 'BOS',
    '</s>': 'EOS',
    '<unk>': 'UNK',
    '|': 'WORDSEP',
}

# Reverse mapping for converting back to IPA
ALPHA_TO_IPA_MAP = {v: k for k, v in IPA_TO_ALPHA_MAP.items()}

def ipa_to_alpha(phoneme_string: str) -> str:
    """
    Convert IPA phoneme string to alphanumeric representation.

    Args:
        phoneme_string: Space-separated IPA phonemes

    Returns:
        Space-separated alphanumeric phoneme codes
    """
    if not phoneme_string:
        return ""

    # Split into individual phonemes
    phonemes = phoneme_string.split()
    converted = []

    for phoneme in phonemes:
        # Try exact match first
        if phoneme in IPA_TO_ALPHA_MAP:
            converted.append(IPA_TO_ALPHA_MAP[phoneme])
        else:
            # Try to handle combined symbols by checking longest matches first
            found = False
            for ipa_symbol in sorted(IPA_TO_ALPHA_MAP.keys(), key=len, reverse=True):
                if phoneme.startswith(ipa_symbol):
                    converted.append(IPA_TO_ALPHA_MAP[ipa_symbol])
                    # Handle remainder if any
                    remainder = phoneme[len(ipa_symbol):]
                    if remainder:
                        converted.append(remainder)  # Keep unknown parts as-is
                    found = True
                    break

            if not found:
                # Keep unknown phonemes as-is
                converted.append(phoneme)

    return ' '.join(converted)

def alpha_to_ipa(alpha_string: str) -> str:
    """
    Convert alphanumeric representation back to IPA phonemes.

    Args:
        alpha_string: Space-separated alphanumeric phoneme codes

    Returns:
        Space-separated IPA phonemes
    """
    if not alpha_string:
        return ""

    codes = alpha_string.split()
    converted = []

    for code in codes:
        if code in ALPHA_TO_IPA_MAP:
            converted.append(ALPHA_TO_IPA_MAP[code])
        else:
            # Keep unknown codes as-is
            converted.append(code)

    return ' '.join(converted)

def process_wav2vec2_output(phoneme_text: str) -> str:
    """
    Process Wav2Vec2 phoneme output to alphanumeric format.

    Args:
        phoneme_text: Raw phoneme output from Wav2Vec2

    Returns:
        Alphanumeric phoneme representation
    """
    # Clean up the input
    cleaned = phoneme_text.strip()

    # Convert to alphanumeric
    alpha_phonemes = ipa_to_alpha(cleaned)

    return alpha_phonemes

# Example usage and test
if __name__ == "__main__":
    # Test with your example
    test_input = "w w ʌ n n s ɐ p ɑː n ɐ t aɪ m ð ɛ ɹ ɪ z ɐ s k w ɪ əl ð æ t l aɪ k k t t t ə dʒ ʌ m m p p"

    print("Original IPA:")
    print(test_input)
    print()

    converted = ipa_to_alpha(test_input)
    print("Converted to alphanumeric:")
    print(converted)
    print()

    # Test reverse conversion
    back_to_ipa = alpha_to_ipa(converted)
    print("Converted back to IPA:")
    print(back_to_ipa)
    print()

    print("Match original:", test_input == back_to_ipa)