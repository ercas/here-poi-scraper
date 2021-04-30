from __future__ import annotations

import configparser
import dataclasses
import typing

import requests

config = configparser.ConfigParser()
config.read("config.ini")

APP_ID = config["here"]["app_id"]
APP_CODE = config["here"]["app_code"]

@dataclasses.dataclass
class Rectangle:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def subdivide(self, rows, columns = None) -> typing.List[Rectangle]:
        if (columns is None):
            columns = rows

        rect_width = self.max_x - self.min_x
        rect_height = self.max_y - self.min_y
        subdivisions = []

        for n in range(rows * columns):
            subdivision_width = rect_width / columns
            subdivision_height = rect_height / rows
            subdivision_row = int(n / columns)
            subdivision_column = n % columns
            subdivisions.append([
                self.min_x + subdivision_width * subdivision_column,
                self.min_y + subdivision_height * subdivision_row,
                self.min_x + subdivision_width * (subdivision_column + 1),
                self.min_y + subdivision_height * (subdivision_row + 1)
            ])

        return subdivisions

class HerePlaces:

    BASE_URL = "https://places.api.here.com/places/v1/"
    BROWSE_ENDPOINT = "%s/browse" % BASE_URL

    def __init__(self, app_id, app_code):
        self.app_id = app_id
        self.app_code = app_code
        self.default_params = {
            "app_id": self.app_id,
            "app_code": self.app_code
        }

    def browse(self, in_, size = 100):
        response = requests.get(
            self.BROWSE_ENDPOINT,
            params = dict({
                "in": ",".join(map(str, in_)),
                "size": size,
            }, **self.default_params)
        )
        if (response.status_code == 200):
            return response.json()["results"]["items"]
