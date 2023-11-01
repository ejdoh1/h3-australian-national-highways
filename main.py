"""Main script to run the shapefile to H3 converter."""

from shapefile_to_h3_converter import InputParams, ShapefileToH3Converter

if __name__ == "__main__":
    input_params = InputParams(
        shapefile_filepath="data_in/National Highways.shp",
        output_filepath_geojson="data_out/highways.geojson",
        output_filepath_geojson_segmentized="data_out/highways_segmentized.geojson",
        output_filepath_h3_hexagons="data_out/h3_hexagons.csv",
        h3_resolution=8,
    )
    converter = ShapefileToH3Converter(input_params)
    converter.write_coordinates_to_file(
        converter.coordinates, "data_out/coordinates.csv"
    )
    converter.write_coordinates_to_file(
        converter.coordinates_segmentized, "data_out/coordinates_segmentized.csv"
    )
    converter.convert()
