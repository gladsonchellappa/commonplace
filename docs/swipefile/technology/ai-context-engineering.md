# AI Context Engineering

Context engineering is the discipline of crafting what information reaches an AI model and how it's structured. Unlike prompt engineering's focus on single queries, context engineering addresses the entire information environment—system prompts, retrieved documents, conversation history, and tool outputs—that shapes model behavior across interactions.

## Table of Contents

1. [Foundations](#1-foundations)
   - [1.1 Context Windows](#11-context-windows)
   - [1.2 Attention Mechanics](#12-attention-mechanics)
   - [1.3 Position Effects](#13-position-effects)
2. [Context Components](#2-context-components)
   - [2.1 System Prompts](#21-system-prompts)
   - [2.2 Few-Shot Examples](#22-few-shot-examples)
   - [2.3 Retrieved Context](#23-retrieved-context)
   - [2.4 Conversation History](#24-conversation-history)
3. [Retrieval Augmented Generation](#3-retrieval-augmented-generation)
   - [3.1 Chunking Strategies](#31-chunking-strategies)
   - [3.2 Embedding Models](#32-embedding-models)
   - [3.3 Retrieval Methods](#33-retrieval-methods)
   - [3.4 Reranking](#34-reranking)
4. [Context Optimization](#4-context-optimization)
   - [4.1 Compression Techniques](#41-compression-techniques)
   - [4.2 Selective Inclusion](#42-selective-inclusion)
   - [4.3 Structured Formatting](#43-structured-formatting)
5. [Agentic Context](#5-agentic-context)
   - [5.1 Tool Definitions](#51-tool-definitions)
   - [5.2 State Management](#52-state-management)
   - [5.3 Memory Systems](#53-memory-systems)
6. [Evaluation and Debugging](#6-evaluation-and-debugging)
   - [6.1 Context Ablation](#61-context-ablation)
   - [6.2 Attribution Analysis](#62-attribution-analysis)
   - [6.3 Failure Modes](#63-failure-modes)
7. [Advanced Patterns](#7-advanced-patterns)
   - [7.1 Multi-Document Reasoning](#71-multi-document-reasoning)
   - [7.2 Hierarchical Context](#72-hierarchical-context)
   - [7.3 Dynamic Context Assembly](#73-dynamic-context-assembly)

## 1. Foundations

Context engineering builds on understanding how transformer models process input sequences. The mechanics of attention, positional encoding, and context window limits create constraints that shape effective context design.

- **Context as Environment** — The model has no persistent memory between calls. Every piece of information it needs must exist in the current context. This includes task instructions, relevant knowledge, output format requirements, and any state from prior interactions.
- **Quality over Quantity** — More context isn't always better. Irrelevant information dilutes attention, increases latency, and can confuse the model. The goal is maximum signal density—every token should earn its place.
- **Reproducibility** — Identical context produces nearly identical outputs (modulo temperature). This makes context the primary lever for controlling model behavior, more reliable than hoping the model "remembers" prior interactions.

### 1.1 Context Windows

The context window is the maximum tokens a model can process in one call.

- **Window Sizes** — GPT-4 Turbo: 128K tokens. Claude 3: 200K tokens. Gemini 1.5: 1M+ tokens. Larger windows enable more context but with tradeoffs in cost, latency, and attention quality.
- **Effective Length** — Models don't use all positions equally. Performance often degrades on very long contexts, especially for information in the middle (lost in the middle phenomenon). A 128K window doesn't mean 128K tokens of equally-accessible information.
- **Token Economics** — Input tokens cost money and time. A 100K context at $0.01/1K tokens = $1 per call. Compression and selective retrieval become economically necessary at scale.

```text
┌────────────────────────────┐
│      Context Window        │
├────────────────────────────┤
│ [System] Instructions      │
│ [Retrieved] Documents      │
│ [History] Prior messages   │
│ [User] Current query       │
│ [Assistant] Response...    │
└────────────────────────────┘
  ◄─── Token limit (e.g. 128K)
```

### 1.2 Attention Mechanics

Self-attention lets each token attend to all others, but attention isn't uniform.

- **Attention Patterns** — Models develop learned patterns: attending to recent tokens, punctuation, semantically similar content, and instruction-like text. Understanding these patterns informs context placement.
- **Attention Dilution** — With more tokens, attention per token decreases on average. Critical information competes with filler for model focus. This is why concise, high-signal context outperforms verbose alternatives.
- **KV Cache** — During generation, the model caches key-value pairs for all context tokens. This enables efficient autoregressive generation but means context processing happens once, then is fixed.

### 1.3 Position Effects

Where information appears in context affects how models use it.

- **Primacy Effect** — Information at the beginning (system prompt, first examples) often has outsized influence. Models anchor on early instructions.
- **Recency Effect** — Recent tokens (end of context, just before the query) are highly attended. Place critical information near the user's question.
- **Lost in the Middle** — Information buried in long contexts is often ignored. Studies show U-shaped retrieval accuracy: good at start, good at end, poor in middle. Structure context to avoid burying key facts.

**Attention by position:**

```text
┌─────────────────────────┐
│ ████                    │ Start
│ ██                      │
│ █                       │ Middle
│ █                       │ (weak)
│ ██                      │
│ ████                    │ End
└─────────────────────────┘
```

## 2. Context Components

Effective contexts combine multiple components, each serving distinct purposes.

### 2.1 System Prompts

The system prompt establishes baseline behavior, persona, and constraints.

- **Role Definition** — Specify what the model is ("You are a senior software engineer..."), what it knows, and how it should behave. Concrete personas outperform vague ones.
- **Output Constraints** — Define format requirements (JSON, markdown, specific structure), length limits, and style guidelines. Be explicit: "Respond in exactly 3 bullet points" beats "be concise."
- **Behavioral Rules** — Safety guidelines, refusal conditions, and interaction patterns. These shape responses across all queries. Place non-negotiable rules here rather than hoping per-query instructions stick.
- **Persistence** — System prompts persist across conversation turns (in most APIs). Changes mid-conversation can confuse the model about which rules apply.

```text
┌─────────────────────────┐
│ SYSTEM PROMPT           │
├─────────────────────────┤
│ Role: [who/what]        │
│ Knowledge: [domain]     │
│ Format: [output spec]   │
│ Rules: [constraints]    │
│ Tone: [style guide]     │
└─────────────────────────┘
```

### 2.2 Few-Shot Examples

Examples demonstrate desired behavior more effectively than descriptions.

- **Format Demonstration** — Show exactly what outputs should look like. One good example often beats paragraphs of explanation. The model pattern-matches against examples.
- **Edge Case Coverage** — Include examples of tricky cases: how to handle ambiguity, what to do with invalid input, when to refuse. Examples teach boundaries.
- **Diversity** — Varied examples prevent overfitting to narrow patterns. If all examples are short, outputs will be short. Mix lengths, styles, and complexity levels.
- **Order Matters** — Place most relevant examples last (recency effect). Start with typical cases, end with the pattern most similar to the current query.

### 2.3 Retrieved Context

Retrieved documents provide knowledge the model wasn't trained on.

- **Source Attribution** — Mark retrieved content clearly: "According to [Document X]: ..." This helps the model distinguish retrieved facts from its parametric knowledge.
- **Relevance Filtering** — Only include documents actually relevant to the query. Irrelevant context is worse than no context—it distracts and can introduce conflicting information.
- **Recency Signals** — For time-sensitive information, include dates. "As of January 2026, the policy states..." helps the model reason about currency.
- **Conflict Handling** — When sources disagree, make conflicts explicit. "Source A says X, but Source B says Y" lets the model reason about uncertainty rather than arbitrarily picking one.

### 2.4 Conversation History

Prior turns provide continuity but accumulate noise.

- **Selective Retention** — Not all history is equally valuable. Summarize or drop old turns that aren't relevant to the current query. Full history quickly exhausts context windows.
- **Reference Resolution** — History enables pronouns and references ("the file we discussed", "that error"). Without history, every turn requires complete re-specification.
- **Correction Handling** — When users correct the model, keep the correction visible. "User: Actually, it's Python 3.11, not 3.10" teaches the model the right fact for this conversation.
- **Summarization** — For long conversations, periodically summarize prior context into a compact form. Replace verbose history with "Summary of prior discussion: [key points]."

## 3. Retrieval Augmented Generation

RAG connects models to external knowledge bases, enabling responses grounded in specific documents.

```text
┌─────────┐  ┌─────────┐
│ Query   │──►│ Embed   │
└─────────┘  └────┬────┘
                  │
            ┌─────▼─────┐
            │ Vector    │
            │ Store     │
            └─────┬─────┘
                  │
            ┌─────▼─────┐
            │ Top-K     │
            │ Chunks    │
            └─────┬─────┘
                  │
┌─────────┐ ┌─────▼─────┐
│ Query   │─►│ LLM       │
│ +Context│  │ Generate  │
└─────────┘ └───────────┘
```

### 3.1 Chunking Strategies

Documents must be split into chunks for embedding and retrieval.

- **Fixed Size** — Split every N tokens (e.g., 512). Simple but breaks mid-sentence and ignores document structure. Use overlap (e.g., 50 tokens) to preserve boundary context.
- **Semantic Chunking** — Split on natural boundaries: paragraphs, sections, sentences. Preserves coherent units but produces variable sizes.
- **Recursive Splitting** — Try larger chunks first; if too big, recursively split on smaller separators (section → paragraph → sentence). Balances coherence with size limits.
- **Parent-Child** — Embed small chunks for precise retrieval, but retrieve the parent chunk (larger context) for the LLM. Best of both: precise matching, sufficient context.

### 3.2 Embedding Models

Embeddings convert text to vectors for similarity search.

- **Model Selection** — OpenAI text-embedding-3, Cohere embed-v3, open-source bge, e5. Different models have different dimensionality, performance, and cost tradeoffs.
- **Query vs Document** — Some models use different prompts for queries vs documents. "query: what is X" vs "passage: X is defined as..." improves asymmetric retrieval.
- **Dimensionality** — Higher dimensions (1536, 3072) capture more nuance but cost more storage and compute. For many use cases, 768 dimensions suffice.
- **Fine-Tuning** — Domain-specific fine-tuning improves retrieval for specialized corpora. General embeddings may miss domain terminology relationships.

### 3.3 Retrieval Methods

Beyond simple vector similarity, multiple retrieval strategies exist.

- **Dense Retrieval** — Embed query, find nearest vectors. Fast and semantic but misses keyword matches. The standard approach.
- **Sparse Retrieval** — BM25/TF-IDF keyword matching. Excellent for exact terms, acronyms, rare words that embeddings miss.
- **Hybrid** — Combine dense and sparse scores. Reciprocal Rank Fusion (RRF) merges ranked lists. Covers both semantic similarity and keyword matching.
- **Multi-Query** — Generate query variations, retrieve for each, deduplicate. "Expand the question into 3 related questions" improves recall for ambiguous queries.

### 3.4 Reranking

Initial retrieval is fast but imprecise. Reranking improves precision.

- **Cross-Encoders** — Score each (query, document) pair with a model that sees both together. More accurate than bi-encoder similarity but O(n) inference—use only on top-K candidates.
- **LLM Reranking** — Ask the LLM to rank retrieved chunks by relevance. Expensive but can incorporate nuanced relevance judgments.
- **Diversity** — Pure similarity ranking can return redundant documents. Maximal Marginal Relevance (MMR) balances relevance with diversity.

## 4. Context Optimization

With limited context windows and attention, optimization is essential.

### 4.1 Compression Techniques

Reduce token count while preserving information.

- **Summarization** — Summarize verbose documents before including. A 1-page summary of a 50-page document may suffice for the query at hand.
- **Extraction** — Pull only relevant sections rather than whole documents. "Extract paragraphs mentioning X" focuses on pertinent content.
- **Deduplication** — Retrieved chunks often overlap. Remove redundant content that would waste tokens.
- **Prompt Compression** — Tools like LLMLingua use small models to identify and remove tokens with minimal information loss. Can achieve 2-10x compression.

### 4.2 Selective Inclusion

Decide what deserves context space.

- **Query Analysis** — Parse the query to determine what information types are needed. A factual question needs different context than a creative task.
- **Confidence Thresholds** — Only include retrieved chunks above a relevance threshold. Low-scoring chunks likely hurt more than help.
- **Dynamic Budgets** — Allocate context tokens based on query complexity. Simple questions need less context; complex reasoning needs more.
- **Tiered Context** — Include detailed context for top-1 result, summaries for results 2-5, just titles for results 6-10.

### 4.3 Structured Formatting

How information is formatted affects model comprehension.

- **Clear Delimiters** — Use XML tags, markdown headers, or clear separators. `<document>...</document>` or `### Source 1` helps models parse structure.
- **Consistent Schema** — If including multiple items, use consistent structure. Tables, lists, and repeated patterns are easier to process than ad-hoc prose.
- **Metadata Placement** — Put source, date, and author at the start of each chunk. Models use this for attribution and recency reasoning.
- **Whitespace** — Judicious whitespace improves readability for models too. Wall-of-text contexts are harder to parse.

```xml
<source id="1">
  <title>Doc A</title>
  <date>2026-01</date>
  <content>
    Relevant text...
  </content>
</source>
```

## 5. Agentic Context

AI agents require context that enables multi-step reasoning and tool use.

### 5.1 Tool Definitions

Tools extend model capabilities through structured context.

- **Function Schemas** — Define tools with name, description, parameters, and return type. Clear descriptions are critical—the model chooses tools based on descriptions.
- **Usage Examples** — Show when and how to use each tool. "Use search when the user asks about current events" guides tool selection.
- **Error Handling** — Define what to do when tools fail. "If api_call returns an error, inform the user and suggest alternatives."
- **Constraints** — Specify limits: "Maximum 3 tool calls per turn", "Always confirm before executing delete."

### 5.2 State Management

Agents maintain state across actions.

- **Scratchpad** — Include a "thinking" or "notes" section the agent can write to and read from. Externalizes working memory.
- **Progress Tracking** — For multi-step tasks, include a checklist or status summary. "Completed: steps 1-3. Remaining: steps 4-5."
- **Variable Binding** — Let agents name and reference intermediate results. "Let X = result of step 1. In step 3, use X."

### 5.3 Memory Systems

Long-term memory extends beyond single contexts.

- **Episodic Memory** — Store summaries of past interactions. "On Jan 15, user asked about X and preferred approach Y."
- **Semantic Memory** — Facts learned during operation. "User's timezone is PST. User prefers Python over JavaScript."
- **Procedural Memory** — Learned procedures and preferences. "When deploying, always run tests first."
- **Memory Retrieval** — Query memories based on current context. Include relevant memories in the prompt, exclude irrelevant ones.

## 6. Evaluation and Debugging

Context problems cause many LLM failures. Systematic debugging is essential.

### 6.1 Context Ablation

Ablation studies isolate component contributions.

- **Remove and Test** — Remove each context component and measure impact. If removing a section doesn't hurt, it's wasting tokens.
- **Reorder and Test** — Move components to different positions. Performance changes reveal position sensitivity.
- **Minimal Context** — Find the smallest context that achieves acceptable performance. This is your baseline—additions must justify their cost.

### 6.2 Attribution Analysis

Understand what the model is using.

- **Attention Visualization** — Tools can show which context tokens the model attended to during generation. Reveals whether retrieved documents are actually used.
- **Citation Prompting** — Ask the model to cite its sources. "Quote the passage that supports your answer." Tests whether answers are grounded.
- **Counterfactual Testing** — Change a fact in context and verify the output changes. If it doesn't, the model is using parametric knowledge, not context.

### 6.3 Failure Modes

Common context-related failures and fixes.

- **Hallucination Despite Context** — Model ignores provided facts, generates from training data. Fix: stronger grounding instructions, explicit "only use provided context."
- **Context Poisoning** — Irrelevant or adversarial content in context derails responses. Fix: better retrieval filtering, input validation.
- **Instruction Forgetting** — Model loses track of system prompt instructions in long conversations. Fix: repeat key instructions, summarize periodically.
- **Format Drift** — Output format degrades over conversation turns. Fix: include format examples in system prompt, remind periodically.

## 7. Advanced Patterns

Sophisticated context engineering for complex applications.

### 7.1 Multi-Document Reasoning

Synthesizing across multiple sources.

- **Explicit Synthesis Prompts** — "Compare the perspectives in Documents A, B, and C on topic X." Direct the model to cross-reference.
- **Structured Comparison** — Present documents in parallel structure to facilitate comparison. Tables with documents as columns work well.
- **Conflict Resolution** — "If sources conflict, note the disagreement and explain which is more authoritative and why."
- **Citation Requirements** — "Every claim must cite at least one source document." Forces grounding.

### 7.2 Hierarchical Context

Organizing context at multiple granularities.

- **Overview + Detail** — Start with high-level summary, then detailed sections. Model can use overview for orientation, detail for specifics.
- **Table of Contents** — For long contexts, include a TOC. Models can "navigate" mentally and may focus attention more effectively.
- **Progressive Disclosure** — Start with minimal context, let the model request more. Reduces noise for simple queries.

### 7.3 Dynamic Context Assembly

Building context based on runtime conditions.

- **Query Classification** — Classify incoming query, route to appropriate context template. FAQ queries get different context than debugging requests.
- **Conversation Phase** — Early conversation needs onboarding context; later turns need less. Adapt context to conversation stage.
- **User Profiling** — Personalize context based on user expertise, preferences, history. Expert users get technical context; novices get simplified.
- **Feedback Loops** — If model output fails validation, add error feedback to context and retry. "Previous attempt failed because: [error]. Try again avoiding this issue."

```text
┌────────────────────────┐
│   Query Analysis       │
└───────────┬────────────┘
            │
      ┌─────▼───────┐
      │ Route/Select│
      └─────┬───────┘
            │
  ┌─────────┼─────────┐
  ▼         ▼         ▼
┌─────┐  ┌─────┐  ┌─────┐
│CTX A│  │CTX B│  │CTX C│
└──┬──┘  └──┬──┘  └──┬──┘
   └────────┼─────────┘
            ▼
      ┌────────────┐
      │ Assemble   │
      └────────────┘
```
