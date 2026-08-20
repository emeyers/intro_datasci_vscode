# NYC flights

Every flight that departed one of the three main New York City airports in a
single year, used in @sec-data-tables. Compiled from the U.S. Bureau of
Transportation Statistics by `make_nycflights.py`.

This is the same dataset, in the same shape, as the R packages
[nycflights13](https://github.com/tidyverse/nycflights13) and
[nycflights23](https://github.com/moderndive/nycflights23). Those ship only as R
binaries and cover 2013 and 2023, so this version is built from the underlying
government source instead, which means it can be rebuilt for any year including
the most recent one.

## Files

| File | Contents |
|---|---|
| `flights.csv.gz` | One row per departing flight. `pd.read_csv` reads it directly from a URL, no decompression step needed. |
| `airlines.csv` | The carrier codes that appear in `flights.csv.gz`, with the full airline name for each. This is the join partner used in the chapter. |
| `make_nycflights.py` | The script that generates both. |

### `flights.csv.gz`

| Column | Meaning |
|---|---|
| `year`, `month`, `day` | Date of departure |
| `dep_time`, `arr_time` | Actual departure and arrival, as local clock times (`1517` means 3:17 pm) |
| `sched_dep_time`, `sched_arr_time` | The same, as scheduled |
| `dep_delay`, `arr_delay` | Minutes late. **Negative means early** |
| `carrier` | Two-letter airline code, joins to `airlines.csv` |
| `flight` | Flight number |
| `tailnum` | Aircraft registration |
| `origin` | `EWR`, `JFK` or `LGA` |
| `dest` | Destination airport code |
| `air_time` | Minutes in the air |
| `distance` | Miles |
| `hour`, `minute` | Scheduled departure split into parts |
| `time_hour` | Scheduled departure rounded down to the hour |

A **cancelled flight still has a row**, with its scheduled times filled in and
its actual times and delays left empty. Those gaps are the reason the chapter
can discuss missing data using a case where the absence means something
specific rather than signalling an error.

## Where the data comes from

Two sources, both from the Bureau of Transportation Statistics:

1. **[Marketing Carrier On-Time Performance](https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ)**,
   published as one zip file per month covering every domestic flight in the
   United States. The script downloads twelve of them and keeps the rows whose
   origin is `EWR`, `JFK` or `LGA`. Each monthly file is about 30 MB, so a full
   year downloads roughly 360 MB.
2. **The carrier lookup table**, which maps the two-letter codes to airline
   names. It lists every carrier the BTS has ever recorded, so the script keeps
   only the ones that appear in the flights it just built.

The column names are BTS's own (`DepDelay`, `Reporting_Airline`, and so on);
`make_nycflights.py` renames them to the `nycflights13`/`nycflights23` schema so
that the table matches what readers will find in other tutorials and in the
course this book grew out of.

The approach is the one taken by the R package
[anyflights](https://github.com/simonpcouch/anyflights), which builds the same
data from the same two endpoints.

### Terms of use

The Bureau of Transportation Statistics is a U.S. federal agency, so its data is
not subject to copyright protection in the United States (17 U.S.C. § 105). This
is worth noting because the equivalent R packages are GPL-3 licensed; building
from the government source avoids inheriting that.

## Rebuilding the data

```bash
uv run python data/nycflights/make_nycflights.py
```

With no arguments the script builds the most recent complete calendar year. BTS
publishes each month roughly two months in arrears, so a year only becomes
available in full partway through the next one.

Useful options:

- `--year 2023` builds a specific year. Running this is also the way to check the
  script against a published dataset, since it should reproduce nycflights23.
- `--zipdir DIR` caches the monthly zips in `DIR` and reuses anything already
  there. Worth passing, because a rebuild otherwise downloads 360 MB again.
- `--months 1 2 3` builds part of a year, which is much faster when testing.
- `--outdir DIR` writes somewhere other than this directory.

If the BTS blocks the download, fetch the monthly zips by hand from the link
above, save them as `bts_<year>_<month>.zip`, and pass their directory with
`--zipdir`.

### Updating to a new year

Run the script again once the next year is complete, then commit and push the
regenerated files. Two things to remember: the chapter loads these files from a
`raw.githubusercontent.com` URL, so nothing changes until the push lands; and
@sec-data-tables quotes specific figures from the data, so every number in that
chapter needs rechecking against the rebuilt file.
