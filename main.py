from __future__ import annotations

import csv
import dataclasses
import datetime
import json
import math
import sqlite3
import typing
import zlib

import haversine
import requests

T_SubdivisionID = typing.List[int]


@dataclasses.dataclass
class Rectangle:
    """ Data class for storing a rectangle and related functions. """

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def centroid(self) -> typing.Tuple[float, float]:
        """ Calculate the average x and y.

        Returns: A tuple containing the average x and y, as floats.
        """

        return (self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2

    def radius(self, unit: typing.Optional[haversine.Unit] = None):
        """ Calculate the maximum radius of this rectangle, calculated as the
        distance between the bottom left and top right corners.

        The default behaviour is to calculate the cartesian distance, but
        great-circle distances can also be calculated in standard units by
        providing the `unit` argument.

        Args:
            unit: If specified, output in these units, using the haversine
                formula to account for curvature.

        Returns: The maximum radius of this rectangle, as a float.
        """

        if unit is None:
            return math.sqrt(
                (self.max_x - self.min_x)**2 +
                (self.max_y - self.min_y)**2
            )
        else:
            return haversine.haversine(
                (self.min_x, self.min_y),
                (self.max_x, self.max_y),
                unit
            )

    def to_tuple(self) -> typing.Tuple[float, float, float, float]:
        """ Convert the Rectangle into a tuple of floats in standard GIS format.

        Returns: A tuple of floats.
        """

        return self.min_x, self.min_y, self.max_x, self.max_y

    def subdivide(self,
                  rows: int,
                  columns: typing.Optional[int] = None,
                  max_radius: typing.Optional[float] = None,
                  max_radius_units: typing.Optional[haversine.Unit] = None
                  ) -> typing.List[Rectangle]:
        """ Subdivide this Rectangle into a list of smaller rectangles, each of
        equal size.

        Args:
            rows: The number of rows to subdivide this Rectangle into.
            columns: The number of columns to subdivide this Rectangle into. If
                blank, uses the number of rows.

        Returns: A list of smaller Rectangle objects.
        """

        if columns is None:
            columns = rows

        rect_width = self.max_x - self.min_x
        rect_height = self.max_y - self.min_y
        subdivisions = []

        for n in range(rows * columns):
            subdivision_width = rect_width / columns
            subdivision_height = rect_height / rows
            subdivision_row = int(n / columns)
            subdivision_column = n % columns
            subdivisions.append(Rectangle(
                self.min_x + subdivision_width * subdivision_column,
                self.min_y + subdivision_height * subdivision_row,
                self.min_x + subdivision_width * (subdivision_column + 1),
                self.min_y + subdivision_height * (subdivision_row + 1)
            ))

        if max_radius and (subdivisions[0].radius(max_radius_units) > max_radius):
            subdivisions = [
                new_subdivision
                for subdivision in subdivisions
                for new_subdivision in subdivision.subdivide(
                    rows, columns, max_radius, max_radius_units
                )
            ]

        return subdivisions


class HerePlacesV1:
    """ **DEPRECATED**: Class providing access to the HERE Places API v1.

    Use of the v1 API has been deprecated by HERE; see HerePlaces for the v7
    API.
    """

    BASE_URL = "https://places.api.here.com/places/v1/"
    BROWSE_ENDPOINT = "{}/browse".format(BASE_URL)

    def __init__(self, app_id: str, app_code: str):
        """ Initialize HerePlacesV1 object.

        Args:
            app_id: The HERE APP ID to use for the Places API.
            app_code: The HERE APP code to use for the Places API.
        """

        self.app_id = app_id
        self.app_code = app_code

    def browse(self,
               in_: Rectangle,
               size: int = 100,
               cat: typing.Optional[typing.Union[str, typing.List[str]]] = None
               ) -> typing.Optional[typing.List[dict]]:
        """ Browse for places in a given area.

        Args:
            in_: The area to search in. The HERE API takes either a circle and
                radius or a rectangle; currently, only rectangular queries are
                supported.
            size: The maximum number of places to be returned.
            cat: A category or list of categories to restrict the search to. For
                a list of categories, see:
                https://developer.here.com/documentation/places/dev_guide/topics/categories.html

        Returns: A list of HERE places if the request was successful; otherwise,
            None. Each place is a dict.
        """

        params = {
            "app_id": self.app_id,
            "app_code": self.app_code,
            "in": "{},{},{},{}".format(*in_.to_tuple()),
            "size": size
        }

        if cat is not None:
            if type(cat) is str:
                params.update({"cat": cat})
            else:
                params.update({"cat": ",".join(cat)})

        response = requests.get(self.BROWSE_ENDPOINT, params=params)
        if response.status_code == 200:
            return response.json()["results"]["items"]


class HerePlacesV7:
    """ Class providing access to the HERE Geocoding & Search API v7. """

    BROWSE_ENDPOINT = "https://browse.search.hereapi.com/v1/browse"

    def __init__(self, api_key: str):
        """ Initialize HerePlacesV7 object.

        Args:
            api_key: The HERE API key to use for the Geocoding & Search API.
        """

        self.api_key = api_key

    def browse(self,
               rect: Rectangle,
               limit: int = 100,
               cat: typing.Optional[typing.Union[str, typing.List[str]]] = None
               ) -> typing.Optional[typing.List[dict]]:
        """ Browse for places in a given area.

        Args:
            in_: The area to search in. The HERE API takes either a circle and
                radius or a rectangle; currently, only rectangular queries are
                supported.
            size: The maximum number of places to be returned.
            cat: A category or list of categories to restrict the search to. For
                a list of categories, see:
                https://developer.here.com/documentation/places/dev_guide/topics/categories.html

        Returns: A list of HERE places if the request was successful; otherwise,
            None. Each place is a dict.
        """

        centroid = rect.centroid
        params = {
            "apiKey": self.api_key,
            "at": "{},{}".format(centroid[1], centroid[0]),
            "in": "bbox:{},{},{},{}".format(*rect.to_tuple()),
            "limit": limit
        }

        if cat is not None:
            if type(cat) is str:
                params.update({"cat": cat})
            else:
                params.update({"cat": ",".join(cat)})

        response = requests.get(self.BROWSE_ENDPOINT, params=params)
        if response.status_code == 200:
            return response.json()["items"]

#%%

class HerePlacesScraper:
    """ Scraper for HERE places API. """

    # HERE places a 250km max limit on the Browse endpoint. see:
    # https://developer.here.com/documentation/geocoding-search-api/dev_guide/topics/endpoint-browse-brief.html
    # to be safe, we will limit this further to only 240km
    MAX_RADIUS_KM = 240

    # max number of categories to export in CSV
    MAX_CATEGORIES = 5

    def __init__(self,
                 db_path: str,
                 api_key: typing.Optional[str] = None,
                 app_id: typing.Optional[str] = None,
                 app_code: typing.Optional[str] = None):
        """ Initialize a new Scraper object.

        Args:
            db_path: The path to an SQLite3 database that will store the scraped
                data. A new one will be created if it does not exist.
            app_id: The HERE APP ID to use for the Places API.
            app_code: The HERE APP code to use for the Places API.
            api_key: The HERE API key to use for the Geocoding & Search API.
        """

        self.db_path = db_path

        if app_id and app_code:
            self.here = HerePlacesV1(app_id, app_code)
        elif api_key:
            self.here = HerePlacesV7(api_key)
        else:
            print("WARNING: no authentication provided; scraping not possible")
            self.here = None

        self.n_requests_made = 0
        self.n_places_encountered = 0
        self.n_total_new_places = 0

        self.db = sqlite3.connect(db_path)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS places(
                place_id TEXT,
                data BLOB,
                UNIQUE(place_id)
            )
        """)

    def insert_places(self,
                      places: typing.List[dict],
                      scraped_datetime: typing.Optional[datetime.datetime] = None
                      ) -> int:
        """ Insert HERE places into the database.

        Only new places are inserted, as per the UNIQUE constraint placed on
        the place ID.

        Args:
            places: A list of HERE places. Each HERE place should be a dict.
            scraped_datetime: The time that these places were retrieved.

        Returns: The number of new places that were inserted into the database.
        """

        n_inserted = 0
        if scraped_datetime is not None:
            scraped_datetime = scraped_datetime.timestamp()

        with self.db:
            for place in places:
                place["scraped"] = scraped_datetime
                try:
                    self.db.execute(
                        "INSERT INTO places(place_id, data) VALUES(?, ?)",
                        (
                            place["id"],
                            zlib.compress(json.dumps(place).encode("utf-8"))
                        )
                    )
                    n_inserted += 1
                except sqlite3.IntegrityError:
                    pass

        return n_inserted

    def iter_places(self) -> typing.Generator[dict]:
        """ Iterate over saved places.

        Returns: A generator that yields HERE place data.
        """

        cursor = self.db.cursor()
        cursor.execute("SELECT place_id, data FROM places")
        for place in cursor:
            (place_id, data) = place
            yield json.loads(zlib.decompress(data))
        cursor.close()

    def write_ndjson(self, output_path: str):
        """  Write stored POI data to an NDJSON file.

        Args:
            output_path: The path to write data to.
        """

        with open(output_path, "w") as output_fp:
            for place in self.iter_places():
                output_fp.write(json.dumps(place, separators=(",", ":")))
                output_fp.write("\n")

    def write_csv(self, output_path: str):
        """  Write stored POI data to a CSV file.

        This will not contain all the data contained in places; only the data
        that seemed to be the most important / relevant / non-duplicative.

        Args:
            output_path: The path to write data to.
        """

        with open(output_path, "w") as output_fp:
            writer = csv.DictWriter(
                output_fp,
                fieldnames=[
                    "lon", "lat", "id", "title", "street", "houseNumber", "postalCode",
                ] + [
                    "category{}".format(i)
                    for i in range(1, self.MAX_CATEGORIES + 1)
                ]
            )
            writer.writeheader()
            for place in self.iter_places():
                print(place)
                row = {
                    "lon": place["position"]["lng"],
                    "lat": place["position"]["lat"],
                    "id": place["id"],
                    "street": place["address"].get("street"),
                    "houseNumber": place["address"].get("houseNumber"),
                    "postalCode": place["address"].get("postalCode")
                }
                for i, category in enumerate(place.get("categories", [])):
                    if i == self.MAX_CATEGORIES:
                        break
                    row["category{}".format(i + 1)] = category["id"]
                writer.writerow(row)

    def write_csv_v1(self, output_path: str):
        """  Write stored POI data to a CSV file.

        **DEPRECATED - intended for use with the v1 API only**

        This will not contain all the data contained in places; only the data
        that seemed to be the most important / relevant / non-duplicative.

        Args:
            output_path: The path to write data to.
        """

        with open(output_path, "w") as output_fp:
            writer = csv.DictWriter(
                output_fp,
                fieldnames=[
                    "lon", "lat", "id", "title", "category", "averageRating"
                ]
            )
            writer.writeheader()
            for place in self.iter_places():
                writer.writerow({
                    "lon": place["position"][1],
                    "lat": place["position"][0],
                    "id": place["id"],
                    "title": place["title"],
                    "category": place["category"]["id"],
                    "averageRating": place["averageRating"]
                })

    def scrape(self,
               rect: Rectangle,
               skip_to: typing.Optional[T_SubdivisionID] = None,
               _id: T_SubdivisionID = [],
               ):
        """ Scrape HERE places.

        Args:
            rect: The rectangle to scrape.
            skip_to: The recursion tree to skip to, if desired.
            _id: Do not use - this is a unique identifier of the current
                recursion tree.
        """

        # TODO: there's probably a better way to implement skipping
        # functionality - look into later

        if self.here is None:
            raise Exception("No app_id or app_code provided")

        subdivisions = rect.subdivide(
            rows=3, max_radius=self.MAX_RADIUS_KM,
            max_radius_units=haversine.Unit.KILOMETERS
        )

        for i, subdivision in enumerate(subdivisions):
            new_id = _id + [i]
            new_id_str = ",".join(map(str, new_id))

            # skipping functionality part 1
            if skip_to == _id:
                skip_to = None
            elif skip_to is not None:
                skip_to_cropped = skip_to[:len(new_id)]
                if skip_to_cropped < new_id:
                    skip_to = None

            if skip_to is None:
                request_time = datetime.datetime.now()
                places = self.here.browse(subdivision)
                n_new_places = self.insert_places(places, request_time)

                self.n_requests_made += 1
                self.n_places_encountered += len(places)
                self.n_total_new_places += n_new_places

                message = "\n".join([
                    "Subdivision ID: {}".format(new_id_str),
                    "Bounding box: {},{},{},{}".format(
                        *subdivision.to_tuple()
                    ),
                    "In this subdivision: found {} places ({} new)".format(len(places), n_new_places),
                    "Since scraping started: made {} requests; encountered {} places ({} new)".format(
                        self.n_requests_made, self.n_places_encountered, self.n_total_new_places
                    )
                ])
                print(message, end="\n\n")

                if len(places) > 90:
                    self.scrape(subdivision, skip_to, new_id)

            # skipping functionality part 2
            else:
                print("skipped")
                if skip_to_cropped == new_id:
                    self.scrape(subdivision, skip_to, new_id)


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help="Command", dest="command", required=True)

    parser.add_argument("-d", "--db", help="The path to the SQLite3 database where data will be stored", required=True)

    scrape_parser = subparsers.add_parser("scrape")
    scrape_parser.add_argument("-a", "--api-key", help="The HERE API key to use for authentication", required=True)
    scrape_parser.add_argument("-r", "--rectangle", help="The rectangle to scrape, in the format \"(min_lon,min_lat,max_lon,max_lat)\"", required=True)

    scrape_v1_parser = subparsers.add_parser("scrape_v1")
    scrape_v1_parser.add_argument("-a", "--app-id", help="The HERE app ID to use for authentication", required=True)
    scrape_v1_parser.add_argument("-A", "--app-code", help="The HERE app code to use for authentication", required=True)
    scrape_v1_parser.add_argument("-r", "--rectangle", help="The rectangle to scrape, in the format \"(min_lon,min_lat,max_lon,max_lat)\"", required=True)

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("-f", "--format", help="The format to export places in", choices=("csv", "json"), required=True)
    export_parser.add_argument("-o", "--output", help="The path to export places to", required=True)
    export_parser.add_argument("-v", "--version", help="The version of HERE places being exported", choices=("1", "7"), default="7")

    args = parser.parse_args()

    rectangle = Rectangle(*eval(args.rectangle))  # TODO: very hacky

    if args.command == "scrape":
        scraper = HerePlacesScraper(args.db, api_key=args.api_key)
        scraper.scrape(rectangle)

    elif args.command == "scrape_v1":
        scraper = HerePlacesScraper(args.db, app_id=args.app_id, app_code=args.app_code)
        scraper.scrape(rectangle)

    elif args.command == "export":
        scraper = HerePlacesScraper(args.db)
        if args.format == "csv":
            if args.version == "v1":
                scraper.write_csv_v1(args.output)
            else:
                scraper.write_csv(args.output)
        elif args.format == "json":
            scraper.write_ndjson(args.output)
        print("Exported stored data to {}".format(args.output))
