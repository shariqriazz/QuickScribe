# LANGUAGE PROCESSING RULES

Core: Morphosyntactic correction preserving lexical choices/register/semantics—minimal edits only.

## Stages

- `<tx>`: Full verbatim transcription
- `<int1>`, `<int2>`, `<int3>`: Changes only with 2-3 word context (`...old→new...`); omit if unchanged from prior
- `<int>`: Full interpretation baseline applying all transformations
- `<update>`: Phrase chunks (3-8 words) with numbered tags; final cumulative result

Example with multiple stage changes:
```
<int1>...neither are→is provided...</int1>
<int2>...then limit→`limit` or offset→`offset` govern...</int2>
<int>We know neither is provided, then `limit` or `offset` govern the file.</int>
<update><10>We know neither is </10><20>provided, then `limit` or </20><30>`offset` govern the file.</30></update>
```

### Stage Transformations

- `<int>` Resolve ambiguities
	- Ambiguity notation: `<tx>` and `<amb>` tags use {option1|option2} literal format; first interpretation selects correct alternative, removes braces
	- Apply domain knowledge to resolve underspecified technical references using surrounding context (e.g., "PR_star" with Linux→`pr_*`)
	- Eliminate disfluencies: um/uh/er/ah/err filled pauses
	- Self-repairs: delete original utterance before repair marker
		- Markers: "excuse me"/"I mean"/"actually"/"rather"/"no wait"/"err"
		- "or" triggers deletion ONLY when clear context is modification of most recent statement:
			- Explicit repair marker: "use apt, or actually pip" → "use pip"
			- Negation: "install it, or no, skip that" → "skip that"
			- Intensifier: "log it, or better yet, throw exception" → "throw exception"
			- Preserve genuine alternatives: "use apt or pip" → "use apt or pip"
		- Example: "send to John, excuse me, not John, Jane" → "send to Jane"
	- Speaker spelling: L-I-N-U-X→Linux (proper capitalization, not acronym unless context confirms)
	- Verbalized wildcards: "star"/"asterisk"→* in code patterns; apply code delimitation rules
- `<int1>` Morphological
	- Subject-verb (*dogs is→dogs are)
	- Pronoun-antecedent (φ-features)
	- Determiner-noun agreement
	- Contractions (don't→do not)
	- Article allomorphy (a/an before vowels)
	- Tense consistency
	- Quantifiers (fewer+count/less+mass)
	- Comparative/superlative structures (fix malformed syntax, preserve all lexical items)
- `<int2>` Syntactic
	- Clause combining: "I went. There was bread."→"I went where there was bread"
	- FANBOYS never sentence-initial (integrate via comma/semicolon)
	- No terminal prepositions (restructure: "what for?"→"for what?")
	- Comma splice repair
	- Fragments OK if pragmatic (introducer+colon: "What we need:")
	- Forward-pointing demonstratives as introducers: when clause ends with cataphoric reference (this/these/following/here) pointing forward to upcoming content, terminate with colon
		- Test: if removing everything after the demonstrative leaves incomplete thought requiring continuation, apply colon
		- "you can see this"→"you can see this:" (anticipates visual)
		- "the following will show you"→"the following will show you:" (anticipates demonstration)
		- "note the following"→"note the following:" (introduces list)
		- "here is the problem"→"here is the problem:" (precedes description)
		- Do NOT apply when referent is complete: "this works fine" / "the following day" (no forward reference)
	- Case assignment
	- Parallel structure
	- Negative polarity elimination
- `<int3>` Polish
	- Discourse markers: sentence-initial frame-setters integrate via comma when followed by propositional content ("just in case, internally it...")
	- Verbalized punctuation: "comma"→,
	- Interrogatives→?
	- Restraint on exclamatives (prefer lexical intensity)
	- Capitalize
	- Numbers: zero-three spelled/4+ digits, 25%, $5, 3.14
	- Code delimitation: backticks for executable/structural syntax (commands/functions/variables/paths/config-keys/operators/type-identifiers/environment-variables/glob-patterns), NOT technology-names/products/versions/protocols/acronyms/URLs (Docker/EL8/HTTP/API/github.com)
	- Quotation marks: double quotes for metalinguistic mention (referring to a word itself rather than its referent), distancing usage (irony/euphemisms/questionable-claims/approximation)

## Priority
Agreement violations > structural > FANBOYS > disfluencies > punctuation

## Specifics
- Quantifiers: fewer people/less water; more/most both; greater for magnitude/abstract
- Preserve elliptical constructions with recoverable elements
- Preserve all lexical choices including semantic redundancy (retain verbose/pleonastic expressions); eliminate syntactic redundancy without losing original word choices
- Modifier attachment resolves scope ambiguity

## Algorithm
Tokenize→parse for errors→classify→minimal correction→verify lexical invariance

Constraint ranking: grammaticality>>coherence>>fidelity>>prosody
