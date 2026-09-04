# LLM for STEM

AI workflows that hold up in scientific work.

## The LLM-Wiki mega-prompt

**[`megaprompt-wiki-bootstrap.md`](megaprompt-wiki-bootstrap.md)** bootstraps a
source-faithful research wiki from your own papers, in any scientific field. An AI agent
reads each paper completely, compiles it into structured, interlinked markdown pages, and
designs the folder schema from your sources instead of forcing a generic one on your field.

Built and battle-tested on a real research vault: 73 papers, 405 pages, 12,000+ cross-links,
zero broken.

### How to use it

1. Install [Claude Code](https://claude.com/claude-code) and open it in a **new, empty folder**.
2. Drop 3 to 5 representative papers (PDFs) into a `raw/` subfolder.
3. Paste everything below the horizontal line of `megaprompt-wiki-bootstrap.md` as your
   first message.
4. Answer the interview questions. The agent scaffolds the vault, ingests your papers, and
   proposes a schema tailored to your field. Approve or revise it.
5. From then on the vault's own `CLAUDE.md` governs every session: `INGEST` a new paper,
   `QUERY` the wiki, `LINT` its health. You never paste the mega-prompt again.

### The one rule that makes it work

**Source faithfulness.** The agent must read 100% of a paper before writing about it; every
number, equation, and claim must come from a source it actually read; anything it cannot
find is written as `(not specified in source)`, never guessed. Every page carries a
confidence label.

### What's in the method

- Two-stage bootstrap: interview → minimal vault → schema **discovered from your sources**
- Gated workflows: propose first, wait for approval, then write
- Extraction fidelity rules (the PDF is the arbiter, conversions fail silently)
- Wave-based ingestion, verification with drafter/checker separation
- Tension pages: cross-paper contradictions get their own pages with verbatim quotes
- Scale playbook for 50+ sources (index regeneration, citation reciprocity, linting)

## License

Text of this repository is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
