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
	- Clause boundary detection via multiple signals:
		- Semantic coherence: verb argument expectations violated by following word → separate clauses
		- Finite verb sequences: multiple tensed verbs without coordination signal clause boundaries
		- Independent predications: complete subject-predicate structures in sequence require separation
	- Clause separation by illocutionary relationship:
		- Different types (declarative/interrogative/imperative): semicolon
		- Same type, independent clauses: semicolon unless semantically coordinated
		- Related interrogatives sharing pragmatic goal: comma (see coordinate interrogatives)
	- Exclude clause separation when subordinating conjunction present (if/whether/that/because introducing embedded clause)
	- No terminal prepositions (restructure: "what for?"→"for what?")
	- Comma splice repair
	- Sentence-initial past participles: convert to imperative by removing -ed/-en suffix; likely transcription error
		- "Provided a list"→"Provide a list"
		- "Created a function"→"Create a function"
		- Exceptions: valid passive constructions with subject ("Provided below is...")
	- Fragments OK if pragmatic (introducer+colon: "What we need:")
	- Forward-pointing demonstratives: terminate with colon when sentence ends with demonstrative creating incomplete reference requiring continuation
		- Common ending patterns include: "of the following" / "like this" / "such as these" / "as follows" / "shown here" / "note these" / "see this" / "observe this" / "include these" / "consider these" / "the following" / "as shown here"
		- Test: removing demonstrative-ending leaves incomplete thought requiring continuation
		- Apply: append colon when test confirms forward reference
		- Typically preserve when referent is complete: "this works" / "following day" / "like this one"
	- Case assignment
	- Parallel structure
	- Negative polarity elimination
- `<int3>` Polish
	- Discourse markers: sentence-initial frame-setters integrate via comma when followed by propositional content ("just in case, internally it...")
	- Verbalized punctuation: "comma"→,
	- Interrogatives: apply question mark to independent interrogative clauses identified via clause boundary detection; mark each independent interrogative clause terminus regardless of position
		- Canonical WH-interrogatives (initial WH-word with or without subject-auxiliary inversion)
		- Subject WH-interrogatives (WH-determiner modifying subject, no inversion)
		- Auxiliary-initial interrogatives (inverted auxiliary before subject)
		- Echo interrogatives (WH-word in non-initial position, typically final)
		- Tag interrogatives (auxiliary + pronoun appended to declarative)
		- Coordinate interrogatives (following semicolon/comma)
		- Exclude embedded interrogatives functioning as complement clauses
	- Restraint on exclamatives (prefer lexical intensity)
	- Capitalize: sentence-initial and proper nouns; convert all-caps to sentence case preserving acronyms/initialisms
	- Numbers: zero-three spelled/4+ digits, 25%, $5, 3.14
	- Code delimitation: backticks ONLY for executable/structural syntax requiring literal interpretation (commands/functions/variables/paths/config-keys/operators/type-identifiers/environment-variables/glob-patterns/file-extensions-in-technical-context); NEVER for technology-names/products/platforms/versions/protocols/acronyms/URLs/file-format-names
		- Examples requiring backticks: `docker run`, `getUserId()`, `API_KEY`, `/etc/config`, `*.txt`, `ArrayBuffer`, `.vsix` (file extension pattern)
		- Examples not requiring backticks: Docker, VS Code, VSIX, HTTP/2, API, github.com, JSON format, VSIX package
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
