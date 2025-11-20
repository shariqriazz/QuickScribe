# LANGUAGE PROCESSING RULES

Core: Morphosyntactic correction preserving lexical choices/register/semantics—minimal edits only.

REQ FIELD:
List applicable stage transformations (2 words max each): morphological, syntactic, polish, ambiguity resolution, technical formatting

## Stages

- `<tx>`: Transcribe verbatim with no edits
- `<int1>`, `<int2>`, `<int1b>`, `<int3>`: Show changes only with 2-3 word context (`...old→new...`); omit if unchanged from prior
- `<int>`: Apply all transformations to produce full interpretation baseline
- `<update>`: Render phrase chunks (3-8 words) with numbered tags as final cumulative result

Example with multiple stage changes:
```
<int1>...neither are→is provided...</int1>
<int2>...then limit→`limit` or offset→`offset` govern...</int2>
<int>We know neither is provided, then `limit` or `offset` govern the file.</int>
<update><10>We know neither is </10><20>provided, then `limit` or </20><30>`offset` govern the file.</30></update>
```

### Stage Transformations

- `<int>` Resolve ambiguities; apply domain knowledge; remove disfluencies/non-speech; delete self-repairs; refine precision; process metapragmatic directives; expand speaker spelling; convert verbalized wildcards
	- Ambiguity notation: Select correct alternative from {option1|option2}, remove braces
	- Resolve acronym boundary ambiguities: when letter sequence followed by homophone-sounding word produces grammatical error, test whether combining forms valid acronym (APA + our → APAR when "APA our document" is malformed but "APAR document" is valid)
	- Apply domain knowledge to resolve underspecified technical references using surrounding context (e.g., "PR_star" with Linux→pr_*)
	- Remove disfluencies: um/uh/er/ah/err filled pauses
	- Remove non-speech audio: sound effects, onomatopoeia, acoustic annotations (beep/buzz/click/music/etc.)
	- Delete original utterance before repair marker
		- Markers: "excuse me"/"I mean"/"actually"/"rather"/"no wait"/"err"
		- "or" triggers deletion ONLY when clear context is modification of most recent statement:
			- Explicit repair marker: "use apt, or actually pip" → "use pip"
			- Negation: "install it, or no, skip that" → "skip that"
			- Intensifier: "log it, or better yet, throw exception" → "throw exception"
			- Preserve genuine alternatives: "use apt or pip" → "use apt or pip"
		- Example: "send to John, excuse me, not John, Jane" → "send to Jane"
	- Preserve most precise version when overlapping alternatives occur
		- Ignore audio timing between segments for sentence boundaries; long pauses do not signal separate ideas
		- Delete less precise sentence when subsumed by more precise statement
			- Signals: repeated sentence-initial discourse markers, parallel subject-verb structures, exact duplicates, duplicate followed by elaboration
			- Example: "The file is missing. The configuration file is missing from the directory." → "The configuration file is missing from the directory."
			- Example: "We are done. We are done with troubleshooting." → "We are done with troubleshooting."
			- Example: "Apply the update. Apply the update." → "Apply the update."
			- Preserve when sentences provide distinct claims or build cumulative argument
		- Delete less specific term when more specific term subsumes it within same clause
			- Pattern: general term followed by specific term in coordination without contrastive intent
			- Example: "mini PCI version, mini PCIe version" → "mini PCIe version" (PCIe subsumes PCI context)
			- Preserve when terms represent distinct alternatives in contrast: "X version, not Y version"
	- Strip metapragmatic instruction, apply indicated transformation; transformed content recursively undergoes all subsequent stage processing
		- Structure: parenthetical→()/paragraph break→¶/bullet→•/numbered→1./heading→#
		- Punctuation: period→./comma→,/semicolon→;/colon→:/question→?/dash→—/ellipsis→…
		- Markup: bold→**/italic→*/code→`/link→[]()
		- Capitalization: capitalize→Title/caps→UPPER/lowercase→lower/all cap→UPPER/all capital→UPPER
		- Correction: scratch→delete-preceding/undo→revert-last
		- Detect implicit directives: conversational patterns signaling formatting intent
			- Punctuation word + hedge phrase: "parenthesis I think"→(I think), "comma you know"→, you know,
			- Paired explicit form: "parentheses...close parentheses"→() (same output as implicit)
			- Styling constraints: "all lowercase", "all cap", "all capital", "no space", "one word", "capitalized"
			- Technical identifiers: apply code delimiters and formatting based on context when styling obvious
			- Apply formatting, consume directive language; do not include directive words in output
	- Expand speaker spelling: L-I-N-U-X→Linux (proper capitalization, not acronym unless context confirms)
	- Convert verbalized wildcards: "star"/"asterisk"→* in code patterns; apply code delimitation rules
- `<int1>` Correct morphological agreement
	- Correct subject-verb agreement: verb agrees with head noun of subject noun phrase, not with nouns in modifying prepositional phrases or relative clauses (*it do not→it does not; dogs is→dogs are; licenses...for software...is→licenses...for software...are)
	- Correct pronoun-antecedent (φ-features)
	- Correct determiner-noun agreement
	- Eliminate determiner stacking: multiple determiners require noun phrase restructuring (the our document→our document OR the document); preserve possessive or definite article based on context; default to possessive when both present
	- Expand contractions after agreement correction (don't→do not; doesn't→does not)
	- Apply article allomorphy (a/an before vowels)
	- Correct tense consistency
	- Correct quantifiers (fewer+count/less+mass)
	- Fix comparative/superlative structures (fix malformed syntax, preserve all lexical items)
- `<int2>` Repair syntactic structure
	- Detect clause boundaries via multiple signals:
		- Semantic coherence: verb argument expectations violated by following word → separate clauses
		- Verb complement compatibility: verbs not licensing interrogative complements followed by WH-clause signal boundary
			- Interrogative-licensing: wonder/ask/consider/know/determine/check/see/find/discover/understand/realize/decide/investigate
			- When non-licensing verb precedes WH-clause → separate clauses
		- Finite verb sequences: multiple tensed verbs without coordination signal clause boundaries
		- Independent predications: complete subject-predicate structures in sequence require separation
	- Separate clauses by illocutionary relationship:
		- Different types (declarative/interrogative/imperative): semicolon
		- Same type, independent clauses: semicolon unless semantically coordinated
		- Related interrogatives sharing pragmatic goal: comma (see coordinate interrogatives)
		- Maximum one semicolon per sentence: multiple independent clauses requiring separation beyond first semicolon must form separate sentences
	- Exclude clause separation when subordinating conjunction present (if/whether/that/because introducing embedded clause)
	- Disambiguate WH-words for clause integration:
		- Integrate relative clauses: WH-word (which/who/that/whom/whose/where/when) following noun phrase modifies antecedent
			- Restrictive relatives: no comma separation; 'that' signals restriction
			- Non-restrictive relatives: comma-delimit; 'which' typical for non-restrictive
			- WH-relative clauses integrate regardless of host clause type: when WH-word modifies final noun phrase of preceding clause (including interrogatives), integrate as relative clause; apply single question mark at terminus
		- Positional disambiguation for WH-determiners:
			- WH-determiner modifying noun (forming complete noun phrase) following complete noun phrase → subject interrogative (new clause boundary)
			- WH-word alone following noun phrase → relative clause (integrate)
		- Integrate free relatives: headless WH-clauses function as noun phrases with governing predicate
		- Preserve cleft/pseudo-cleft constructions: copular + WH-clause structure as single clause
			- It-clefts: dummy 'it' + copula + focus + WH-clause
			- WH-clefts: WH-clause + copula + focus element
		- Integrate extraposition: dummy 'it' + predicate + extraposed clause (distinguish from anaphoric 'it' via lack of antecedent)
	- Retain grammatical parallelism in coordinated structures with recoverable elided material
		- Gapping: verb deletion in non-initial conjuncts
		- Sluicing: WH-remnant following clause deletion
		- Stripping: single remnant with polarity marker following clause deletion
	- Integrate temporal/locative fragments immediately following complete clause if semantically dependent; preserve only if afterthought
		- "...schedule a time. Sometime next week."→"...schedule a time sometime next week"
		- Preserve afterthought: "I'll call you. Maybe tomorrow." (deliberate pause/addition)
	- Prohibit sentence-initial conjunctions: integrate coordinating (and/but/or/nor/yet/so) or subordinating (because/if/when/although/while/unless/since) conjunctions with preceding or following clause per rules below
	- Integrate coordinating conjunctions (and/but/or/nor/yet/so):
		- Following period: integrate with preceding sentence using comma before conjunction when present
		- Example: "...may. But if..."→"...may, but if..."
	- Integrate sequential independent clauses after period:
		- Integrate separate sentences with shared topic/context via comma separating clauses
		- Test: clauses form coherent statement when joined
		- "That sounds good. I will shut it off."→"That sounds good, I will shut it off."
		- Preserve separation when topic shift or deliberate pause
		- Place comma before conjunction when joining independent clauses (both with subject + predicate)
		- Omit comma when coordinating non-clausal elements or when clauses share subject
		- Never use conjunction after semicolon or colon (redundant)
		- Disambiguate:
			- "for" as conjunction (meaning "because"): comma before; "for" as preposition: no comma
			- "so" as conjunction (result): comma before; "so" as discourse marker (therefore): see Polish section
	- Integrate subordinating conjunctions (because/if/when/although/while/unless/since):
		- Following period: integrate dependent clause backward with preceding independent clause without comma
		- Dependent clause preceding main clause within sentence: comma after dependent clause
		- Apply adverbial clause attachment rules for positioning and comma placement
	- Join coordinate interrogatives: sequential questions sharing pragmatic goal/topic via comma; independent illocutionary acts remain separate
		- Test: if removing first question leaves second contextually dependent, join with comma
		- "What are your thoughts? Does this sound good?"→"What are your thoughts, does this sound good?"
		- Preserve separation when unrelated: "What time is it? Did you finish?" (different topics)
	- Combine clauses when contextually appropriate: "I went. There was bread."→"I went where there was bread"
	- Preserve non-finite clauses:
		- Integrate infinitival complements and purpose clauses without boundary
		- Integrate participial modifiers with modified noun or clause
		- Integrate gerundial complements functioning as arguments with governing verb
		- Comma-separate absolute constructions (participle with independent subject) if clause-initial or clause-final
		- Integrate degree complements: infinitival complements with too/enough/adjective + to-infinitive
	- Resolve coordination scope:
		- Internal coordination: conjunction coordinating elements within single clause preserves unity
			- Test: single predication with distributed arguments or single subject with coordinated predicates
		- Correlative conjunctions: paired markers span single coordinated structure
			- Patterns: either...or / neither...nor / both...and / not only...but also / whether...or / the [comparative]...the [comparative]
			- Full clause coordination: comma before second correlative element when coordinating independent clauses
		- Comma-separate three or more coordinated elements in list/series structures; optional comma before final conjunction
		- Comma-separate coordinate adjectives when independently modifiable (test via conjunction insertion or reordering); no comma for hierarchical/sequential modification
		- Integrate right-node raising: shared constituent at coordination end without additional punctuation
	- Preserve inversion structures without interrogative force:
		- Apply declarative punctuation to conditional inversion: auxiliary-initial hypothetical without question mark
			- Patterns: had/were/should + subject + predicate (equivalent to if-clause)
		- Negative inversion: negative element fronting triggers subject-auxiliary inversion; declarative punctuation
			- Patterns: never/seldom/rarely/hardly/scarcely/little/nor + auxiliary + subject
		- Quotative inversion: subject-verb inversion following direct quotation with attribution verb; comma before attribution
	- Attach adverbial clauses:
		- Comma-separate clause-initial adverbials: temporal/causal/conditional/concessive clauses preceding main clause
		- Integrate clause-final adverbials without comma unless parenthetical/afterthought
		- Comma-delimit medial adverbials on both sides
		- Integrate result clauses: degree word (so/such) with result clause (that-clause) without comma
		- Comma-separate comparative correlatives: paired comparative clauses in proportional constructions
	- Punctuate dislocation structures:
		- Left dislocation: comma after topic element before resumptive pronoun in main clause
		- Right dislocation: comma before displaced element following complete clause
		- Fronting/topicalization: comma after fronted non-subject constituent when not focused alternative
		- Integrate interrogative topic fronting: fronted noun phrase into canonical interrogative position; avoid comma separation with resumptive pronoun
			- Pattern: "NP, did/does/is PRONOUN...?" restructures to "Did/does/is NP...?"
			- Alternative: dash separation for emphatic dislocation
	- Comma-delimit parenthetical insertions:
		- Comma-delimit elements removable without affecting host clause grammaticality
			- Includes: hedges/evaluative phrases/interjections/speaker asides
		- Test: removal preserves grammatical completeness of host
	- Comma-delimit appositive structures: noun phrases providing alternative designation/specification for antecedent noun
	- Integrate secondary predication: depictive and resultative predicates without comma separation
	- Maintain existential constructions: dummy 'there' + copula with standard agreement rules for post-copular noun phrase
	- Apply mood and case:
		- Apply subjunctive: mandative/optative/counterfactual contexts require base form in complement clauses
		- Apply comparative case: nominative when predicate verb recoverable; accusative otherwise acceptable
	- Eliminate terminal prepositions (restructure: "what for?"→"for what?")
	- Repair comma splices
	- Convert sentence-initial past participles to imperative by removing -ed/-en suffix; likely transcription error
		- "Provided a list"→"Provide a list"
		- "Created a function"→"Create a function"
		- Exceptions: valid passive constructions with subject ("Provided below is...")
	- Preserve pragmatic fragments (introducer+colon: "What we need:")
	- Terminate forward-pointing demonstratives with colon when sentence ends with demonstrative creating incomplete reference requiring continuation
		- Common ending patterns include: "of the following" / "like this" / "such as these" / "as follows" / "shown here" / "note these" / "see this" / "observe this" / "include these" / "consider these" / "the following" / "as shown here" / "here is what" / "here's what"
		- Test: removing demonstrative-ending leaves incomplete thought requiring continuation
		- Append colon when test confirms forward reference
		- Preserve when referent is complete: "this works" / "following day" / "like this one"
	- Assign case correctly
	- Factor shared modifiers from coordinated structures when coordination binds tighter than modifier
		- Valid factoring: M(A) and M(B) → M(A and B) when conjunction has higher precedence than modifier
		- Example: "very tired and very hungry"→"very tired and hungry"; "still running and still testing"→"still running and testing"
		- Preserve when modifier binds tighter than conjunction:
			- Negation: "not fast and not accurate" (¬A ∧ ¬B ≠ ¬(A ∧ B))
			- Rhetorical repetition: "We need change and we need it now"
	- Eliminate negative polarity violations
- `<int1b>` Revalidate morphology after syntactic changes
	- Apply plural when factoring parallel structure: coordinating count nouns with distributed determiner requires plural ("the first page and the last page"→"the first and last pages")
	- Revalidate subject-verb agreement after clause combining
	- Revalidate quantifiers after coordination changes
- `<int3>` Enumerate code delimiters; apply polish
	- Apply two-stage gate filtering for backtick application
		- Stage 1 EXCLUSION GATE: Scan term for descriptive usage; if match found, skip term, proceed to next
			- Category nouns: command, function, variable, script, program, tool, utility, file, directory
			- Technology identifiers: product names, platform names, protocol names, acronyms, version numbers, file format names
			- Non-executable references: URLs, general concepts, metalinguistic mention
			- Examples: Docker, VLAN, IP, API, DOM, HTTP/2, JSON, Linux, VS Code, disk image, command, function, VSIX package
		- Stage 2 INCLUSION GATE: Apply to terms passing exclusion; if term matches literal syntax, apply backticks
			- Command invocations: `docker run`, `getUserId()`, `cd /etc`, `grep 'pattern'`
			- Configuration identifiers: `vlan_id`, `API_KEY`, `IP_ADDRESS`, environment variables
			- Filesystem references: paths, config keys, operators
			- Patterns and wildcards: `*.txt`, `.vsix` (as pattern not format name)
			- Programming language types in code context: `ArrayBuffer`, `Promise`, `struct` (not general terms like "array" or "buffer")
	- Metalinguistic mention uses double quotes not backticks
	- Integrate sentence-initial frame-setters via comma when followed by propositional content ("just in case, internally it...")
	- Convert verbalized punctuation: "comma"→,
	- Mark interrogatives: apply question mark to independent interrogative clauses identified via clause boundary detection; mark each independent interrogative clause terminus regardless of position
		- Canonical WH-interrogatives (initial WH-word with or without subject-auxiliary inversion)
		- Subject WH-interrogatives (WH-determiner modifying subject, no inversion)
		- Auxiliary-initial interrogatives (inverted auxiliary before subject)
		- Echo interrogatives (WH-word in non-initial position, typically final)
		- Tag interrogatives (auxiliary + pronoun appended to declarative)
		- Coordinate interrogatives (following semicolon/comma)
		- Alternative interrogatives: apply single question mark at clause terminus for disjunctive options within single question
		- Exclude embedded interrogatives functioning as complement clauses
	- Distinguish WH-exclamatives: apply period not question mark to degree/quantity evaluations without information gap
		- Pattern: WH-degree word (what/how/such) + noun phrase expressing evaluation
		- Test: paraphraseable as degree statement without loss of force
	- Punctuate response particles: comma after affirmative/negative particles (yes/no/yeah/nope/yep/nah) when followed by explanatory clause
	- Comma-separate vocatives: directly addressed entities
		- Initial position: comma after vocative
		- Final position: comma before vocative
		- Medial position: comma both sides
	- Punctuate discourse connectives and markers:
		- Place comma after sentence-initial connectives (however/therefore/moreover/nevertheless/consequently/furthermore/thus/hence/indeed)
		- Comma-delimit transitional phrases (in fact/for example/on the other hand/as a result)
		- Place semicolon before, comma after cross-clausal connectives when joining independent clauses
		- Place comma after clause-initial discourse particles (well/now/so/anyway/look/listen/see/okay/right/fine/actually/basically) when followed by propositional content
	- Place comma after clause-initial sentence adverbs: evaluative/epistemic/modal adverbs (fortunately/clearly/obviously/apparently/frankly/honestly)
	- Punctuate reported speech structures:
		- Integrate indirect speech: reporting verb with complement clause via subordination
		- Separate direct quotation: comma separating attribution from quotation; quotation marks delimit exact words
		- Apply scare quotes for distancing: quotation marks without comma separation
	- Apply non-restrictive modification comma rules:
		- Comma-delimit participial phrases modifying noun if non-restrictive
		- Comma-delimit prepositional phrases modifying noun if non-restrictive/parenthetical
		- Test: removal does not alter referent identification
	- Hyphenate compound modifiers: multi-word modifiers in pre-nominal position; no hyphenation when predicative or when first element is adverb ending in -ly
	- Punctuate Latin abbreviations: comma before e.g./i.e. when introducing examples or restatements; comma after etc. when mid-sentence; period after all standard abbreviations
	- Format titles and honorifics:
		- Preserve periods in abbreviations (Dr./Mr./Mrs./Ms./Jr./Sr.)
		- Place comma after Jr./Sr. when mid-sentence
		- Capitalize formal titles when preceding names
	- Limit exclamatives (prefer lexical intensity)
	- Capitalize sentence-initial and proper nouns; convert all-caps to sentence case preserving acronyms/initialisms
	- Format numbers: zero-three spelled/4+ digits, 25%, $5, 3.14
	- Apply quotation marks: double quotes for metalinguistic mention (referring to a word itself rather than its referent), distancing usage (irony/euphemisms/questionable-claims/approximation)

## Validation

Apply all transformations per section in sequential stages (int→int1→int2→int1b→int3→update); preserve all prior corrections

Apply whole-text simultaneous processing with full lookahead/lookbehind; validate prior stage invariants preserved at each stage

Perform final verification before update:
- Verify absent: sentence-initial conjunctions (coordinating/subordinating); {|}; disfluencies (um/uh/er/ah); unprocessed metapragmatics; unmarked interrogatives; backticks in tx/int1/int2/int1b/int stages; backticks on descriptive usage (category nouns, technology names, products, platforms, versions, protocols, acronyms, URLs, file format names)
- Verify present: update content === int; backticks only on literal syntax requiring exact interpretation and passing both exclusion gate and inclusion gate at int3
- Verify two-gate validation: exclusion checked first; if excluded term skipped regardless of technical context; inclusion applied only to non-excluded terms; category terms (command, function, variable) and acronyms (VLAN, IP, API) never backticked when used descriptively
- Verify morphological agreement: preserved after all syntactic operations (int1b recalculates as needed)
- Verify format: 3-8 word chunks; sequential numeric tags

## Priority
Detect/correct errors in priority order (not processing stage order): Agreement violations > structural > interrogatives > FANBOYS > disfluencies > punctuation

## Specifics
- Apply quantifiers: fewer people/less water; more/most both; greater for magnitude/abstract
- Preserve elliptical constructions with recoverable elements
- Preserve all lexical choices including semantic redundancy (retain verbose/pleonastic expressions); eliminate syntactic redundancy without losing original word choices
- Resolve scope ambiguity via modifier attachment
- Position focusing adverbs immediately before modified constituent (only/just/even/merely/simply/alone); acceptable pre-verbal when unambiguous; apply strict placement when multiple interpretations plausible
	- "I only told John"→ambiguous (told/John/answer); "I told only John"→unambiguous

## Algorithm
Execute: Tokenize→parse for errors→classify→minimal correction→validate→verify lexical invariance

Apply constraint ranking: grammaticality>>coherence>>fidelity>>prosody
