#!/usr/bin/env python3
"""
latex_updates — tracked-changes diff between two LaTeX manuscripts.

  New text   : BLUE
  Removed text: ORANGE with wavy strikethrough

Detects the journal from \\documentclass and applies journal-specific
latexdiff options automatically (A&A, AASTeX, MNRAS, …).

Usage:
    latex_updates old.tex new.tex
    latex_updates old.tex new.tex --output changes.tex
    latex_updates old.tex new.tex --no-compile

Requirements:
    latexdiff   (brew install latexdiff  /  apt install latexdiff  /  tlmgr install latexdiff)
    pdflatex    (for optional compilation)
"""

import argparse
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path


# ---------------------------------------------------------------------------
# Journal profiles
# ---------------------------------------------------------------------------
# Each profile specifies:
#   name        — human-readable journal name
#   docclass    — compiled regex matching the \documentclass declaration
#   extra_args  — extra arguments forwarded to latexdiff
#
# Design notes per journal:
#
# A&A  : \abstract{context}{aims}{methods}{results}{conclusions} is a
#         5-argument command.  latexdiff's TEXTCMD mechanism handles only
#         one-argument commands, so word-level diffing inside \abstract
#         produces broken markup.  --append-context2cmd=abstract tells
#         latexdiff to treat \abstract as a context command: in deleted
#         passages the command and its arguments are suppressed entirely,
#         which is clean and always compiles.  \subtitle is A&A-specific
#         and should not be treated as a text command.
#
# AASTeX: author-metadata commands (\affiliation, \correspondingauthor, …)
#         have argument formats incompatible with word-level diffing.
#
# MNRAS : uses a standard abstract environment — no special handling needed.

JOURNALS: dict[str, dict] = {
    'aa': {
        'name': 'Astronomy & Astrophysics (A&A)',
        'docclass': re.compile(
            r'\\documentclass(?:\[[^\]]*\])?\{aa\}', re.IGNORECASE
        ),
        'extra_args': [
            '--append-context2cmd=abstract',
            '--exclude-textcmd=subtitle',
        ],
    },
    'aastex': {
        'name': 'AASTeX (ApJ / AJ / ApJL / PASP)',
        'docclass': re.compile(
            r'\\documentclass(?:\[[^\]]*\])?\{aastex\w*\}', re.IGNORECASE
        ),
        'extra_args': [
            '--exclude-textcmd='
            'affiliation,correspondingauthor,email,received,revised,accepted,published',
        ],
    },
    'mnras': {
        'name': 'Monthly Notices of the Royal Astronomical Society (MNRAS)',
        'docclass': re.compile(
            r'\\documentclass(?:\[[^\]]*\])?\{mnras\}', re.IGNORECASE
        ),
        'extra_args': [],
    },
}


def detect_journal(text: str) -> tuple[str, dict] | tuple[None, None]:
    """Scan LaTeX source for a known \\documentclass and return (key, profile)."""
    for key, profile in JOURNALS.items():
        if profile['docclass'].search(text):
            return key, profile
    return None, None


# ---------------------------------------------------------------------------
# LaTeX brace-matching utilities
# ---------------------------------------------------------------------------

def find_matching_brace(text: str, open_pos: int) -> int:
    """Return position of the } that matches the { at open_pos."""
    depth = 1
    i = open_pos + 1
    n = len(text)
    while i < n and depth > 0:
        c = text[i]
        if c == '\\':
            i += 2
            continue
        if c == '%':
            while i < n and text[i] != '\n':
                i += 1
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        i += 1
    return i - 1


def strip_bf_markup(text: str) -> str:
    """Remove {\\bf ...} and \\textbf{...} groups, keeping their content."""
    result = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == '{' and text[i+1:i+4] == '\\bf':
            after_bf = i + 4
            if after_bf < n and text[after_bf] in ' \t\n\\':
                while after_bf < n and text[after_bf] in ' \t':
                    after_bf += 1
                close = find_matching_brace(text, i)
                result.append(text[after_bf:close])
                i = close + 1
                continue
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
    """Strip bare { } groups that open at the very start of a line."""
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
    """Prepare a LaTeX file for latexdiff."""
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

%% latexdiff loads the 'color' package, which lacks named colours beyond the
%% basic set.  Define orange here so \color{orange} works regardless.
\definecolor{orange}{rgb}{1.0,0.55,0.0}

%% Wavy strikethrough for deleted text.
\DeclareRobustCommand*\DIFwavestrike{\bgroup \ULdepth=-.5ex
  \markoverwith{\hbox{\sixly\char58}}\ULon}

%% Colour overrides for latexdiff markup.
\long\def\DIFadd#1{{\color{blue}#1}}
\long\def\DIFaddtex#1{{\color{blue}#1}}
\long\def\DIFaddFL#1{\DIFadd{#1}}

\long\def\DIFdel#1{\ifshowdel{\color{orange}\DIFwavestrike{#1}}\fi}
\long\def\DIFdeltex#1{\ifshowdel{\color{orange}\DIFwavestrike{#1}}\fi}
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


def run_latexdiff(
    old_path: Path,
    new_path: Path,
    extra_args: list[str] | None = None,
) -> str:
    """Run latexdiff and return the merged diff source."""
    cmd = [
        'latexdiff',
        '--encoding=utf8',
        '--math-markup=0',
        *(extra_args or []),
        str(old_path),
        str(new_path),
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    if result.returncode != 0:
        sys.exit(f'latexdiff failed:\n{result.stderr[:1000]}')
    if result.stderr.strip():
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

    # --- Detect journal ---
    new_text_raw = new_path.read_text(encoding='utf-8', errors='replace')
    journal_key, journal = detect_journal(new_text_raw)
    if journal:
        print(f'  Detected journal: {journal["name"]}')
    else:
        print('  Journal: generic (no known \\documentclass detected)')

    # --- Clean ---
    print(f'  Cleaning {old_path.name} (strip {{\\bf}} markup)...')
    old_clean = clean_file(
        old_path.read_text(encoding='utf-8', errors='replace'),
        strip_bare_groups=False,
    )

    print(f'  Cleaning {new_path.name} (strip bare groups)...')
    new_clean = clean_file(new_text_raw, strip_bare_groups=True)

    # Write temporary files adjacent to the inputs
    tmp_dir = old_path.parent
    tmp_old = tmp_dir / f'._lu_old_{old_path.stem}.tex'
    tmp_new = tmp_dir / f'._lu_new_{new_path.stem}.tex'
    try:
        tmp_old.write_text(old_clean, encoding='utf-8')
        tmp_new.write_text(new_clean, encoding='utf-8')

        print('  Running latexdiff...')
        diff_text = run_latexdiff(
            tmp_old,
            tmp_new,
            extra_args=journal['extra_args'] if journal else None,
        )
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
            'Generate a tracked-changes PDF from two LaTeX manuscripts.\n'
            'Detects A&A, AASTeX, MNRAS and applies journal-specific options.\n'
            'New text is shown in BLUE; removed text in ORANGE with wavy strikethrough.'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Output toggle (near top of the generated .tex file):
              \\showdeltrue    — deleted text visible (default)
              \\showdelfalse   — deleted text hidden

            Examples:
              latex_updates v1_paper.tex v2_paper.tex
              latex_updates old.tex new.tex -o changes.tex
              latex_updates old.tex new.tex --no-compile
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
