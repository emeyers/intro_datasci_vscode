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
- **Voice and tone: warm but precise, approachable but not chatty.** Friendliness should come from *directness and concreteness* — address the reader as "you" for instructions/exercises and "we" for shared reasoning; introduce a concept with a concrete example or problem before naming and defining it; keep sentences short to moderate; define jargon on first use; prefer concrete nouns. Do **not** reach for casual diction: avoid filler intensifiers ("really", "pretty", "super", "a lot"), idioms/clichés ("got the job done", "under the hood", "the heart of", "shines"), colloquial evaluative adjectives ("clunky", "neat", "handy", "nice", "messy"), vague hedges ("basically", "sort of"), jokes/emoji, and forced reassurance ("don't worry, this is easy"). Keep/cut test: phrasing that signals *closeness* (direct "you", a plain imperative, a concrete noun, an honest "this takes practice") stays; phrasing that signals *looseness* (an intensifier, idiom, slang adjective, hedge, or joke) goes. The `chapter-editor` agent enforces this and can run a dedicated tone pass.
- **Avoid prose mannerisms that read as AI-generated.** The biggest tell is the **em dash (—) used as a parenthetical or appositive break** ("arrays — the foundation of NumPy — are..."); rewrite with a comma, a colon, a period splitting the sentence, or parentheses instead. An occasional em dash for a genuine interruption or sentence break is fine, but more than one or two per page is a sign of overuse — restructure the sentence rather than reaching for the dash by default. Also avoid: triplet lists used as a rhythmic crutch ("clearer, faster, and more powerful"), "Let's" as a sentence-opener more than once or twice a chapter, throat-clearing transitions ("It's worth noting that...", "In other words..."), and a too-tidy three-beat cadence on every paragraph. Vary sentence length and structure the way a human writer drafting over multiple sittings would, rather than producing uniformly polished paragraphs.
- Concepts are built progressively. `descriptive_stats_and_plots.qmd` deliberately uses **base Python + Matplotlib only** (lists, not DataFrames) because Pandas hasn't been taught yet — when editing a chapter, only use tools introduced in it or earlier chapters.
- **Illustrations are built with Matplotlib/NumPy, not external images**, with the drawing code hidden via `#| echo: false` so only the figure renders (see the axis-layout and RGB-mixing diagrams in `array_computations.qmd` for the pattern). When a concept is spatial or structural (array shapes, axes, a transformation, a color model), prefer building a diagram this way over describing it in prose alone. The `chapter-student` and `chapter-editor` agents both review illustrations as part of a chapter review: whether each one is easy to understand, and whether a passage would benefit from an illustration that doesn't exist yet.
- **Static, hand-placed images (not code-generated) go in the top-level `images/` directory**, which is tracked in git (unlike `data/`). Reference them with a normal relative path, e.g. `![](images/cover_img.png){width="300px"}` as `index.qmd` does for the book cover. **Every image placed in `images/` must have a corresponding entry in `images/SOURCES.md`** recording where it came from (source URL) and its license — add the entry in the same change that adds the image.
- **End most sections with an exercise.** The established pattern (see ch. 2–4) is one exercise at the end of each content section, plus a consolidated `## Exercises` section at the chapter's end. Each exercise is a `::: {.callout-tip title="Exercise" #exercise-<chapter>-<slug>}` block followed by a collapsible `::: {.callout-note title="Solution" #solution-<chapter>-<slug> collapse="true"}` block. An exercise must only use tools introduced up to that point in the chapter. Pure setup sections (e.g. loading the dataset) can be skipped.
- Datasets are loaded by URL (e.g. the FiveThirtyEight Bechdel CSV) so the GitHub Actions renderer can fetch them without committed data. The local `data/` directory is gitignored.
- Much of the book's material derives from an introductory data science class the author teaches. Relevant source material from that class lives in `extras/` (e.g. class slides, code, notebooks) — **consult these files when developing new chapters or sections**, as they're a primary source for the book's content even though they aren't rendered into it.
  - `extras/material_from_2025f/` holds the notebooks (`class_code/`) and slides (`slides/`) from the **most recent** time the class was taught (Fall 2025) — prefer it over the older `extras/class_notebooks/` and `extras/*_2024f.pdf` material. The class-N notebook usually maps to a book chapter (e.g. `class_06`/`class_07` ≈ the array-computations chapter); `*_answers.ipynb` versions include worked solutions.

## Not part of the book

- `cut_could_be_added_later.qmd`, `notebooks/` — scratch/reference material. Not in `_quarto.yml`, not rendered. Don't treat these as authoritative.
- `creation_pieces/` — a holding area for generated drafts/sections the author isn't using yet but wants to keep (e.g. `array_computations_v1.qmd`, an earlier version of a chapter). Not in `_quarto.yml`, not rendered. Reference for alternative drafts, not authoritative.
- `_book/`, `_freeze/`, `.quarto/`, `*_files/` — generated render artifacts.
- `main.py` — leftover project scaffold, unused.
