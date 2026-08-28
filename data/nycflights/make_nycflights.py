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

Running this script produces four files in `data/nycflights/`:

    flights.csv.gz   one row per departing flight, gzipped
    airlines.csv     the carrier codes appearing in flights.csv.gz, with names
    weather.csv.gz   hourly weather at the three New York airports, gzipped
    airports.csv     the airports appearing in flights.csv.gz, with locations

The weather and airport tables exist so that the book can teach joins on data
that carries genuinely new information rather than only decoding a lookup code.
Both are small: weather is about 360 KB gzipped and airports about 12 KB.

Every source used here is in the public domain, so all four files can be
redistributed with the book:

  * Flight records and carrier names come from the Bureau of Transportation
    Statistics, a US government agency.
  * Weather comes from the Iowa Environmental Mesonet's archive of ASOS
    observations, which is the same source the R package `nycflights13` uses.
    The observations are made by the National Weather Service and the FAA, so
    they are US government works.
  * Airport names and coordinates come from OurAirports
    (<https://ourairports.com/data/>), which states that "all data is released
    to the Public Domain".

Usage:

    uv run python data/nycflights/make_nycflights.py

By default it builds the most recent complete calendar year. To build a
different one, and to keep the downloaded zips so a rebuild does not fetch them
again:

    uv run python data/nycflights/make_nycflights.py --year 2023 --zipdir /tmp/bts

Building the flights file downloads roughly 360 MB of monthly zips, one per
month at about 30 MB each. The weather and airport files are small and can be
rebuilt on their own, which reads the airport codes back out of an existing
flights.csv.gz rather than downloading the flight data again:

    uv run python data/nycflights/make_nycflights.py --parts weather airports

If the BTS blocks the download, fetch the monthly zips by hand from
<https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ> and put them in
a directory passed with --zipdir; anything already there is reused.

The approach follows the R package `anyflights`
(<https://github.com/simonpcouch/anyflights>), which builds the same data from
the same sources.
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

# Hourly surface observations. The times are requested in New York local time so
# that `time_hour` here lines up with the `time_hour` built from each flight's
# scheduled local departure, which is what makes the two tables joinable.
IEM_ASOS = (
    "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
    "?{stations}"
    "&data=tmpf&data=dwpf&data=relh&data=drct&data=sknt&data=gust"
    "&data=p01i&data=alti&data=vsby"
    "&year1={year}&month1=1&day1=1&year2={next_year}&month2=1&day2=1"
    "&tz=America%2FNew_York&format=onlycomma&latlon=no"
    "&missing=M&trace=T&direct=no&report_type=3"
)

BTS_AIRPORT_LOOKUP = "https://www.transtats.bts.gov/Download_Lookup.asp?Y11x72=Y_NVecbeg"
OURAIRPORTS_LOOKUP = "https://davidmegginson.github.io/ourairports-data/airports.csv"

# The three main New York City airports, which is what makes this "NYC flights"
# rather than the whole country.
NYC_AIRPORTS = ["EWR", "JFK", "LGA"]

# The order columns appear in weather.csv.gz, matching nycflights13/23.
WEATHER_COLUMNS = [
    "origin", "year", "month", "day", "hour", "temp", "dewp", "humid",
    "wind_dir", "wind_speed", "wind_gust", "precip", "pressure", "visib",
    "time_hour",
]

# The IEM reports wind in knots and pressure as an altimeter setting in inches
# of mercury; nycflights13 uses miles per hour and millibars.
KNOTS_TO_MPH = 1.15078
INHG_TO_MILLIBARS = 33.8639

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


def build_weather(year):
    """Download a year of hourly weather for the three New York airports.

    The IEM returns every routine observation, which is usually one per hour per
    airport but occasionally more. Keeping the first observation in each hour
    gives exactly one row per airport per hour, which is the shape a join
    against the flight data needs.
    """
    log("Downloading hourly weather observations")
    stations = "&".join(f"station={code}" for code in NYC_AIRPORTS)
    url = IEM_ASOS.format(stations=stations, year=year, next_year=year + 1)

    raw = pd.read_csv(io.BytesIO(download(url)), na_values=["M"], low_memory=False)
    raw["valid"] = pd.to_datetime(raw["valid"])
    raw["time_hour"] = raw["valid"].dt.floor("h")
    raw = raw.sort_values("valid")
    hourly = raw.groupby(["station", "time_hour"], as_index=False).first()

    # A "T" in the precipitation column means a trace of rain too small to
    # measure, which is a real observation of almost no rain rather than a
    # missing one, so it becomes zero rather than NaN.
    precip = pd.to_numeric(hourly["p01i"].replace("T", 0.0), errors="coerce")

    weather = pd.DataFrame({
        "origin": hourly["station"],
        "year": hourly["time_hour"].dt.year,
        "month": hourly["time_hour"].dt.month,
        "day": hourly["time_hour"].dt.day,
        "hour": hourly["time_hour"].dt.hour,
        "temp": hourly["tmpf"].round(1),
        "dewp": hourly["dwpf"].round(1),
        "humid": hourly["relh"].round(1),
        "wind_dir": hourly["drct"].round(0).astype("Int64"),
        "wind_speed": (hourly["sknt"] * KNOTS_TO_MPH).round(1),
        "wind_gust": (hourly["gust"] * KNOTS_TO_MPH).round(1),
        "precip": precip,
        "pressure": (hourly["alti"] * INHG_TO_MILLIBARS).round(1),
        "visib": hourly["vsby"],
        "time_hour": hourly["time_hour"],
    })

    # The request runs to the first hour of the following year so that the last
    # night of December is complete; trim anything that spilled over.
    weather = weather[weather["year"] == year]
    return weather.sort_values(["origin", "time_hour"])[WEATHER_COLUMNS]


def build_airports(codes):
    """Look up the airports that appear in the flight data, with their locations.

    Names come from the BTS, so that an airport is called here what it is called
    in the flight records themselves, and coordinates come from OurAirports.
    Filtering to the airports the flights actually use keeps the file at a
    hundred-odd rows rather than the eighty thousand in the full lookup.
    """
    log("Downloading the airport lookup")
    lookup = pd.read_csv(
        io.BytesIO(download(BTS_AIRPORT_LOOKUP)), dtype=str, encoding="latin-1"
    ).rename(columns={"Code": "faa", "Description": "description"})
    lookup = lookup[lookup["faa"].isin(codes)].drop_duplicates("faa").sort_values("faa")

    # The BTS writes a description as "West Palm Beach, FL: Palm Beach
    # International", which holds the city, the state and the airport name.
    place, name = lookup["description"].str.split(": ", n=1, expand=True).pipe(
        lambda parts: (parts[0], parts[1])
    )
    city, state = place.str.rsplit(", ", n=1, expand=True).pipe(
        lambda parts: (parts[0], parts[1])
    )

    airports = pd.DataFrame({
        "faa": lookup["faa"], "name": name, "city": city, "state": state,
    }).reset_index(drop=True)

    log("Downloading airport coordinates")
    coords = pd.read_csv(io.BytesIO(download(OURAIRPORTS_LOOKUP)), low_memory=False)
    coords = coords[coords["type"] != "closed"]
    position_columns = ["latitude_deg", "longitude_deg", "elevation_ft"]

    # Match on the IATA code, and fall back to the ICAO identifier, which for
    # the United States is the same code with a K in front. The fallback matters
    # when an airport has been renamed and its IATA code reassigned, which has
    # happened to at least one airport in this data.
    by_iata = (coords.dropna(subset=["iata_code"]).drop_duplicates("iata_code")
               .set_index("iata_code")[position_columns])
    by_icao = coords.drop_duplicates("ident").set_index("ident")[position_columns]

    position = by_iata.reindex(airports["faa"]).reset_index(drop=True)
    fallback = by_icao.reindex("K" + airports["faa"]).reset_index(drop=True)
    position = position.fillna(fallback)

    airports["lat"] = position["latitude_deg"].round(4).values
    airports["lon"] = position["longitude_deg"].round(4).values
    airports["alt"] = position["elevation_ft"].round(0).astype("Int64").values

    unnamed = sorted(set(codes) - set(airports["faa"]))
    if unnamed:
        log(f"  warning: no name found for {', '.join(unnamed)}")
    unplaced = sorted(airports.loc[airports["lat"].isna(), "faa"])
    if unplaced:
        log(f"  warning: no coordinates found for {', '.join(unplaced)}")
    return airports


def airport_codes_from_file(flights_path):
    """Read the airport codes back out of an already-built flights file."""
    log(f"Reading airport codes from {flights_path}")
    existing = pd.read_csv(flights_path, usecols=["origin", "dest"])
    return set(existing["origin"].dropna()) | set(existing["dest"].dropna())


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
    parser.add_argument("--parts", nargs="+", default=["flights", "weather", "airports"],
                        choices=["flights", "weather", "airports"],
                        help="which files to build (default: all of them). Building "
                             "'flights' also builds airlines.csv, and downloads about "
                             "360 MB; 'weather' and 'airports' are small and can be "
                             "rebuilt on their own.")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    flights_path = args.outdir / "flights.csv.gz"
    flights = None

    if "flights" in args.parts:
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

        # Times, delays and durations are all whole minutes, but a cancelled
        # flight has no actual departure, so these columns need a type that
        # allows a missing value alongside the integers.
        for column in ["dep_time", "sched_dep_time", "dep_delay", "arr_time",
                       "sched_arr_time", "arr_delay", "flight", "air_time",
                       "distance", "hour", "minute"]:
            flights[column] = flights[column].astype("Int64")

        flights = flights[FINAL_COLUMNS]

        flights.to_csv(flights_path, index=False, compression="gzip")
        size_mb = flights_path.stat().st_size / 1e6
        log(f"Wrote {flights_path} ({len(flights):,} rows, {size_mb:.1f} MB)")

        airlines = build_airlines(set(flights["carrier"].dropna()))
        airlines_path = args.outdir / "airlines.csv"
        airlines.to_csv(airlines_path, index=False)
        log(f"Wrote {airlines_path} ({len(airlines)} airlines)")

    if "weather" in args.parts:
        weather = build_weather(args.year)
        weather_path = args.outdir / "weather.csv.gz"
        weather.to_csv(weather_path, index=False, compression="gzip")
        size_kb = weather_path.stat().st_size / 1024
        log(f"Wrote {weather_path} ({len(weather):,} rows, {size_kb:.0f} KB)")

    if "airports" in args.parts:
        # The airport table lists only the airports the flights actually use, so
        # it needs the flight data. When flights were not rebuilt in this run,
        # the codes come from the file built by a previous one.
        if flights is not None:
            codes = set(flights["origin"].dropna()) | set(flights["dest"].dropna())
        elif flights_path.exists():
            codes = airport_codes_from_file(flights_path)
        else:
            raise SystemExit(
                f"{flights_path} does not exist, so there is no list of airports to "
                "look up. Build the flights file first, or pass --parts flights airports."
            )

        airports = build_airports(codes)
        airports_path = args.outdir / "airports.csv"
        airports.to_csv(airports_path, index=False)
        size_kb = airports_path.stat().st_size / 1024
        log(f"Wrote {airports_path} ({len(airports)} airports, {size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
