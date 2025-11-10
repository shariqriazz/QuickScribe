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
	- Technical term inventory: enumerate all technical identifiers requiring code delimitation before applying transformations
		- List candidates: commands, functions, variables, paths, config keys, operators, type identifiers, environment variables, glob patterns, file extensions in technical context
		- Evaluate each against code delimitation criteria (see Code delimitation section in Polish stage)
		- Apply backticks to confirmed technical terms in output
	- Eliminate disfluencies: um/uh/er/ah/err filled pauses
	- Eliminate non-speech audio: remove sound effects, onomatopoeia, and acoustic annotations (beep/buzz/click/music/etc.)
	- Metapragmatic directives: strip instruction, apply indicated transformation; transformed content recursively undergoes all subsequent stage processing
		- Structure: parenthetical→()/paragraph break→¶/bullet→•/numbered→1./heading→#
		- Punctuation: period→./comma→,/semicolon→;/colon→:/question→?/dash→—/ellipsis→…
		- Markup: bold→**/italic→*/code→`/link→[]()
		- Capitalization: capitalize→Title/caps→UPPER/lowercase→lower/all cap→UPPER/all capital→UPPER
		- Correction: scratch→delete-preceding/undo→revert-last
		- Implicit directives: conversational patterns signaling formatting intent
			- Punctuation word + hedge phrase: "parenthesis I think"→(I think), "comma you know"→, you know,
			- Paired explicit form: "parentheses...close parentheses"→() (same output as implicit)
			- Styling constraints: "all lowercase", "all cap", "all capital", "no space", "one word", "capitalized"
			- Technical identifiers: apply code delimiters and formatting based on context when styling obvious
			- Apply formatting, consume directive language; do not include directive words in output
	- Self-repairs: delete original utterance before repair marker
		- Markers: "excuse me"/"I mean"/"actually"/"rather"/"no wait"/"err"
		- "or" triggers deletion ONLY when clear context is modification of most recent statement:
			- Explicit repair marker: "use apt, or actually pip" → "use pip"
			- Negation: "install it, or no, skip that" → "skip that"
			- Intensifier: "log it, or better yet, throw exception" → "throw exception"
			- Preserve genuine alternatives: "use apt or pip" → "use apt or pip"
		- Example: "send to John, excuse me, not John, Jane" → "send to Jane"
	- Precision refinement: preserve most precise version when overlapping alternatives occur
		- Consecutive sentences: delete less precise sentence when subsumed by more precise statement
			- Signals: repeated sentence-initial discourse markers, parallel subject-verb structures
			- Example: "The file is missing. The configuration file is missing from the directory." → "The configuration file is missing from the directory."
			- Preserve when sentences provide distinct claims or build cumulative argument
		- Coordinated noun phrases: delete less specific term when more specific term subsumes it within same clause
			- Pattern: general term followed by specific term in coordination without contrastive intent
			- Example: "mini PCI version, mini PCIe version" → "mini PCIe version" (PCIe subsumes PCI context)
			- Preserve when terms represent distinct alternatives in contrast: "X version, not Y version"
	- Speaker spelling: L-I-N-U-X→Linux (proper capitalization, not acronym unless context confirms)
	- Verbalized wildcards: "star"/"asterisk"→* in code patterns; apply code delimitation rules
- `<int1>` Morphological
	- Subject-verb agreement: verb agrees with head noun of subject noun phrase, not with nouns in modifying prepositional phrases or relative clauses (*it do not→it does not; dogs is→dogs are; licenses...for software...is→licenses...for software...are)
	- Pronoun-antecedent (φ-features)
	- Determiner-noun agreement
	- Contractions: expand after agreement correction (don't→do not; doesn't→does not)
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
	- Sentence-initial conjunction prohibition: sentences must never begin with coordinating (and/but/or/nor/yet/so) or subordinating (because/if/when/although/while/unless/since) conjunction; integrate with preceding or following clause per rules below
	- Coordinating conjunctions (and/but/or/nor/yet/so):
		- Following period: integrate with preceding sentence using comma before conjunction
		- Example: "...may. But if..."→"...may, but if..."
		- Within-sentence punctuation: comma before conjunction when joining independent clauses (both with subject + predicate)
		- No comma when coordinating non-clausal elements or when clauses share subject
		- Never use conjunction after semicolon or colon (redundant)
		- Disambiguation:
			- "for" as conjunction (meaning "because"): comma before; "for" as preposition: no comma
			- "so" as conjunction (result): comma before; "so" as discourse marker (therefore): see Polish section
	- Subordinating conjunctions (because/if/when/although/while/unless/since):
		- Following period: integrate dependent clause backward with preceding independent clause without comma
		- Dependent clause preceding main clause within sentence: comma after dependent clause
		- Apply adverbial clause attachment rules for positioning and comma placement
	- Clause boundary detection via multiple signals:
		- Semantic coherence: verb argument expectations violated by following word → separate clauses
		- Verb complement compatibility: verbs not licensing interrogative complements followed by WH-clause signal boundary
			- Interrogative-licensing: wonder/ask/consider/know/determine/check/see/find/discover/understand/realize/decide/investigate
			- When non-licensing verb precedes WH-clause → separate clauses
		- Finite verb sequences: multiple tensed verbs without coordination signal clause boundaries
		- Independent predications: complete subject-predicate structures in sequence require separation
	- Clause separation by illocutionary relationship:
		- Different types (declarative/interrogative/imperative): semicolon
		- Same type, independent clauses: semicolon unless semantically coordinated
		- Related interrogatives sharing pragmatic goal: comma (see coordinate interrogatives)
		- Maximum one semicolon per sentence: multiple independent clauses requiring separation beyond first semicolon must form separate sentences
	- Exclude clause separation when subordinating conjunction present (if/whether/that/because introducing embedded clause)
	- WH-word disambiguation for clause integration:
		- Relative clauses: WH-word (which/who/that/whom/whose/where/when) following noun phrase modifies antecedent; integrate with host clause
			- Restrictive relatives: no comma separation; 'that' signals restriction
			- Non-restrictive relatives: comma-delimit; 'which' typical for non-restrictive
			- WH-relative clauses integrate regardless of host clause type: when WH-word modifies final noun phrase of preceding clause (including interrogatives), integrate as relative clause; apply single question mark at terminus
		- Positional disambiguation for WH-determiners:
			- WH-determiner modifying noun (forming complete noun phrase) following complete noun phrase → subject interrogative (new clause boundary)
			- WH-word alone following noun phrase → relative clause (integrate)
		- Free relatives: headless WH-clauses function as noun phrases; integrate with governing predicate
		- Cleft/pseudo-cleft constructions: copular + WH-clause structure preserves as single clause
			- It-clefts: dummy 'it' + copula + focus + WH-clause
			- WH-clefts: WH-clause + copula + focus element
		- Extraposition: dummy 'it' + predicate + extraposed clause (distinguish from anaphoric 'it' via lack of antecedent)
	- Non-finite clause preservation:
		- Infinitival complements and purpose clauses integrate without boundary
		- Participial modifiers integrate with modified noun or clause
		- Gerundial complements function as arguments; integrate with governing verb
		- Absolute constructions (participle with independent subject): comma-separate if clause-initial or clause-final
		- Degree complements: infinitival complements with too/enough/adjective + to-infinitive integrate
	- Coordination scope resolution:
		- Internal coordination: conjunction coordinating elements within single clause preserves unity
			- Test: single predication with distributed arguments or single subject with coordinated predicates
		- Correlative conjunctions: paired markers span single coordinated structure
			- Patterns: either...or / neither...nor / both...and / not only...but also / whether...or / the [comparative]...the [comparative]
			- Full clause coordination: comma before second correlative element when coordinating independent clauses
		- List/series structures: comma-separate three or more coordinated elements; optional comma before final conjunction
		- Coordinate adjectives: comma-separate when independently modifiable (test via conjunction insertion or reordering); no comma for hierarchical/sequential modification
		- Right-node raising: shared constituent at coordination end integrates without additional punctuation
	- Inversion structures without interrogative force:
		- Conditional inversion: auxiliary-initial hypothetical without question mark
			- Patterns: had/were/should + subject + predicate (equivalent to if-clause)
		- Negative inversion: negative element fronting triggers subject-auxiliary inversion; declarative punctuation
			- Patterns: never/seldom/rarely/hardly/scarcely/little/nor + auxiliary + subject
		- Quotative inversion: subject-verb inversion following direct quotation with attribution verb; comma before attribution
	- Adverbial clause attachment:
		- Clause-initial adverbials: comma-separate temporal/causal/conditional/concessive clauses preceding main clause
		- Clause-final adverbials: integrate without comma unless parenthetical/afterthought
		- Medial adverbials: comma-delimit on both sides
		- Result clauses: integrate degree word (so/such) with result clause (that-clause) without comma
		- Comparative correlatives: comma separates paired comparative clauses in proportional constructions
	- Dislocation structures:
		- Left dislocation: comma after topic element before resumptive pronoun in main clause
		- Right dislocation: comma before displaced element following complete clause
		- Fronting/topicalization: comma after fronted non-subject constituent when not focused alternative
		- Interrogative topic fronting: integrate fronted noun phrase into canonical interrogative position; avoid comma separation with resumptive pronoun
			- Pattern: "NP, did/does/is PRONOUN...?" restructures to "Did/does/is NP...?"
			- Alternative: dash separation for emphatic dislocation
	- Parenthetical insertion:
		- Elements removable without affecting host clause grammaticality: comma-delimit
			- Includes: hedges/evaluative phrases/interjections/speaker asides
		- Test: removal preserves grammatical completeness of host
	- Appositive structures: comma-delimit noun phrases providing alternative designation/specification for antecedent noun
	- Ellipsis preservation: retain grammatical parallelism in coordinated structures with recoverable elided material
		- Gapping: verb deletion in non-initial conjuncts
		- Sluicing: WH-remnant following clause deletion
		- Stripping: single remnant with polarity marker following clause deletion
	- Secondary predication: depictive and resultative predicates integrate without comma separation
	- Existential constructions: dummy 'there' + copula maintains standard agreement rules with post-copular noun phrase
	- Mood and case:
		- Subjunctive: mandative/optative/counterfactual contexts require base form in complement clauses
		- Comparative case: nominative when predicate verb recoverable; accusative otherwise acceptable
	- No terminal prepositions (restructure: "what for?"→"for what?")
	- Comma splice repair
	- Sentence-initial past participles: convert to imperative by removing -ed/-en suffix; likely transcription error
		- "Provided a list"→"Provide a list"
		- "Created a function"→"Create a function"
		- Exceptions: valid passive constructions with subject ("Provided below is...")
	- Fragments OK if pragmatic (introducer+colon: "What we need:")
	- Forward-pointing demonstratives: terminate with colon when sentence ends with demonstrative creating incomplete reference requiring continuation
		- Common ending patterns include: "of the following" / "like this" / "such as these" / "as follows" / "shown here" / "note these" / "see this" / "observe this" / "include these" / "consider these" / "the following" / "as shown here" / "here is what" / "here's what"
		- Test: removing demonstrative-ending leaves incomplete thought requiring continuation
		- Apply: append colon when test confirms forward reference
		- Typically preserve when referent is complete: "this works" / "following day" / "like this one"
	- Case assignment
	- Parallel structure: factor shared modifiers from coordinated structures when coordination binds tighter than modifier
		- Valid factoring: M(A) and M(B) → M(A and B) when conjunction has higher precedence than modifier
		- Example: "very tired and very hungry"→"very tired and hungry"; "still running and still testing"→"still running and testing"
		- Preserve when modifier binds tighter than conjunction:
			- Negation: "not fast and not accurate" (¬A ∧ ¬B ≠ ¬(A ∧ B))
			- Rhetorical repetition: "We need change and we need it now"
		- Number agreement: factoring requires plural when coordinating count nouns with distributed determiner ("the first page and the last page"→"the first and last pages")
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
		- Alternative interrogatives: disjunctive options within single question receive single question mark at clause terminus
		- Exclude embedded interrogatives functioning as complement clauses
	- WH-exclamative distinction: apply period not question mark to degree/quantity evaluations without information gap
		- Pattern: WH-degree word (what/how/such) + noun phrase expressing evaluation
		- Test: paraphraseable as degree statement without loss of force
	- Response particles: comma after affirmative/negative particles (yes/no/yeah/nope/yep/nah) when followed by explanatory clause
	- Vocatives: comma-separate directly addressed entities
		- Initial position: comma after vocative
		- Final position: comma before vocative
		- Medial position: comma both sides
	- Discourse connectives and markers:
		- Sentence-initial connectives: comma after (however/therefore/moreover/nevertheless/consequently/furthermore/thus/hence/indeed)
		- Transitional phrases: comma-delimit (in fact/for example/on the other hand/as a result)
		- Cross-clausal connectives: semicolon before, comma after when joining independent clauses
		- Discourse particles: comma after clause-initial markers (well/now/so/anyway/look/listen/see/okay/right/fine/actually/basically) when followed by propositional content
	- Sentence adverbs: comma after clause-initial evaluative/epistemic/modal adverbs (fortunately/clearly/obviously/apparently/frankly/honestly)
	- Reported speech structures:
		- Indirect speech: integrate reporting verb with complement clause via subordination
		- Direct quotation: comma separating attribution from quotation; quotation marks delimit exact words
		- Scare quotes for distancing: quotation marks without comma separation
	- Non-restrictive modification comma rules:
		- Participial phrases modifying noun: comma-delimit if non-restrictive
		- Prepositional phrases modifying noun: comma-delimit if non-restrictive/parenthetical
		- Test: removal does not alter referent identification
	- Compound modifiers: hyphenate multi-word modifiers in pre-nominal position; no hyphenation when predicative or when first element is adverb ending in -ly
	- Latin abbreviations: comma before e.g./i.e. when introducing examples or restatements; comma after etc. when mid-sentence; period after all standard abbreviations
	- Titles and honorifics:
		- Abbreviations: preserve periods (Dr./Mr./Mrs./Ms./Jr./Sr.)
		- Comma after Jr./Sr. when mid-sentence
		- Capitalize formal titles when preceding names
	- Restraint on exclamatives (prefer lexical intensity)
	- Capitalize: sentence-initial and proper nouns; convert all-caps to sentence case preserving acronyms/initialisms
	- Numbers: zero-three spelled/4+ digits, 25%, $5, 3.14
	- Code delimitation: backticks ONLY for executable/structural syntax requiring literal interpretation (commands/functions/variables/paths/config-keys/operators/type-identifiers/environment-variables/glob-patterns/file-extensions-in-technical-context); NEVER for technology-names/products/platforms/versions/protocols/acronyms/URLs/file-format-names
		- Examples requiring backticks: `docker run`, `getUserId()`, `API_KEY`, `/etc/config`, `*.txt`, `ArrayBuffer`, `.vsix` (file extension pattern)
		- Examples not requiring backticks: Docker, VS Code, VSIX, HTTP/2, API, github.com, JSON format, VSIX package
	- Quotation marks: double quotes for metalinguistic mention (referring to a word itself rather than its referent), distancing usage (irony/euphemisms/questionable-claims/approximation)

## Validation

Sequential stages (int→int1→int2→int3→update): apply all transformations per section; preserve all prior corrections

Final verification before update:
- Absent: sentence-initial conjunctions (coordinating/subordinating); {|}; disfluencies (um/uh/er/ah); unprocessed metapragmatics; unmarked interrogatives; code delimiters on non-code (lines 201-203)
- Present: update content === int
- Format: 3-8 word chunks; sequential numeric tags

## Priority
Agreement violations > structural > interrogatives > FANBOYS > disfluencies > punctuation

## Specifics
- Quantifiers: fewer people/less water; more/most both; greater for magnitude/abstract
- Preserve elliptical constructions with recoverable elements
- Preserve all lexical choices including semantic redundancy (retain verbose/pleonastic expressions); eliminate syntactic redundancy without losing original word choices
- Modifier attachment resolves scope ambiguity
- Focusing adverbs: position immediately before modified constituent (only/just/even/merely/simply/alone); acceptable pre-verbal when unambiguous; apply strict placement when multiple interpretations plausible
	- "I only told John"→ambiguous (told/John/answer); "I told only John"→unambiguous

## Algorithm
Tokenize→parse for errors→classify→minimal correction→validate→verify lexical invariance

Constraint ranking: grammaticality>>coherence>>fidelity>>prosody
