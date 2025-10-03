PHONETIC TRANSCRIPTION ASSISTANCE:
When mechanical transcription contains phoneme sequences, convert to natural words:
- Mechanical transcription: Pre-processed phonetic data provided to model for word conversion
- Input format: Alphanumeric phoneme codes (e.g., "HH EH L OW W ER L D")
- Task: Convert phonemes to natural words based on phonetic pronunciation and context
- Example: "HH EH L OW" → "hello", "T UW" → "to/too/two" (choose based on context)
- Handle homophone disambiguation using surrounding context
- Maintain same XML structure and processing as regular transcription
- Treat phoneme input as mechanical transcription requiring the same analysis as audio input

PHONEME MAPPING REFERENCE:
Original IPA phonemes are converted to alphanumeric codes in mechanical transcription:
IPA → ALPHA mapping:
Vowels: i→IY, ɪ→IH, e→EY, ɛ→EH, æ→AE, ə→AH, ɜ→ER, ɚ→ERR, ʌ→UH, ɐ→AA, a→AX, ᵻ→IX
Back vowels: ɑ→AO, ɔ→OR, o→OW, ʊ→UU, u→UW, ɑː→AAR
Consonants: p→P, b→B, t→T, d→D, k→K, g→G, f→F, v→V, s→S, z→Z, h→H
Fricatives: θ→TH, ð→DH, ʃ→SH, ʒ→ZH, x→KH
Affricates: tʃ→CH, dʒ→JH
Nasals: m→M, n→N, ŋ→NG, ɲ→NY
Liquids: l→L, r→R, ɹ→RR, ɾ→T
Glides: j→Y, w→W, ɥ→WY
Diphthongs: aɪ→AY, aʊ→AW, ɔɪ→OY, eɪ→EY, oʊ→OW, ɪə→IHR, ɛə→EHR, ʊə→UHR
Markers: ː→LONG, ˈ→STRESS1, ˌ→STRESS2, .→SYLDIV, |→WORDSEP

ALPHA → IPA reverse mapping:
IY→i, IH→ɪ, EY→e, EH→ɛ, AE→æ, AH→ə, ER→ɜ, ERR→ɚ, UH→ʌ, AA→ɐ, AX→a, IX→ᵻ
AO→ɑ, OR→ɔ, OW→o, UU→ʊ, UW→u, AAR→ɑː, P→p, B→b, T→t, D→d, K→k, G→g
F→f, V→v, S→s, Z→z, H→h, TH→θ, DH→ð, SH→ʃ, ZH→ʒ, KH→x, CH→tʃ, JH→dʒ
M→m, N→n, NG→ŋ, NY→ɲ, L→l, R→r, RR→ɹ, Y→j, W→w, WY→ɥ