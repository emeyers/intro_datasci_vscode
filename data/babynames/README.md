# Baby names

The dataset used in @sec-introduction, built from U.S. Social Security
Administration records. It replaces
[hadley/data-baby-names](https://github.com/hadley/data-baby-names), which stops
at 2008; this version currently covers **1880–2025**.

## Files

| File | Contents |
|---|---|
| `baby_names.csv` | The 1,000 most common names per sex per year. 291,876 rows, 8.8 MB. This is the file the book loads. |
| `baby_names_all.csv.gz` | Every name the SSA publishes, gzipped. 2,181,032 rows, 10.9 MB. `pd.read_csv` reads it directly, no decompression step needed. |
| `us_births_by_sex.csv` | The denominators used to compute `percent`, saved so the build can run when the SSA's page is unreachable. |
| `make_babynames.py` | The script that generates all three. |

Both name files have the same five columns:

| Column | Meaning |
|---|---|
| `year` | Year of birth, 1880–2025 |
| `name` | The given name, 2 to 15 characters |
| `percent` | `count` divided by the number of card holders of that sex born that year, stored as a proportion (`0.081546`, not `8.1546`) |
| `sex` | `boy` or `girl` |
| `count` | Number of babies given the name that year |

`percent` carries six decimal places in `baby_names.csv` and eight in
`baby_names_all.csv.gz`. The smallest proportion among the top 1,000 names is
about 2.6 × 10⁻⁵, whereas the full file goes down to five births in a year of
nearly two million, so the extra places keep three significant figures in each
file rather than rounding the rarest names toward zero.

The column names and the `boy`/`girl` spelling are carried over from the older
dataset so that code written against it keeps working; `count` is new.

## Where the data comes from

Two SSA sources, both linked from
[Beyond the Top 1000 Names](https://www.ssa.gov/oact/babynames/limits.html):

1. **`names.zip`** — one `yobYYYY.txt` file per year, each line `name,sex,count`,
   sorted by frequency. This supplies `name`, `sex`, and `count`.
2. **[Number of Social Security card holders born in the U.S. by year of birth
   and sex](https://www.ssa.gov/oact/babynames/numberUSbirths.html)** — supplies
   the denominator for `percent`.

The second source is needed because the first is incomplete by design. Using the
sum of the counts in `names.zip` as the denominator instead would put Mary at
7.8% of girls born in 1880 rather than 7.2%, because the withheld rare names
would vanish from the total as well as from the list.

As of August 2026 the SSA's servers return `403 Forbidden` to automated
downloads from at least some networks, so the files here were built from
Internet Archive captures: `names.zip` from 14 August 2026 and the birth totals
page from 5 June 2026.

### Provenance of the method

The two-source approach is the one used by
[jsvine/babynames](https://github.com/jsvine/babynames) and by the R
[babynames](https://github.com/hadley/babynames) package. Rebuilding the years
those datasets already cover reproduces them: of the 258,000 rows in
`hadley/data-baby-names`, 257,498 match on year, name, and sex, with a mean
absolute difference in `percent` of 7 × 10⁻⁷. The remaining rows are names that
moved across the rank-1,000 boundary and a small number of counts the SSA has
revised since 2008.

### What the data does and does not measure

- It counts **applications for a Social Security card**, not births. Nobody who
  never applied appears in it.
- Social Security began in 1936, so people born before then are represented only
  if they applied later in life. The earliest decades undercount, and undercount
  unevenly.
- Names given to **fewer than five babies** in a year are withheld for privacy,
  which is why `count` never drops below 5.
- Names are recorded as they were written on the application, so spelling
  variants are separate names, and a name's apparent decline is sometimes a
  split between two spellings.

The SSA states that for U.S. births in 2025 the top 1,000 names represent about
72 percent of all names, which is a useful check on this build: the same figure
computed from `baby_names.csv` and `us_births_by_sex.csv` is 71.5 percent.

### Terms of use

The data is published by a U.S. federal agency and is not subject to copyright
protection in the United States (17 U.S.C. § 105).

## Rebuilding the data

```bash
uv run python data/babynames/make_babynames.py
```

The script downloads both sources, falling back to the Internet Archive when the
SSA refuses the request. If neither is reachable, download `names.zip` by hand
from <https://www.ssa.gov/oact/babynames/limits.html> and pass it in:

```bash
uv run python data/babynames/make_babynames.py --zip ~/Downloads/names.zip
```

Other options: `--top N` changes how many names per sex per year go into
`baby_names.csv`, `--no-full` skips the gzipped file, `--births` takes a local
copy of the birth-totals page, and `--outdir` writes somewhere other than this
directory.

### Updating to a new year

The SSA adds a year of data each spring. To pick it up, run the script again and
commit the regenerated files. Nothing else needs to change, but note that
@sec-introduction quotes figures for the most recent year in the file, so check
those sentences against the new data.
