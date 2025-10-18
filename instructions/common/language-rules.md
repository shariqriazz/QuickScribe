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
	- Metapragmatic directives: strip instruction, apply indicated transformation; transformed content recursively undergoes all subsequent stage processing
		- Structure: parenthetical→()/paragraph break→¶/bullet→•/numbered→1./heading→#
		- Punctuation: period→./comma→,/semicolon→;/colon→:/question→?/dash→—/ellipsis→…
		- Markup: bold→**/italic→*/code→`/link→[]()
		- Capitalization: capitalize→Title/caps→UPPER/lowercase→lower
		- Correction: scratch→delete-preceding/undo→revert-last
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
	- Coordinate interrogatives: sequential questions sharing pragmatic goal/topic join via comma; independent illocutionary acts remain separate
		- Test: if removing first question leaves second contextually dependent, join with comma
		- "What are your thoughts? Does this sound good?"→"What are your thoughts, does this sound good?"
		- Preserve separation when unrelated: "What time is it? Did you finish?" (different topics)
	- Fragment integration: temporal/locative fragments immediately following complete clause integrate if semantically dependent; preserve only if afterthought
		- "...schedule a time. Sometime next week."→"...schedule a time sometime next week"
		- Preserve afterthought: "I'll call you. Maybe tomorrow." (deliberate pause/addition)
	- FANBOYS (for/and/nor/but/because/or/yet/so) never sentence-initial; integrate via comma (if continuing thought) or semicolon (if contrasting/independent)
		- "Sentence. And another."→"Sentence, and another." OR "Sentence; and another."
		- "Sentence. Because reason."→"Sentence because reason."
	- No terminal prepositions (restructure: "what for?"→"for what?")
	- Comma splice repair
	- Sentence-initial past participles: convert to imperative by removing -ed/-en suffix; likely transcription error
		- "Provided a list"→"Provide a list"
		- "Created a function"→"Create a function"
		- Exceptions: valid passive constructions with subject ("Provided below is...")
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
	- Interrogatives: apply question mark when sentence exhibits interrogative syntax
		- WH-word sentence-initial (what/where/when/why/who/how/which) with inversion: "why was this not flagged"→"Why was this not flagged?"
		- Auxiliary-initial (is/are/was/were/do/does/did/can/could/will/would/should/have/has/had) before subject: "was this flagged"→"Was this flagged?"
		- Embedded questions without inversion retain period: "I wonder what we can do."
	- Restraint on exclamatives (prefer lexical intensity)
	- Capitalize: sentence-initial and proper nouns; convert all-caps to sentence case preserving acronyms/initialisms
	- Numbers: zero-three spelled/4+ digits, 25%, $5, 3.14
	- Code delimitation: backticks for executable/structural syntax (commands/functions/variables/paths/config-keys/operators/type-identifiers/environment-variables/glob-patterns), NOT technology-names/products/versions/protocols/acronyms/URLs (Docker/EL8/HTTP/API/github.com)
	- Quotation marks: double quotes for metalinguistic mention (referring to a word itself rather than its referent), distancing usage (irony/euphemisms/questionable-claims/approximation)

## Priority
Agreement violations > structural > interrogatives > FANBOYS > disfluencies > punctuation

## Specifics
- Quantifiers: fewer people/less water; more/most both; greater for magnitude/abstract
- Preserve elliptical constructions with recoverable elements
- Preserve all lexical choices including semantic redundancy (retain verbose/pleonastic expressions); eliminate syntactic redundancy without losing original word choices
- Modifier attachment resolves scope ambiguity

## Algorithm
Tokenize→parse for errors→classify→minimal correction→verify lexical invariance

Constraint ranking: grammaticality>>coherence>>fidelity>>prosody
