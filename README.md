# latex_updates

**Generate A&A-style tracked-changes documents between two LaTeX manuscripts.**

New text is shown in **blue**.  
Removed text is shown in **orange with strikethrough**.  
A one-line toggle controls whether deleted text is visible in the PDF.

---

## Requirements

| Tool | Purpose | Install |
|------|---------|---------|
| Python ≥ 3.10 | runs the package | [python.org](https://python.org) |
| `latexdiff` | computes the diff | see below |
| `pdflatex` | compiles the PDF | part of any TeX distribution |

### Installing latexdiff

```bash
# macOS (Homebrew)
brew install latexdiff

# Debian / Ubuntu
sudo apt install latexdiff

# TeX Live (any platform)
tlmgr install latexdiff
```

No Python packages beyond the standard library are required.

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
git clone https://github.com/eartigau/latex-updates.git
cd latex-updates
latex_updates demo/demo_old.tex demo/demo_new.tex
```

This produces:
```
demo/diff_demo_new.tex   ← tracked-changes LaTeX source
demo/diff_demo_new.pdf   ← compiled PDF
```

---

## Usage

```
latex_updates OLD.tex NEW.tex [options]
```

| Argument | Description |
|----------|-------------|
| `OLD.tex` | Previous version of the manuscript |
| `NEW.tex` | New version of the manuscript |
| `-o FILE` / `--output FILE` | Override the output filename (default: `diff_<NEW>.tex`) |
| `--no-compile` | Skip pdflatex; produce `.tex` only |

### Examples

```bash
# Basic usage — produces diff_v2_paper.tex and diff_v2_paper.pdf
latex_updates v1_paper.tex v2_paper.tex

# Custom output name
latex_updates old.tex new.tex -o for_referee.tex

# Generate .tex only (compile later)
latex_updates old.tex new.tex --no-compile
pdflatex diff_new.tex
```

---

## Controlling deleted-text visibility

Near the top of every generated `.tex` file you will find:

```latex
%% latex_updates toggle
\newif\ifshowdel
\showdeltrue   ← change to \showdelfalse to hide deleted text
```

- **`\showdeltrue`** (default) — deleted text appears in orange with strikethrough  
- **`\showdelfalse`** — deleted text is completely hidden (clean submission copy)

---

## How it works

1. **Clean** the old file — strips `{\bf …}` and `\textbf{…}` markup that was
   added manually to track changes in earlier rounds.
2. **Clean** the new file — strips leftover bare `{ }` groups at section level.
3. **Run `latexdiff`** — computes a word-level diff between the two cleaned files.
4. **Inject** the colour definitions and `\showdel` toggle into the output.
5. **Compile** with `pdflatex` (two passes for cross-references).

The generated `.tex` file is a self-contained manuscript that compiles with
any standard LaTeX installation, including the A&A (`aa.cls`) document class.

---

## Colour conventions

| Element | Colour | LaTeX |
|---------|--------|-------|
| Added text | Blue | `{\color{blue} …}` |
| Removed text | Orange + strikethrough | `{\color{orange}\sout{…}}` |

The colours can be customised by editing the `TOGGLE_PREAMBLE` string in
`latex_updates/__init__.py`.

---

## Demo

The `demo/` directory contains two realistic astronomy manuscripts:

- **`demo_old.tex`** — first-submission version of a paper on wide substellar
  companions (1 800-star sample, 14 recovered companions)
- **`demo_new.tex`** — revised version after a referee round (2 126 stars,
  17 companions, new Discussion section, updated results)

Run:
```bash
latex_updates demo/demo_old.tex demo/demo_new.tex
```

---

## License

MIT — see [LICENSE](LICENSE).
