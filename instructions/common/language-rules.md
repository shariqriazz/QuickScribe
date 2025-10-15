# LANGUAGE PROCESSING RULES

**Core**: Morphosyntactic correction preserving lexical choices/register/semantics—minimal edits only.

**Stages** (cumulative, omit if identical to prior):
- `<int>` Resolve ambiguities
	- **Ambiguity notation**: {option1|option2} selects correct alternative, removes braces
	- Eliminate disfluencies (um/uh/er/ah filled pauses)
	- Self-repairs: delete original utterance before repair marker
		- Markers: "excuse me"/"I mean"/"actually"/"rather"/"no wait"
		- "or" triggers deletion ONLY with:
			- Explicit repair marker: "use apt, or actually pip" → "use pip"
			- Negation: "install it, or no, skip that" → "skip that"
			- Intensifier: "log it, or better yet, throw exception" → "throw exception"
		- Preserve genuine alternatives: "use apt or pip" → "use apt or pip"
		- "send to John, excuse me, not John, Jane" → "send to Jane"
	- Speaker spelling (L-I-N-U-X→Linux)
- `<int1>` Morphological
	- Subject-verb (*dogs is→dogs are)
	- Pronoun-antecedent (φ-features)
	- Determiner-noun agreement
	- Contractions (don't→do not)
	- Article allomorphy (a/an before vowels)
	- Tense consistency
	- Quantifiers (fewer+count/less+mass)
- `<int2>` Syntactic
	- Clause combining ("I went. There was bread."→"I went where there was bread")
	- FANBOYS never sentence-initial (integrate via comma/semicolon)
	- No terminal prepositions (restructure: "what for?"→"for what?")
	- Comma splice repair
	- Fragments OK if pragmatic (introducer+colon: "What we need:")
	- Case assignment
	- Parallel structure
	- Negative polarity elimination
- `<int3>` Polish
	- **Discourse markers**: Sentence-initial frame-setters integrate via comma when followed by propositional content ("just in case, internally it...")
	- Verbalized punctuation ("comma"→,)
	- Interrogatives→?
	- Restraint on exclamatives (prefer lexical intensity)
	- Capitalize
	- Numbers (zero-three spelled/4+ digits, 25%, $5, 3.14)
	- **Code delimitation**: Backticks for executable syntax (commands/functions/methods/variables/parameters/paths/type-identifiers/operators/configuration-keys), NOT proper nouns (technology-names/protocols/products/acronyms)

**Priority**: Agreement violations > structural > FANBOYS > disfluencies > punctuation

**Specifics**:
- Quantifiers
	- fewer people/less water
	- more/most both
	- greater for magnitude/abstract
- Self-repair markers ("I mean"/"actually"/"rather") trigger original deletion
- Preserve elliptical constructions with recoverable elements
- Voice/pleonasm unchanged (retain verbose if grammatical)
- Modifier attachment resolves scope ambiguity

**Algorithm**: Tokenize→parse for errors→classify→minimal correction→verify lexical invariance
- Constraint ranking: grammaticality>>coherence>>fidelity>>prosody
