from __future__ import annotations

import configparser
import dataclasses
import datetime
import json
import os
import sqlite3
import typing
import zlib

import requests

config = configparser.ConfigParser()
config.read("config.ini")

APP_ID = config["here"]["app_id"]
APP_CODE = config["here"]["app_code"]

T_SubdivisionID = typing.List[int]


@dataclasses.dataclass
class Rectangle:
    """ Data class for storing a rectangle and related functions. """

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def to_tuple(self) -> typing.Tuple[float, float, float, float]:
        """ Convert the Rectangle into a tuple of floats in standard GIS format.

        Returns: A tuple of floats.
        """

        return self.min_x, self.min_y, self.max_x, self.max_y

    def subdivide(self,
                  rows: int,
                  columns: typing.Optional[int] = None
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

        return subdivisions


class HerePlaces:
    BASE_URL = "https://places.api.here.com/places/v1/"
    BROWSE_ENDPOINT = "%s/browse" % BASE_URL

    def __init__(self, app_id: str, app_code: str):
        """ Initialize HerePlaces object.

        Args:
            app_id: The HERE APP ID to use for the Places API.
            app_code: The HERE APP code to use for the Places API.
        """

        self.app_id = app_id
        self.app_code = app_code
        self.default_params = {
            "app_id": self.app_id,
            "app_code": self.app_code
        }

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
            **self.default_params,
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


class HerePlacesScraper:
    """ Scraper for HERE places API. """

    def __init__(self, db_path: str, app_id: str, app_code: str):
        """ Initialize a new Scraper object.

        Args:
            db_path: The path to an SQLite3 database that will store the scraped
                data. A new one will be created if it does not exist.
            app_id: The HERE APP ID to use for the Places API.
            app_code: The HERE APP code to use for the Places API.
        """

        self.db_path = db_path
        self.here = HerePlaces(app_id, app_code)

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

        for i, subdivision in enumerate(rect.subdivide(3)):
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
                print(message, end = "\n\n")

                if len(places) > 90:
                    self.scrape(subdivision, skip_to, new_id)

            # skipping functionality part 2
            else:
                print("skipped")
                if skip_to_cropped == new_id:
                    self.scrape(subdivision, skip_to, new_id)


# %%

scraper = HerePlacesScraper("harvard_longwood.db", APP_ID, APP_CODE)

#%%
scraper.scrape(Rectangle(-71.1054416355,42.3346006792,-71.1001952347,42.3393749713))

# %%

list(scraper.iter_places())
