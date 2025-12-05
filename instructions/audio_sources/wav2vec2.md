IPA PHONEME INPUT:
Convert IPA phoneme sequences to natural words using context.
Maintain XML structure identical to audio transcription.

MULTI-SPEED ENSEMBLE (4 speeds):

80% - Completeness (30% weight):
- Preserves syllable onsets/endings other speeds drop
- Use for: Missing word beginnings, final syllables, basic vocabulary

85% - Moderate Complexity (15% weight):
- Reliable on 3-4 syllable words
- Degrades on 5+ syllables (drops consonants)

90% - Primary Baseline (45% weight):
- Best complex polysyllabic preservation
- Optimal cluster handling (/stɹ/, /kw/, /ntɹ/)
- Fewest errors across vocabulary types

95% - Unique Phonemes (10% weight):
- Complete vowel sequences (/juː/, diphthongs)
- High error rate (spurious insertions, missing onsets)

ENSEMBLE RULES:

1. 3+ speeds agree → Use consensus
2. 2 speeds agree → Use majority, reject outliers
3. Speed-specific override on disagreement:
   - 80%: Onsets/endings missing in others
   - 90%: Complex words (5+ syllables)
   - 95%: Unique vowel sequences absent elsewhere
4. Reject phonemes appearing in only 1 speed
5. Spacing: Single=word, double=phrase, triple=sentence boundary
6. Use 90% spacing when speeds conflict

WORKFLOW:
1. Check consensus across speeds
2. Apply speed-specific overrides for conflicts
3. Start from 90% baseline
4. Validate with 80% completeness
5. Cross-check 85% on moderate words
6. Extract unique phonemes from 95%
7. Reject single-speed outliers
8. Generate {option1|option2} in TX for valid alternatives
9. Resolve in INT via context