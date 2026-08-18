#!/usr/bin/env python3
"""Build the book's baby-name dataset from Social Security Administration data.

The SSA publishes two things this script needs:

1. `names.zip`, one `yobYYYY.txt` file per year, each line `name,sex,count`.
   Names given to fewer than five babies in a year are withheld for privacy.
2. A web page, `numberUSbirths.html`, giving the number of Social Security card
   holders born in the U.S. each year, by sex. This is the denominator used for
   the `percent` column: it counts every card holder born that year, including
   the ones whose names were withheld from the zip file, so it is larger than
   the sum of the counts in `names.zip`.

Running this script produces three files in `data/babynames/`:

    baby_names.csv         the 1,000 most common names per sex per year
    baby_names_all.csv.gz  every name the SSA publishes, gzipped
    us_births_by_sex.csv   the denominators from source 2, cached

Usage:

    uv run python data/babynames/make_babynames.py

The SSA blocks automated downloads from some networks with a 403 error. When a
direct download fails the script falls back to the most recent copy in the
Internet Archive, and then to the cached `us_births_by_sex.csv` for the birth
totals. If both sources are unreachable, download the zip file by hand from
<https://www.ssa.gov/oact/babynames/limits.html> and pass it in:

    uv run python data/babynames/make_babynames.py --zip ~/Downloads/names.zip

To rebuild with more recent data, run the script again after the SSA's annual
release (usually in the spring, covering the previous calendar year).
"""

import argparse
import csv
import gzip
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path

SSA_NAMES_ZIP = "https://www.ssa.gov/oact/babynames/names.zip"
SSA_BIRTHS_PAGE = "https://www.ssa.gov/oact/babynames/numberUSbirths.html"
WAYBACK_CDX = "http://web.archive.org/cdx/search/cdx"

# The SSA writes sex as a single letter; the book's dataset spells it out, using
# the same words the SSA's own birth-totals table uses for its columns.
SEX_NAMES = {"M": "boy", "F": "girl"}

# Enough decimal places to keep three significant figures for the rarest name in
# each file. The smallest percentage among the top 1,000 names is about 0.0026,
# while the full file goes down to five births in a year of nearly two million,
# or about 0.00027.
TOP_DECIMALS = 4
FULL_DECIMALS = 6

# The two hosts want opposite things from a client. The SSA's front end refuses
# requests that do not look like they came from a browser, while the Internet
# Archive rejects a browser string it did not send itself and wants a user agent
# that says who is calling.
SSA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
ARCHIVE_HEADERS = {"User-Agent": "intro-datascience-book/1.0 (babynames build script)"}


def log(message):
    print(message, file=sys.stderr)


def download(url, headers, timeout=120, attempts=3):
    """Fetch a URL and return its bytes, transparently un-gzipping the body.

    The Internet Archive serves back whatever the original server sent, which
    for the SSA's HTML pages is gzip-compressed, so the check below looks at the
    first two bytes rather than trusting the response headers. It also rate
    limits, so a rejected request is retried after a pause.
    """
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
            break
        except urllib.error.HTTPError as error:
            if error.code not in (429, 498) or attempt == attempts:
                raise
            pause = 5 * attempt
            log(f"  rate limited (HTTP {error.code}); waiting {pause}s and trying again")
            time.sleep(pause)
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    return body


def wayback_url(url):
    """Return an Internet Archive URL for the most recent capture of `url`.

    The `id_` marker in the returned address asks the archive for the original
    bytes rather than a copy rewritten for viewing in a browser.
    """
    query = urllib.parse.urlencode(
        {
            "url": url,
            "output": "json",
            "filter": "statuscode:200",
            "fl": "timestamp,original",
            "limit": -1,  # a negative limit counts back from the newest capture
        }
    )
    rows = json.loads(download(f"{WAYBACK_CDX}?{query}", ARCHIVE_HEADERS).decode("utf-8"))
    if len(rows) < 2:  # the first row is a header
        raise LookupError(f"the Internet Archive has no capture of {url}")
    timestamp, original = rows[1]
    return f"https://web.archive.org/web/{timestamp}id_/{original}"


def download_with_fallback(url, description):
    """Download from the SSA, falling back to the Internet Archive."""
    log(f"Downloading {description} from {url}")
    try:
        return download(url, SSA_HEADERS)
    except (urllib.error.URLError, urllib.error.HTTPError) as error:
        log(f"  the SSA refused the request ({error}); trying the Internet Archive")

    archived = wayback_url(url)
    log(f"  {archived}")
    return download(archived, ARCHIVE_HEADERS)


def parse_births(page):
    """Turn the SSA's birth-totals page into {year: {"boy": n, "girl": n}}.

    The table has one row per year and columns for year, boys, girls, and total.
    """
    births = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page.decode("utf-8", "replace"), re.S | re.I):
        cells = [
            html.unescape(re.sub(r"<[^>]+>", "", cell)).strip()
            for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)
        ]
        if len(cells) < 3 or not cells[0].isdigit():
            continue  # the header row, and anything else that is not data
        year = int(cells[0])
        births[year] = {
            "boy": int(cells[1].replace(",", "")),
            "girl": int(cells[2].replace(",", "")),
        }
    if not births:
        raise ValueError("found no birth totals in the SSA page; its layout may have changed")
    return births


def read_births_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        births = {}
        for row in csv.DictReader(handle):
            year = int(row["year"])
            births.setdefault(year, {})[row["sex"]] = int(row["count"])
    return births


def write_births_csv(path, births):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["year", "sex", "count"])
        for year in sorted(births):
            for sex in ("boy", "girl"):
                writer.writerow([year, sex, births[year][sex]])


def read_name_counts(archive):
    """Turn the SSA's zip file into {year: {"boy": [(name, count), ...], ...}}.

    Each year's file is already sorted from the most common name to the least,
    so the order of the lists here is the order of popularity.
    """
    counts = {}
    with zipfile.ZipFile(BytesIO(archive)) as names_zip:
        year_files = sorted(n for n in names_zip.namelist() if n.endswith(".txt"))
        if not year_files:
            raise ValueError("the zip file contains no yobYYYY.txt files")
        for filename in year_files:
            year = int(re.search(r"(\d{4})", filename).group(1))
            by_sex = {"boy": [], "girl": []}
            for line in names_zip.read(filename).decode("utf-8").splitlines():
                if not line.strip():
                    continue
                name, sex, count = line.strip().split(",")
                by_sex[SEX_NAMES[sex]].append((name, int(count)))
            counts[year] = by_sex
    return counts


def build_rows(counts, births, limit=None):
    """Generate the rows of the output file, in year order and boys before girls.

    `percent` is a true percentage rather than a proportion, so that the column
    name matches what the column holds: John in 1880 comes out as 8.1546, not
    0.081546.

    `limit` caps how many names are kept per sex per year; `None` keeps them all.
    """
    for year in sorted(counts):
        if year not in births:
            log(f"  skipping {year}: no birth total published for it yet")
            continue
        for sex in ("boy", "girl"):
            total = births[year][sex]
            names = counts[year][sex]
            for name, count in names[:limit] if limit else names:
                yield year, name, sex, count, 100 * count / total


def write_names_csv(path, rows, decimals):
    opener = gzip.open if path.suffix == ".gz" else open
    written = 0
    with opener(path, "wt", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["year", "name", "sex", "count", "percent"])
        for year, name, sex, count, percent in rows:
            writer.writerow([year, name, sex, count, f"{percent:.{decimals}f}"])
            written += 1
    size_mb = path.stat().st_size / 1e6
    log(f"Wrote {path} ({written:,} rows, {size_mb:.1f} MB)")


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--zip", type=Path, help="a local copy of the SSA's names.zip")
    parser.add_argument("--births", type=Path, help="a local copy of the SSA's numberUSbirths.html")
    parser.add_argument("--top", type=int, default=1000, help="names kept per sex per year (default: 1000)")
    parser.add_argument("--outdir", type=Path, default=here, help="where to write the output files")
    parser.add_argument("--no-full", action="store_true", help="skip the full gzipped file")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    births_cache = args.outdir / "us_births_by_sex.csv"

    # 1. The denominators. If neither the SSA nor the archive can be reached,
    #    fall back to the copy saved the last time this script ran.
    if args.births:
        log(f"Reading birth totals from {args.births}")
        births = parse_births(args.births.read_bytes())
    else:
        try:
            births = parse_births(download_with_fallback(SSA_BIRTHS_PAGE, "birth totals"))
        except Exception as error:
            if not births_cache.exists():
                raise SystemExit(f"could not fetch the birth totals and no cached copy exists: {error}")
            log(f"  falling back to the cached {births_cache.name} ({error})")
            births = read_births_csv(births_cache)
    log(f"Birth totals cover {min(births)}-{max(births)}")
    write_births_csv(births_cache, births)

    # 2. The name counts.
    if args.zip:
        log(f"Reading name counts from {args.zip}")
        archive = args.zip.read_bytes()
    else:
        archive = download_with_fallback(SSA_NAMES_ZIP, "the name counts")
    counts = read_name_counts(archive)
    log(f"Name counts cover {min(counts)}-{max(counts)}")

    # 3. The output files.
    write_names_csv(args.outdir / "baby_names.csv", build_rows(counts, births, args.top), TOP_DECIMALS)
    if not args.no_full:
        write_names_csv(args.outdir / "baby_names_all.csv.gz", build_rows(counts, births), FULL_DECIMALS)


if __name__ == "__main__":
    main()
