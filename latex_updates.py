#!/usr/bin/env python3
"""
latex_updates.py — A&A-style tracked-changes diff between two LaTeX manuscripts.

  New text   : BLUE
  Removed text: ORANGE with strikethrough

A showdeltrue / showdelfalse toggle in the output file controls
whether deleted text is rendered or hidden entirely.

Usage:
    python latex_updates.py old.tex new.tex
    python latex_updates.py old.tex new.tex --output changes.tex
    python latex_updates.py old.tex new.tex --no-compile

Requirements:
    latexdiff   (brew install latexdiff  /  apt install latexdiff  /  tlmgr install latexdiff)
    pdflatex    (for optional compilation)
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path


# ---------------------------------------------------------------------------
# LaTeX brace-matching utilities
# ---------------------------------------------------------------------------

def find_matching_brace(text: str, open_pos: int) -> int:
    """Return position of the } that matches the { at open_pos.

    Correctly handles:
      - \\X sequences (backslash + any character, including \\% and \\{)
      - LaTeX % comment lines (rest of line is ignored for brace counting)
    """
    depth = 1
    i = open_pos + 1
    n = len(text)
    while i < n and depth > 0:
        c = text[i]
        if c == '\\':
            i += 2          # skip the command character after backslash
            continue
        if c == '%':
            while i < n and text[i] != '\n':
                i += 1      # skip to end of comment line
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        i += 1
    return i - 1


def strip_bf_markup(text: str) -> str:
    """Remove {\\bf ...} and \\textbf{...} groups, keeping their content.

    These are old-revision tracking markers that should not appear as
    "changed" text in the diff.
    """
    result = []
    i = 0
    n = len(text)
    while i < n:
        # {\\bf content} → content
        if text[i] == '{' and text[i+1:i+4] == '\\bf':
            after_bf = i + 4
            if after_bf < n and text[after_bf] in ' \t\n\\':
                while after_bf < n and text[after_bf] in ' \t':
                    after_bf += 1
                close = find_matching_brace(text, i)
                result.append(text[after_bf:close])
                i = close + 1
                continue
        # \\textbf{content} → content
        if text[i:i+8] == '\\textbf{':
            open_pos = i + 7
            close = find_matching_brace(text, open_pos)
            result.append(text[open_pos + 1:close])
            i = close + 1
            continue
        result.append(text[i])
        i += 1
    return ''.join(result)


def strip_line_start_bare_groups(text: str, max_passes: int = 8) -> str:
    """Strip bare { } groups that open at the very start of a line.

    These are leftover section-level braces from {\\bf} → { } conversions.
    The pattern is: a line that begins with { followed only by spaces/tabs
    then a newline — the entire matching group is replaced by its content.
    Multiple passes handle nested groups.
    """
    for _ in range(max_passes):
        result = []
        pos = 0
        n = len(text)
        changed = False
        while pos < n:
            at_line_start = (pos == 0 or text[pos - 1] == '\n')
            if at_line_start and pos < n and text[pos] == '{':
                j = pos + 1
                if j < n:
                    k = j
                    while k < n and text[k] in ' \t':
                        k += 1
                    if k < n and text[k] == '\n':
                        close = find_matching_brace(text, pos)
                        result.append(text[j:close])
                        pos = close + 1
                        changed = True
                        continue
            result.append(text[pos])
            pos += 1
        text = ''.join(result)
        if not changed:
            break
    return text


# ---------------------------------------------------------------------------
# File cleaning
# ---------------------------------------------------------------------------

def clean_file(text: str, strip_bare_groups: bool = False) -> str:
    """Prepare a LaTeX file for latexdiff.

    Args:
        text:              Raw LaTeX source.
        strip_bare_groups: Strip line-start bare { } groups (use for the
                           NEW file when the OLD file used {\\bf} markup).
    """
    text = strip_bf_markup(text)
    if strip_bare_groups:
        text = strip_line_start_bare_groups(text)
    return text


# ---------------------------------------------------------------------------
# Diff output customisation
# ---------------------------------------------------------------------------

TOGGLE_PREAMBLE = r"""
%% ============================================================
%% latex_updates — tracked-changes toggle
%%
%%   \showdeltrue    show deleted text in orange (default)
%%   \showdelfalse   hide deleted text entirely
%%
%% Change the line below to switch modes.
%% ============================================================
\newif\ifshowdel
\showdeltrue

%% A&A-style colour overrides for latexdiff markup.
%% \long\def allows arguments that span paragraph breaks.
\long\def\DIFadd#1{{\color{blue}#1}}
\long\def\DIFaddtex#1{{\color{blue}#1}}
\long\def\DIFaddFL#1{\DIFadd{#1}}

\long\def\DIFdel#1{\ifshowdel{\color{orange}\sout{#1}}\fi}
\long\def\DIFdeltex#1{\ifshowdel{\color{orange}\sout{#1}}\fi}
\long\def\DIFdelFL#1{\DIFdel{#1}}

%% Make the float-environment begin/end markers truly empty so that
%% \hline after \DIFaddendFL works correctly inside tabular environments.
\def\DIFaddbeginFL{}
\def\DIFaddendFL{}
\def\DIFdelbeginFL{}
\def\DIFdelendFL{}

"""


def postprocess_diff(text: str) -> str:
    """Inject the colour/toggle preamble into latexdiff output."""
    return text.replace('\\begin{document}',
                        TOGGLE_PREAMBLE + '\\begin{document}', 1)


# ---------------------------------------------------------------------------
# External tool wrappers
# ---------------------------------------------------------------------------

def _check_tool(name: str, install_hint: str) -> None:
    if not shutil.which(name):
        sys.exit(
            f'Error: {name!r} not found.\n'
            f'Install it with:\n{textwrap.indent(install_hint, "  ")}'
        )


def run_latexdiff(old_path: Path, new_path: Path) -> str:
    """Run latexdiff and return the merged diff source."""
    result = subprocess.run(
        [
            'latexdiff',
            '--encoding=utf8',
            '--math-markup=0',
            str(old_path),
            str(new_path),
        ],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    if result.returncode != 0:
        sys.exit(f'latexdiff failed:\n{result.stderr[:1000]}')
    if result.stderr.strip():
        # Print non-fatal warnings so the user is aware
        for line in result.stderr.splitlines()[:5]:
            print(f'  [latexdiff] {line}', file=sys.stderr)
    return result.stdout


def compile_pdf(tex_path: Path) -> bool:
    """Compile tex_path with pdflatex (two passes).  Returns True on success."""
    if not shutil.which('pdflatex'):
        return False
    kwargs = dict(capture_output=True, cwd=tex_path.parent)
    for _ in range(2):
        result = subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', tex_path.name],
            **kwargs,
        )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def generate(
    old_file: str,
    new_file: str,
    output_file: str | None = None,
    do_compile: bool = True,
) -> Path:
    """Run the full pipeline and return the output .tex path."""
    old_path = Path(old_file).resolve()
    new_path = Path(new_file).resolve()

    for p in (old_path, new_path):
        if not p.exists():
            sys.exit(f'Error: file not found: {p}')

    out_path = (
        Path(output_file).resolve()
        if output_file
        else new_path.parent / f'diff_{new_path.name}'
    )

    _check_tool(
        'latexdiff',
        'brew install latexdiff        # macOS\n'
        'apt  install latexdiff        # Debian/Ubuntu\n'
        'tlmgr install latexdiff       # TeX Live',
    )

    # --- Clean ---
    print(f'  Cleaning {old_path.name} (strip {{\\bf}} markup)...')
    old_clean = clean_file(
        old_path.read_text(encoding='utf-8', errors='replace'),
        strip_bare_groups=False,
    )

    print(f'  Cleaning {new_path.name} (strip bare groups)...')
    new_clean = clean_file(
        new_path.read_text(encoding='utf-8', errors='replace'),
        strip_bare_groups=True,
    )

    # Write temporary files adjacent to the inputs
    tmp_dir = old_path.parent
    tmp_old = tmp_dir / f'._lu_old_{old_path.stem}.tex'
    tmp_new = tmp_dir / f'._lu_new_{new_path.stem}.tex'
    try:
        tmp_old.write_text(old_clean, encoding='utf-8')
        tmp_new.write_text(new_clean, encoding='utf-8')

        print('  Running latexdiff...')
        diff_text = run_latexdiff(tmp_old, tmp_new)
    finally:
        tmp_old.unlink(missing_ok=True)
        tmp_new.unlink(missing_ok=True)

    # --- Post-process ---
    print('  Inserting colour definitions and toggle...')
    diff_text = postprocess_diff(diff_text)
    out_path.write_text(diff_text, encoding='utf-8')
    print(f'\n  Diff source → {out_path}')

    # --- Compile ---
    if do_compile:
        if shutil.which('pdflatex'):
            print('  Compiling PDF (2 passes)...')
            ok = compile_pdf(out_path)
            pdf = out_path.with_suffix('.pdf')
            if ok and pdf.exists():
                print(f'  Diff PDF    → {pdf}')
            else:
                print('  PDF compilation had errors — check the .log file.')
                print(f'  Retry with:  pdflatex {out_path.name}')
        else:
            print('  pdflatex not found — skipping compilation.')
            print(f'  Compile with:  pdflatex {out_path.name}')

    return out_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog='latex_updates',
        description=(
            'Generate an A&A-style tracked-changes PDF from two LaTeX manuscripts.\n'
            'New text is shown in BLUE; removed text in ORANGE with strikethrough.'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Output toggle (near top of the generated .tex file):
              \\showdeltrue    — deleted text visible (default)
              \\showdelfalse   — deleted text hidden

            Examples:
              python latex_updates.py v1_paper.tex v2_paper.tex
              python latex_updates.py old.tex new.tex -o changes.tex
              python latex_updates.py old.tex new.tex --no-compile
        """),
    )
    parser.add_argument('old', help='Old version of the manuscript (.tex)')
    parser.add_argument('new', help='New version of the manuscript (.tex)')
    parser.add_argument(
        '-o', '--output', default=None, metavar='FILE',
        help='Output .tex file (default: diff_<new>.tex in same directory)',
    )
    parser.add_argument(
        '--no-compile', action='store_true',
        help='Skip pdflatex compilation (produce .tex only)',
    )
    args = parser.parse_args()

    print(f'\nlatex_updates: generating diff between')
    print(f'  old: {args.old}')
    print(f'  new: {args.new}')
    print()
    generate(args.old, args.new, args.output, do_compile=not args.no_compile)
    print('\nDone.\n')


if __name__ == '__main__':
    main()
