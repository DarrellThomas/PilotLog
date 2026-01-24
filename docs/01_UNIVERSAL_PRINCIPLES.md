# Universal Programming & Architecture Principles

**Purpose:** These principles apply to ALL projects. Load this prompt before any project-specific work. These are non-negotiable foundations for building maintainable, scalable systems.

---

## Core Philosophy

> "Architecture is portable, tools are not." — Nate's First Principle

Learn and apply **patterns**, not just tools. Tools change; principles endure. When you understand *why* something works, you can implement it anywhere.

---

## 1. CLEAN CODE FUNDAMENTALS

### 1.1 Naming

- **Use intention-revealing names.** A name should tell you why it exists, what it does, and how it's used.
- **Avoid disinformation.** Don't use names that obscure meaning or conflict with established meanings.
- **Make meaningful distinctions.** If names must differ, they should differ meaningfully (`getActiveAccount()` vs `getActiveAccountInfo()` is noise).
- **Use pronounceable names.** Code is read by humans. `genymdhms` is unacceptable; `generationTimestamp` is clear.
- **Use searchable names.** Single-letter variables and numeric constants are impossible to grep.
- **Avoid encodings.** No Hungarian notation. No `m_` prefixes. Modern IDEs make these obsolete.
- **Class names are nouns.** `Customer`, `WikiPage`, `Account`, `AddressParser`.
- **Method names are verbs.** `postPayment`, `deletePage`, `save`.

### 1.2 Functions

- **Small.** Functions should be small. Then smaller than that.
- **Do one thing.** A function should do one thing, do it well, and do it only.
- **One level of abstraction per function.** Don't mix high-level concepts with low-level details.
- **Descriptive names.** Long descriptive names are better than short enigmatic ones.
- **Minimal arguments.** Zero arguments (niladic) is best. One (monadic) is good. Two (dyadic) is acceptable. Three (triadic) requires justification. More requires refactoring.
- **No flag arguments.** Passing a boolean into a function screams "this function does more than one thing."
- **No side effects.** A function that promises to do one thing should not secretly modify state elsewhere.
- **Command-Query Separation.** Functions should either do something OR answer something, never both.
- **Prefer exceptions to error codes.** Error codes force immediate handling; exceptions allow cleaner logic flow.
- **DRY: Don't Repeat Yourself.** Duplication is the root of all software evil.

### 1.3 Comments

- **Comments are a failure to express yourself in code.** Strive for self-documenting code.
- **Good comments:** Legal notices, explanation of intent, clarification when code cannot be changed, warnings, TODO markers, documentation for public APIs.
- **Bad comments:** Mumbling, redundant comments, misleading comments, mandated comments, journal comments, noise comments, commented-out code.
- **If you must comment, comment the WHY, not the WHAT.** The code shows what; comments explain why.

### 1.4 Formatting

- **Vertical openness.** Separate concepts with blank lines.
- **Vertical density.** Related code should appear dense.
- **Vertical distance.** Variables declared close to their usage. Related functions near each other.
- **Horizontal alignment is unnecessary.** Modern IDEs handle this.
- **Team rules.** Consistency within a codebase trumps individual preference.

### 1.5 Error Handling

- **Use exceptions rather than return codes.**
- **Write try-catch-finally first.** Define scope and behavior from the start.
- **Use unchecked exceptions.** Checked exceptions violate the Open/Closed Principle.
- **Provide context with exceptions.** Include operation attempted and failure type.
- **Don't return null.** Return empty collections or use the Null Object pattern.
- **Don't pass null.** Forbid it in your APIs.
- **Don't swallow errors.** Every error is information. Log it, handle it, or propagate it.

---

## 2. ARCHITECTURE PRINCIPLES

### 2.1 Separation of Concerns

- **Single Responsibility Principle (SRP).** A class/module should have one and only one reason to change.
- **Separate construction from use.** Main/startup logic should be isolated from runtime behavior.
- **Separate policy from mechanism.** High-level business rules should not know about low-level implementation details.
- **Dependency Injection.** Don't create dependencies; receive them.

### 2.2 Module Design

- **High cohesion.** Elements within a module should be strongly related.
- **Low coupling.** Modules should have minimal dependencies on each other.
- **Information hiding.** Expose only what's necessary.
- **Program to interfaces, not implementations.**

### 2.3 The Law of Demeter

A method `f` of class `C` should only call methods of:
- `C` itself
- Objects created by `f`
- Objects passed as arguments to `f`
- Objects held in instance variables of `C`

**No train wrecks:** `a.getB().getC().doSomething()` violates this law.

### 2.4 Avoid Circular Dependencies

- Module A should never depend on Module B if Module B depends on Module A.
- Use dependency inversion or event-driven patterns to break cycles.
- Circular dependencies indicate unclear module boundaries.

---

## 3. PRINCIPLES-BASED GUIDANCE (AI-Era Building)

> "Principles-based guidance scales way better than rules-based guidance." — Nate's Second Principle

### 3.1 Write Principles, Not Rules

When guiding AI agents or future developers:
- **Principle:** "Use test-driven development"
- **Rule:** "Write a test file named `test_<module>.py` for every module"

The principle allows judgment; the rule is brittle.

### 3.2 Enable Self-Correction

- If an AI agent builds it, the agent can maintain it.
- Keep conversation context and artifacts.
- Document the *build process*, not just the result.
- Design for agent maintainability: clear structure, explicit dependencies, observable state.

### 3.3 Infrastructure vs. Tool Mindset

- **Tool:** Solves a specific problem for you.
- **Infrastructure:** Enables others (including future you, or agents) to build on top.

Ask: "Could this become infrastructure?" Design accordingly.

---

## 4. TESTING PRINCIPLES

### 4.1 The Three Laws of TDD

1. You may not write production code until you have written a failing unit test.
2. You may not write more of a unit test than is sufficient to fail.
3. You may not write more production code than is sufficient to pass the test.

### 4.2 F.I.R.S.T. Tests

- **Fast.** Tests should run quickly.
- **Independent.** Tests should not depend on each other.
- **Repeatable.** Tests should work in any environment.
- **Self-validating.** Tests should have boolean output (pass/fail).
- **Timely.** Tests should be written just before the production code.

### 4.3 One Assert Per Test (guideline, not law)

Each test should verify a single concept. Multiple asserts are acceptable if they verify aspects of the same behavior.

### 4.4 Test Boundary Conditions

- Empty collections
- Null inputs
- Maximum/minimum values
- Off-by-one errors
- Concurrent access

---

## 5. CONCURRENCY PRINCIPLES

### 5.1 Keep Concurrency-Related Code Separate

Concurrency design is hard enough without mixing it with business logic.

### 5.2 Limit Scope of Shared Data

Use `synchronized` sparingly. Prefer immutable data.

### 5.3 Use Copies of Data

When possible, avoid sharing by giving each thread its own copy.

### 5.4 Threads Should Be Independent

Design threads to operate without sharing state where possible.

### 5.5 Know Your Execution Models

- Producer-Consumer
- Readers-Writers
- Dining Philosophers

Understand the patterns and their failure modes.

---

## 6. CODE SMELLS TO AVOID

### Comments
- Inappropriate information
- Obsolete comments
- Redundant comments
- Commented-out code

### Environment
- Build requires more than one step
- Tests require more than one step

### Functions
- Too many arguments
- Output arguments
- Flag arguments
- Dead functions

### General
- Obvious behavior is unimplemented
- Incorrect behavior at boundaries
- Overridden safeties
- Duplication (DRY violations)
- Code at wrong level of abstraction
- Feature envy
- Selector arguments
- Obscured intent
- Misplaced responsibility
- Magic numbers
- Structure over convention violations

### Names
- Names at wrong abstraction level
- Names that don't describe side effects
- Unambiguous names missing

---

## 7. EMERGENT DESIGN RULES (Kent Beck)

In priority order:
1. **Runs all the tests.** A system that cannot be verified cannot be trusted.
2. **Contains no duplication.** The DRY principle.
3. **Expresses the intent of the programmer.** Clear, readable code.
4. **Minimizes the number of classes and methods.** Don't over-engineer.

---

## 8. THE BOY SCOUT RULE

> "Leave the campground cleaner than you found it."

Every time you touch code, leave it better than you found it. Small improvements compound.

---

## Usage Notes for Claude-Code

When starting any project:
1. Load this principles document first
2. Load project-specific principles (if any)
3. Load project specifications
4. Begin implementation with these principles as your foundation

**Remember:** These are not suggestions. They are the standards by which professional code is judged.
