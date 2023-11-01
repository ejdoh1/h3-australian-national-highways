"""Converts a shapefile to H3 hexagons."""

from enum import Enum
from typing import List, Union
import geopandas
from pydantic import BaseModel, Field, RootModel
from shapely.geometry import LineString
import h3


class InputParams(BaseModel):
    """Input parameters."""

    shapefile_filepath: str = Field(
        ..., description="Path to the shapefile containing the highways.", min_length=1
    )
    output_filepath_geojson: str = Field(
        ..., description="Path to the output file.", min_length=1
    )
    output_filepath_geojson_segmentized: str = Field(
        ..., description="Path to the output file.", min_length=1
    )
    h3_resolution: int = Field(..., description="H3 resolution.", ge=0, le=15)
    output_filepath_h3_hexagons: str = Field(
        ..., description="Path to the output file.", min_length=1
    )


class PropertyClass(str, Enum):
    """Property class."""

    principal_road = "Principal Road"
    dual_carriageway = "Dual Carriageway"


class FeatureGeometryType(str, Enum):
    """Feature geometry type."""

    LineString = "LineString"


class Properties(BaseModel):
    """GeoJSON properties."""

    id_t1: float
    road_name: str
    class_: Union[PropertyClass, None] = Field(
        ..., alias="class", description="Class of the road."
    )
    nrn: Union[str, None]


# coordinate class
class Coordinate(RootModel):
    """GeoJSON coordinate."""

    root: List[float] = Field(..., min_length=2, max_length=2, min=0, max=180)


class Geometry(BaseModel):
    """GeoJSON geometry."""

    type: FeatureGeometryType
    coordinates: List[Coordinate] = Field(
        ..., description="Coordinates of the road.", min_length=1
    )


class Feature(BaseModel):
    """GeoJSON feature."""

    id: str
    type: str
    properties: Properties
    geometry: Geometry


class CrsProperties(BaseModel):
    """Coordinate reference system properties."""

    name: str


class Crs(BaseModel):
    """Coordinate reference system."""

    type: str
    properties: CrsProperties


class GeoJsonModel(BaseModel):
    """GeoJSON model."""

    type: str
    features: List[Feature]
    crs: Crs


class ShapefileToH3Converter:
    """Converts a shapefile to H3 hexagons."""

    _input: InputParams
    _shapefile_data: geopandas.GeoDataFrame
    _geojson_data: GeoJsonModel
    _coordinates: List[Coordinate]
    _coordinates_segmentized: List[Coordinate]
    _h3_hexagons: List[str]

    def __init__(self, input_params: InputParams) -> None:
        self._input = input_params
        self._shapefile_data = geopandas.read_file(input_params.shapefile_filepath)
        self._geojson_data = GeoJsonModel.model_validate_json(
            self._shapefile_data.to_json()
        )
        self._coordinates = self._extract_coordinates(data=self._geojson_data)

        # write data to file
        with open(input_params.output_filepath_geojson, "w", encoding="utf-8") as f:
            f.write(self._geojson_data.model_dump_json())

        segmentized_geojson_data = self.segmentize_geojson_data(self._geojson_data)
        self._coordinates_segmentized = self._extract_coordinates(
            data=segmentized_geojson_data
        )

        with open(
            input_params.output_filepath_geojson_segmentized, "w", encoding="utf-8"
        ) as f:
            f.write(segmentized_geojson_data.model_dump_json())

        self._h3_hexagons = self._coordinates_to_h3_hexagons(
            coordinates=self._coordinates_segmentized,
            resolution=input_params.h3_resolution,
        )

    def segmentize_geojson_data(self, data: GeoJsonModel) -> GeoJsonModel:
        """Segmentizes the GeoJSON data."""
        print("segmentizing...")
        data_copy = data.model_copy()
        for feature in data_copy.features:
            if feature.geometry.type == FeatureGeometryType.LineString:
                coords = []
                for coordinate in feature.geometry.coordinates:
                    coords.append(coordinate.root)
                linestring = LineString(coords)
                # print(linestring)
                feature.geometry.coordinates = self.segmentize_linestring(
                    linestring=linestring
                )
        return data_copy

    def _extract_coordinates(self, data: GeoJsonModel) -> List[Coordinate]:
        """Extracts the coordinates from the GeoJSON data."""

        coordinates: List[Coordinate] = []
        for feature in data.features:
            for coordinate in feature.geometry.coordinates:
                coordinates.append(coordinate)
        return coordinates

    @property
    def coordinates(self) -> List[Coordinate]:
        """Returns the coordinates."""

        return self._coordinates

    @property
    def coordinates_segmentized(self) -> List[Coordinate]:
        """Returns the coordinates."""

        return self._coordinates_segmentized

    @property
    def h3_hexagons(self) -> List[str]:
        """Returns the H3 hexagons."""

        return self._h3_hexagons

    def write_h3_hexagons_to_file(self, filepath: str) -> None:
        """Writes the H3 hexagons to a file."""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("index,h3_hexagon\n")
            i = 0
            for h3_hexagon in self._h3_hexagons:
                f.write(f"{i},{h3_hexagon}\n")
                i += 1

    def write_coordinates_to_file(
        self, coordinates: List[Coordinate], filepath: str, decimals: int = 4
    ) -> None:
        """Writes the coordinates to a file."""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("index,latitude,longitude\n")
            i = 0
            for coordinate in coordinates:
                f.write(
                    f"{i},{round(coordinate.root[1],decimals)},{round(coordinate.root[0],decimals)}\n"
                )
                i += 1

    def segmentize_linestring(
        self, linestring: LineString, max_segment_length: float = 0.001
    ) -> List[Coordinate]:
        """Segmentizes a linestring."""
        s = geopandas.GeoSeries([linestring])
        segments = s.segmentize(max_segment_length=max_segment_length)
        # covert to list of coordinates
        coordinates = []
        for segment in segments:
            for point in segment.coords:
                coordinates.append(Coordinate(root=list(point)))
        return coordinates

    def convert(self) -> None:
        """Converts the shapefile to H3 hexagons."""

        print("converting...")
        self.write_h3_hexagons_to_file(self._input.output_filepath_h3_hexagons)

    def _coordinates_to_h3_hexagons(
        self, coordinates: List[Coordinate], resolution: int
    ) -> List[str]:
        """Converts the coordinates to H3 hexagons."""

        hexagons: List[str] = []
        for coordinate in coordinates:
            cell = h3.latlng_to_cell(
                coordinate.root[1],
                coordinate.root[0],
                resolution,
            )
            hexagons.append(cell)
            # append the neighbors
            neighbors = h3.grid_ring(cell, 1)
            hexagons.extend(neighbors)
        # deduplicate
        hexagons = list(set(hexagons))
        return hexagons
