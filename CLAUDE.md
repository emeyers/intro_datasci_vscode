# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **Quarto book** — the textbook *"Introduction to Data Science"* (Python). The "code" is prose chapters in `.qmd` files containing executable Python code blocks. This is teaching material, not an application: the audience is beginners learning data science, so explanations should be clear and code should favor readability over cleverness.

## Commands

This project uses `uv` for Python dependency management (`pyproject.toml` + `uv.lock`).

- **Render the whole book:** `uv run quarto render` → output in `_book/`
- **Live preview while editing:** `uv run quarto preview` (auto-rebuilds on save)
- **Render a single chapter:** `uv run quarto render descriptive_stats_and_plots.qmd`
- **Install/sync deps:** `uv sync`

Publishing is automated: pushing to `main` triggers `.github/workflows/publish.yml`, which renders and deploys to the `gh-pages` branch.

## Chapter structure

`_quarto.yml` defines the book and the **chapter order** — a new chapter only appears in the book if it is added to the `chapters:` list there. Chapters render in listed order:

1. `index.qmd` (welcome) → `introduction.qmd` → `python_basics.qmd` → `descriptive_stats_and_plots.qmd` → `array_computations.qmd` → `data_tables.qmd` → `data_visualization.qmd`

The later chapters are mostly stubs to be filled in.

## Authoring conventions

- **Executable Python blocks use the `{python}` fence** — ` ```{python} ` — not a plain ` ```python `. The curly braces are what makes Quarto execute the block and embed its output. A recurring past bug was blocks failing to run because the braces were missing.
- Code in a chapter shares one kernel session top-to-bottom: variables defined in an early block are available in later blocks. Chapters typically load a dataset once at the top and reference its variables throughout.
- Concepts are built progressively. `descriptive_stats_and_plots.qmd` deliberately uses **base Python + Matplotlib only** (lists, not DataFrames) because Pandas hasn't been taught yet — when editing a chapter, only use tools introduced in it or earlier chapters.
- Datasets are loaded by URL (e.g. the FiveThirtyEight Bechdel CSV) so the GitHub Actions renderer can fetch them without committed data. The local `data/` directory is gitignored.
- Much of the book's material derives from an introductory data science class the author teaches. Relevant source material from that class lives in `extras/` (e.g. class slides, code, notebooks) — **consult these files when developing new chapters or sections**, as they're a primary source for the book's content even though they aren't rendered into it.
  - `extras/material_from_2025f/` holds the notebooks (`class_code/`) and slides (`slides/`) from the **most recent** time the class was taught (Fall 2025) — prefer it over the older `extras/class_notebooks/` and `extras/*_2024f.pdf` material. The class-N notebook usually maps to a book chapter (e.g. `class_06`/`class_07` ≈ the array-computations chapter); `*_answers.ipynb` versions include worked solutions.

## Not part of the book

- `cut_could_be_added_later.qmd`, `notebooks/` — scratch/reference material. Not in `_quarto.yml`, not rendered. Don't treat these as authoritative.
- `creation_pieces/` — a holding area for generated drafts/sections the author isn't using yet but wants to keep (e.g. `array_computations_v1.qmd`, an earlier version of a chapter). Not in `_quarto.yml`, not rendered. Reference for alternative drafts, not authoritative.
- `_book/`, `_freeze/`, `.quarto/`, `*_files/` — generated render artifacts.
- `main.py` — leftover project scaffold, unused.
