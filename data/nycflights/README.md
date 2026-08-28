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

| File | Size | Contents |
|---|---|---|
| `flights.csv.gz` | 8.9 MB | One row per departing flight. `pd.read_csv` reads it directly from a URL, no decompression step needed. |
| `airlines.csv` | 318 B | The carrier codes that appear in `flights.csv.gz`, with the full airline name for each. The first join partner used in the chapter. |
| `weather.csv.gz` | 351 KB | Hourly weather at the three New York airports. Joins to `flights.csv.gz` on `origin` **and** `time_hour`. |
| `airports.csv` | 8 KB | The 119 airports that appear in `flights.csv.gz`, with city, state and coordinates. Joins to `dest` (or `origin`). |
| `make_nycflights.py` | — | The script that generates all four. |

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

### `weather.csv.gz`

One row per airport per hour: 3 airports × roughly 8,760 hours, or 26,247 rows.

| Column | Meaning |
|---|---|
| `origin` | `EWR`, `JFK` or `LGA`, the airport the observation was made at |
| `year`, `month`, `day`, `hour` | The hour the observation describes, in New York local time |
| `temp`, `dewp` | Temperature and dew point, in °F |
| `humid` | Relative humidity, as a percentage |
| `wind_dir` | Wind direction, in degrees clockwise from north |
| `wind_speed`, `wind_gust` | Wind and gust speed, in miles per hour |
| `precip` | Precipitation in the last hour, in inches |
| `pressure` | Sea-level pressure, in millibars |
| `visib` | Visibility, in miles |
| `time_hour` | The observation hour, matching `time_hour` in `flights.csv.gz` |

The times are deliberately requested in **New York local time**, because
`time_hour` in `flights.csv.gz` is built from each flight's scheduled *local*
departure. That is what lets the two tables be joined on `origin` and
`time_hour` together, which matches 99.9% of flights. A `wind_gust` is missing
whenever the wind was steady, which is most of the time, so that column is an
example of a gap that means "nothing to report" rather than "not recorded".

### `airports.csv`

| Column | Meaning |
|---|---|
| `faa` | Three-letter airport code, joins to `dest` or `origin` |
| `name` | Airport name, as the BTS writes it |
| `city`, `state` | Where the airport is |
| `lat`, `lon` | Latitude and longitude, in degrees |
| `alt` | Elevation, in feet |

Only the airports that actually appear in `flights.csv.gz` are listed, which is
why the file is 119 rows rather than the tens of thousands in the source lookup.
The `lat` and `lon` columns are here so that a later chapter can put these
destinations on a map.

## Where the data comes from

Flights and airline names come from the Bureau of Transportation Statistics:

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

Weather comes from a third source:

3. **The [Iowa Environmental Mesonet's ASOS archive](https://mesonet.agron.iastate.edu/ASOS/)**,
   which serves hourly surface observations for any station and date range as a
   CSV. This is the same source `nycflights13` uses. The script requests the
   three New York stations for one year, keeps the first observation in each
   hour, and converts wind from knots to miles per hour and pressure from
   inches of mercury to millibars.

Airport names come from the **BTS airport lookup**, so that an airport is called
here what it is called in the flight records themselves. Coordinates come from
**[OurAirports](https://ourairports.com/data/)**, matched on the IATA code with
the ICAO identifier (the same code with a `K` in front) as a fallback. The
fallback is not hypothetical: OurAirports has reassigned `PBI` to a new code
following a renaming, and without the fallback Palm Beach would lose its
coordinates.

The approach is the one taken by the R package
[anyflights](https://github.com/simonpcouch/anyflights), which builds the same
data from the same endpoints.

### Terms of use

**Everything here is in the public domain and can be redistributed with the
book.** Specifically:

- The Bureau of Transportation Statistics is a U.S. federal agency, so its data
  is not subject to copyright protection in the United States (17 U.S.C. § 105).
  This is worth noting because the equivalent R packages are GPL-3 licensed;
  building from the government source avoids inheriting that.
- The ASOS observations are collected by the National Weather Service and the
  FAA and archived by NOAA's National Centers for Environmental Information, so
  they are U.S. government works on the same footing. The Iowa Environmental
  Mesonet redistributes them and does not add a licence of its own.
- OurAirports states that "all data is released to the Public Domain, and comes
  with no guarantee of accuracy or fitness for use."

An earlier draft of the airport table used OpenFlights, which is **ODbL**
licensed and would have imposed attribution and share-alike obligations on the
book. It was replaced with the two public-domain sources above for that reason;
do not switch back without checking the licence implications.

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
- `--parts weather airports` rebuilds only the small files, which takes seconds
  and downloads about 15 MB rather than 360 MB. The airport list is read back
  out of the existing `flights.csv.gz`, so the flight data is not fetched again.
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
