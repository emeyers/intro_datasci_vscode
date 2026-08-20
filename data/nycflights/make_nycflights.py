#!/usr/bin/env python3
"""Build the book's NYC flight-delay dataset from Bureau of Transportation Statistics data.

Every flight departing the three main New York City airports (Newark, JFK and
LaGuardia) in a given year, with its scheduled and actual times, its delay, and
the airline that operated it.

The BTS publishes one zip file per month covering every domestic flight in the
United States. This script downloads twelve of them, keeps the rows that left a
New York airport, and renames the columns to the schema used by the R packages
`nycflights13` and `nycflights23`, so that the result matches the dataset most
readers will meet elsewhere.

Running this script produces two files in `data/nycflights/`:

    flights.csv.gz   one row per departing flight, gzipped
    airlines.csv     the carrier codes appearing in flights.csv.gz, with names

Usage:

    uv run python data/nycflights/make_nycflights.py

By default it builds the most recent complete calendar year. To build a
different one, and to keep the downloaded zips so a rebuild does not fetch them
again:

    uv run python data/nycflights/make_nycflights.py --year 2023 --zipdir /tmp/bts

Each monthly zip is about 30 MB, so a full year downloads roughly 360 MB. If the
BTS blocks the download, fetch the monthly zips by hand from
<https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ> and put them in
a directory passed with --zipdir; anything already there is reused.

The approach follows the R package `anyflights`
(<https://github.com/simonpcouch/anyflights>), which builds the same data from
the same two sources.
"""

import argparse
import datetime as dt
import io
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

BTS_FLIGHTS_ZIP = (
    "https://transtats.bts.gov/PREZIP/"
    "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip"
)
BTS_CARRIER_LOOKUP = "https://www.transtats.bts.gov/Download_Lookup.asp?Y11x72=Y_haVdhR_PNeeVRef"

# The three main New York City airports, which is what makes this "NYC flights"
# rather than the whole country.
NYC_AIRPORTS = ["EWR", "JFK", "LGA"]

# The BTS column names on the left, the names used by nycflights13/23 on the
# right. Reading only these keeps a 286 MB monthly file down to something small.
COLUMNS = {
    "Year": "year",
    "Month": "month",
    "DayofMonth": "day",
    "DepTime": "dep_time",
    "CRSDepTime": "sched_dep_time",
    "DepDelay": "dep_delay",
    "ArrTime": "arr_time",
    "CRSArrTime": "sched_arr_time",
    "ArrDelay": "arr_delay",
    "Reporting_Airline": "carrier",
    "Flight_Number_Reporting_Airline": "flight",
    "Tail_Number": "tailnum",
    "Origin": "origin",
    "Dest": "dest",
    "AirTime": "air_time",
    "Distance": "distance",
}

# The order columns appear in the finished file, matching nycflights13/23.
FINAL_COLUMNS = [
    "year", "month", "day", "dep_time", "sched_dep_time", "dep_delay",
    "arr_time", "sched_arr_time", "arr_delay", "carrier", "flight", "tailnum",
    "origin", "dest", "air_time", "distance", "hour", "minute", "time_hour",
]

# The BTS front end refuses requests that do not look like they came from a
# browser, the same way the Social Security Administration's does.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def log(message):
    print(message, file=sys.stderr)


def download(url, timeout=600):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def latest_complete_year():
    """The most recent year the BTS is likely to have published in full.

    Monthly files appear a couple of months after the month they cover, so a
    year is only safely complete once we are well into the next one.
    """
    today = dt.date.today()
    return today.year - 1 if today.month >= 4 else today.year - 2


def month_zip(year, month, zipdir):
    """Return the bytes of one monthly BTS file, downloading it if necessary."""
    if zipdir:
        cached = zipdir / f"bts_{year}_{month}.zip"
        if cached.exists():
            log(f"  {year}-{month:02d}: using {cached}")
            return cached.read_bytes()

    url = BTS_FLIGHTS_ZIP.format(year=year, month=month)
    log(f"  {year}-{month:02d}: downloading")
    body = download(url)
    if zipdir:
        zipdir.mkdir(parents=True, exist_ok=True)
        (zipdir / f"bts_{year}_{month}.zip").write_bytes(body)
    return body


def read_month(year, month, zipdir):
    """Read one month and return only the flights leaving a New York airport."""
    archive = zipfile.ZipFile(io.BytesIO(month_zip(year, month, zipdir)))

    # The zip holds the data CSV plus a readme; the data file is the larger one.
    members = sorted(archive.infolist(), key=lambda i: i.file_size, reverse=True)
    data_file = next(m.filename for m in members if m.filename.endswith(".csv"))

    frame = pd.read_csv(
        archive.open(data_file),
        usecols=list(COLUMNS),
        low_memory=False,
    ).rename(columns=COLUMNS)

    nyc = frame[frame["origin"].isin(NYC_AIRPORTS)].copy()
    log(f"    {len(frame):,} US flights, {len(nyc):,} from New York")
    return nyc


def add_time_columns(flights):
    """Split the scheduled departure into hour and minute, and build a timestamp.

    The BTS writes scheduled times as an integer like 1745 for 5:45 pm, so the
    hour is the integer part of a division by 100 and the minute is the
    remainder. `time_hour` is the scheduled departure rounded down to the hour,
    which is what makes this table joinable to hourly weather records.
    """
    scheduled = flights["sched_dep_time"].astype("Int64")
    flights["hour"] = scheduled // 100
    flights["minute"] = scheduled % 100

    # A scheduled time of 2400 means midnight at the end of the day; pandas
    # needs that expressed as hour 0, so wrap it before building the timestamp.
    hour_for_stamp = flights["hour"].where(flights["hour"] < 24, 0)
    flights["time_hour"] = pd.to_datetime(
        dict(
            year=flights["year"],
            month=flights["month"],
            day=flights["day"],
            hour=hour_for_stamp,
        ),
        errors="coerce",
    )
    return flights


def build_airlines(carriers):
    """Fetch the BTS carrier lookup and keep the airlines that actually flew."""
    log("Downloading the carrier lookup")
    lookup = pd.read_csv(io.BytesIO(download(BTS_CARRIER_LOOKUP)), dtype=str)
    lookup = lookup.rename(columns={"Code": "carrier", "Description": "name"})

    airlines = lookup[lookup["carrier"].isin(carriers)].copy()

    # A handful of codes have been reused by different airlines over the years,
    # which leaves duplicate rows; keep the first listing for each code.
    airlines = airlines.drop_duplicates(subset="carrier").sort_values("carrier")

    missing = sorted(set(carriers) - set(airlines["carrier"]))
    if missing:
        log(f"  warning: no name found for {', '.join(missing)}")
    return airlines[["carrier", "name"]]


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--year", type=int, default=latest_complete_year(),
                        help="calendar year to build (default: most recent complete year)")
    parser.add_argument("--months", type=int, nargs="+", default=list(range(1, 13)),
                        help="months to include (default: all twelve)")
    parser.add_argument("--zipdir", type=Path,
                        help="directory to cache the monthly BTS zips in, and to read them from")
    parser.add_argument("--outdir", type=Path, default=here,
                        help="where to write the output files")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    log(f"Building NYC flights for {args.year}")
    try:
        months = [read_month(args.year, m, args.zipdir) for m in args.months]
    except (urllib.error.URLError, urllib.error.HTTPError) as error:
        raise SystemExit(
            f"could not download from the BTS ({error}).\n"
            "Fetch the monthly zips by hand from\n"
            "  https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ\n"
            "save them as bts_<year>_<month>.zip, and pass their directory with --zipdir."
        )

    flights = pd.concat(months, ignore_index=True)
    flights = add_time_columns(flights)
    flights = flights.sort_values(["month", "day", "sched_dep_time"]).reset_index(drop=True)

    # Times, delays and durations are all whole minutes, but a cancelled flight
    # has no actual departure, so these columns need a type that allows a
    # missing value alongside the integers.
    for column in ["dep_time", "sched_dep_time", "dep_delay", "arr_time",
                   "sched_arr_time", "arr_delay", "flight", "air_time",
                   "distance", "hour", "minute"]:
        flights[column] = flights[column].astype("Int64")

    flights = flights[FINAL_COLUMNS]

    flights_path = args.outdir / "flights.csv.gz"
    flights.to_csv(flights_path, index=False, compression="gzip")
    size_mb = flights_path.stat().st_size / 1e6
    log(f"Wrote {flights_path} ({len(flights):,} rows, {size_mb:.1f} MB)")

    airlines = build_airlines(set(flights["carrier"].dropna()))
    airlines_path = args.outdir / "airlines.csv"
    airlines.to_csv(airlines_path, index=False)
    log(f"Wrote {airlines_path} ({len(airlines)} airlines)")


if __name__ == "__main__":
    main()
