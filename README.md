# latex_updates

**Turn two LaTeX manuscript versions into a tracked-changes PDF in one command.**

When resubmitting a paper after referee comments, most journals ask for a version
showing exactly what changed. `latex_updates` automates the full pipeline:

- Cleans the source files (strips old `{\bf}` markup, bare groups, spacing quirks)
- Runs `latexdiff` with the right options for your journal — detected automatically
- Injects colour definitions: **blue** for additions, **orange wavy strikethrough** for deletions
- Compiles the PDF with two `pdflatex` passes

A one-line toggle in the output lets you switch between the annotated referee version
and a clean resubmission copy without rerunning anything.

---

## Requirements

| Tool | Purpose | Install |
|------|---------|---------|
| Python ≥ 3.10 | runs the package | [python.org](https://python.org) |
| `latexdiff` | computes the word-level diff | see below |
| `pdflatex` | compiles the PDF *(optional)* | part of any TeX distribution |

No Python packages beyond the standard library are required.

### Installing latexdiff

```bash
brew install latexdiff          # macOS
sudo apt install latexdiff      # Debian / Ubuntu
tlmgr install latexdiff         # TeX Live (any platform)
```

---

## Installation

Install directly from GitHub — the `latex_updates` command will be available
everywhere in your terminal:

```bash
pip install git+https://github.com/eartigau/latex-updates.git
```

Or clone and install locally:

```bash
git clone https://github.com/eartigau/latex-updates.git
pip install ./latex-updates
```

---

## Quick start

```bash
# Clone to get the demo files, then try the tool immediately:
git clone https://github.com/eartigau/latex-updates.git
latex_updates latex-updates/demo/demo_old.tex latex-updates/demo/demo_new.tex
```

Output:
```
demo/diff_demo_new.tex   ← tracked-changes LaTeX source
demo/diff_demo_new.pdf   ← compiled PDF (open this)
```

---

## Usage

```
latex_updates OLD.tex NEW.tex [options]
```

| Argument | Description |
|----------|-------------|
| `OLD.tex` | Previous version — the manuscript as originally submitted |
| `NEW.tex` | Revised version — the post-referee manuscript |
| `-o FILE` / `--output FILE` | Custom output filename (default: `diff_<NEW>.tex`) |
| `--no-compile` | Produce the `.tex` diff only; skip pdflatex |

### Examples

```bash
# Typical workflow — produces diff_v2_paper.tex and diff_v2_paper.pdf
latex_updates v1_paper.tex v2_paper.tex

# Name the output file (handy for sending to a referee)
latex_updates old.tex new.tex -o changes_for_referee.tex

# Generate .tex only, compile later (useful if pdflatex needs extra setup)
latex_updates old.tex new.tex --no-compile
pdflatex diff_new.tex
```

---

## Controlling deleted-text visibility

Near the top of every generated `.tex` file you will find a toggle:

```latex
\newif\ifshowdel
\showdeltrue    % ← change to \showdelfalse to hide deleted text
```

| Setting | Effect |
|---------|--------|
| `\showdeltrue` | Deleted text shown in orange with wavy strikethrough — use for the referee response |
| `\showdelfalse` | Deleted text completely hidden — use for the clean resubmission copy |

Edit one word, recompile, done. The same `.tex` file produces both documents.

---

## Automatic journal detection

`latex_updates` reads `\documentclass` and applies journal-specific options
automatically — no flags needed.

| Journal | Detected class | What is handled |
|---------|---------------|-----------------|
| Astronomy & Astrophysics (A&A) | `\documentclass{aa}` | A&A's `\abstract` takes 5 arguments — treated as a block so deleted abstracts compile cleanly. Section headings and `\subtitle` excluded from word-level diff. |
| AASTeX (ApJ, AJ, ApJL, PASP) | `\documentclass{aastex63}` *etc.* | Author-metadata commands (`\affiliation`, `\correspondingauthor`, `\email`, …) excluded from word-level diff. |
| MNRAS | `\documentclass{mnras}` | Standard `abstract` environment — no special handling needed. |
| Any other class | — | Generic mode with math-mode protection. |

The detected journal is printed at the start of every run:

```
latex_updates: generating diff between
  old: old.tex
  new: new.tex

  Detected journal: Astronomy & Astrophysics (A&A)
  Cleaning old.tex (strip {\bf} markup)...
  ...
```

**A&A note:** if `aa.cls` is not in your TeX path, `latex_updates` will search
for it automatically on your system. To install it permanently:
`tlmgr install aa` (TeX Live) or `sudo apt install texlive-publishers` (Debian/Ubuntu).

---

## How it works

1. **Clean the old file** — strips `{\bf …}` and `\textbf{…}` markup that was
   manually added during earlier revision rounds to highlight changes in-text.
2. **Clean the new file** — removes leftover bare `{ }` groups and normalises
   LaTeX spacing commands that confuse latexdiff's parser.
3. **Run `latexdiff`** — word-level diff with math-mode protection and
   journal-specific options.
4. **Inject colour & toggle** — blue additions, orange wavy-strikethrough deletions,
   and `\showdel` flag inserted before `\begin{document}`.
5. **Compile** — two `pdflatex` passes to resolve cross-references and produce the PDF.

---

## Colour conventions

| Element | Colour | Appearance |
|---------|--------|-----------|
| Added text | Blue | `\color{blue}` |
| Removed text | Orange + wavy strikethrough | `\color{orange}\uwave{…}` |

Colours can be customised by editing `TOGGLE_PREAMBLE` in `latex_updates/__init__.py`.

---

## Demo manuscripts

The `demo/` directory contains two versions of a short mock paper
(*On the Statistically Suspicious Helpfulness of Artificial Minds*)
designed to exercise as many diff scenarios as possible:

- **`demo_old.tex`** — 3 authors, 4 sections, numbered list, table, bibliography
- **`demo_new.tex`** — 4th author added, title reworded, numbers updated,
  new list item, extra table row, new subsection, full new Discussion section,
  extended bibliography

Together they cover inline edits, math value changes, and structural additions —
making them a practical smoke-test for any LaTeX diff workflow.

---

## License

MIT — see [LICENSE](LICENSE).
