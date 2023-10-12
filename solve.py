# request reference from
# https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Process/Examples/S1GRD.html#s1grd-orthorectified-decibel-gamma0-rgb-composite-of-vv-vh-vvvh10-between--20-db-and-0-db-png
# STAC standard from
# https://github.com/radiantearth/stac-spec/tree/master/item-spec

import my_token
import subprocess
from osgeo import gdal


class STACItem:
    def __init__(self, evalscript, bounding_box, time_range, url, request,
                 COG_path, RGB_paths, true_color_path, overview_path, thumbnail_path):
        # STAC item properties
        self.stac_version = "1.0.0"
        self.id = "your-asset-id"
        self.type = "Feature"
        self.properties = {
            "evalscript": evalscript,
            "bounding_box": bounding_box,
            "time_range": time_range,
            # Add other properties as needed
        }
        self.geometry = None  # You can set the geometry if needed
        self.links = None  # You can set links if needed

        # STAC item assets
        self.assets = {
            "request": {
                "href": url,
                "method": "POST",
                "headers": {
                    "Accept": "image/tiff",
                },
                "body": request,
            },
            "COG": {
                "href": COG_path,
                "type": "image/tiff",
            },
            "true_color":{
                "href": true_color_path,
                "type": "image/tiff",
            },
            "overview":{
                "href": overview_path,
                "type": "image/webp",
            },
            "thumbnail": {
                "href": thumbnail_path,
                "type": "image/webp",
            }

        }

        for i, image_path in enumerate(RGB_paths, start=1):
            asset_name = f"band_{i}"
            self.assets[asset_name] = {
                "href": image_path,
                "type": "image/tiff",
            }



    def to_dict(self):
        # Convert the STACItem object to a dictionary
        stac_dict = {
            "type": self.type,
            "stac_version": self.stac_version,
            "id": self.id,
            "properties": self.properties,
            "assets": self.assets,
        }
        if self.geometry:
            stac_dict["geometry"] = self.geometry
        if self.links:
            stac_dict["links"] = self.links
        return stac_dict

# High resolution images are presented for viewing as COG
def get_COG(request, url):
    response = my_token.oauth.post(url, json=request)
    if response.status_code == 200:
        # If the request was successful, save the response as a TIFF file
        with open("my_data.tif", "wb") as tiff_file:
            tiff_file.write(response.content)

        store_path = "COG/sentinel1_data_cog.tif"
        # Convert the TIFF to COG using GDAL
        subprocess.run(["gdal_translate", "my_data.tif", store_path, "-of", "COG"])
        #subprocess.run(["gdal_translate", "sentinel1_RGB.tif", "sentinel1_RGB_cog.tif", "-of", "COG"])

        print("Sentinel-1 data downloaded and saved as sentinel1_data_cog.tif (COG format)")
        return store_path

    else:
        print(f"Request failed with status code {response.status_code}:")
        print(response.text)
        return None

# If an image contains pixels where no data were captured, these are rendered transparent
def no_data_transparent(path):

    dataset = gdal.Open(path)
    new_path = "COG/sentinel1_data_cog_transparent.tif"
    output_dataset = gdal.GetDriverByName("GTiff").CreateCopy(new_path, dataset)
    output_dataset.GetRasterBand(1).SetNoDataValue(0)  # Adjust to your specific no-data value

    dataset = None
    output_dataset = None
    return new_path

# For multi spectral data
def get_RGB(path):
    # Path to the multi-spectral dataset
    #multi_spectral_path = "sentinel1_RGB_cog.tif"  # Replace with your dataset

    # Open the multi-spectral dataset
    multi_spectral_dataset = gdal.Open(path, gdal.GA_ReadOnly)
    path_list = []
    if multi_spectral_dataset is not None:
        # Loop through the bands

        for band_index in range(1, multi_spectral_dataset.RasterCount + 1):
            # Get the band
            band = multi_spectral_dataset.GetRasterBand(band_index)

            # Read the band data
            band_data = band.ReadAsArray()

            # Save the individual band as a single-channel high-resolution image
            output_path = f"bands/band_{band_index}.tif"
            path_list.append(output_path)
            driver = gdal.GetDriverByName("GTiff")
            output_dataset = driver.Create(output_path, band.XSize, band.YSize, 1, band.DataType)
            output_dataset.GetRasterBand(1).WriteArray(band_data)

            output_dataset = None


        true_color_image_path = "true_color/true_color_image.tif"
        cmd = ["gdal_merge.py", "-o", true_color_image_path, "-separate"] + path_list
        subprocess.run(cmd)

        return path_list, true_color_image_path

    else:
        print("Failed to open the multi-spectral dataset.")
        return None

# An overview image is given, in webp format, no more than 500 kB in size
def create_webp_overview(input_tiff_path):

    input_dataset = gdal.Open(input_tiff_path, gdal.GA_ReadOnly)
    #input_dataset.BuildOverviews("NEAREST", [2, 4, 8])
    output_path = 'overview/overview.webp'
    output_dataset = gdal.GetDriverByName("WebP").CreateCopy(output_path, input_dataset)

    # Set WebP compression options to target a specific file size (e.g., 500 KB)
    compression_options = ["-size", "500k"]
    output_dataset.SetMetadata({"COMPRESS": "WEBP", "WEBP_OPTIONS": " ".join(compression_options)})

    return output_path

# A thumbnail is given, in webp format, no more than 500 px wide or high
def create_webp_thumbnail(input_tiff_path):

    input_dataset = gdal.Open(input_tiff_path, gdal.GA_ReadOnly)
    output_path = 'thumbnail/thumbnail.webp'
    gdal.Translate(
        output_path,
        input_dataset,
        format="WEBP",
        width=500,  # Maximum width (adjust as needed)
        height=500,  # Maximum height (adjust as needed)
    )

    return output_path


evalscript = """
//VERSION=3
function setup() {
  return {
    input: ["VV", "VH"],
    output: { id: "default", bands: 3 },
  }
}

function evaluatePixel(samples) {
  var vvdB = toDb(samples.VV)
  var vhdB = toDb(samples.VH)
  return [vvdB, vhdB, vvdB / vhdB / 10]
}

// displays VV in decibels from -20 to 0

function toDb(linear) {
  // the following commented out lines are simplified below
  // var log = 10 * Math.log(linear) / Math.LN10
  // var val = Math.max(0, (log + 20) / 20)
  return Math.max(0, Math.log(linear) * 0.21714724095 + 1)
}
"""

request = {
    "input": {
        "bounds": {
            "bbox": [
                1360000,
                5121900,
                1370000,
                5131900,
            ],
            "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/3857"},
        },
        "data": [
            {
                "type": "sentinel-1-grd",
                "dataFilter": {
                    "timeRange": {
                        "from": "2019-02-02T00:00:00Z",
                        "to": "2019-04-02T23:59:59Z",
                    }
                },
                "processing": {"orthorectify": "true"},
            }
        ],
    },
    "output": {
        "width": 512,
        "height": 512,
        "responses": [
            {
                "identifier": "default",
                "format": {"type": "image/png"},
            }
        ],
    },
    "evalscript": evalscript,
}
url = "https://sh.dataspace.copernicus.eu/api/v1/process"
COG_path = get_COG(request, url)
COG_transparent_path = no_data_transparent(COG_path)
thumbnail_path = create_webp_thumbnail(COG_transparent_path)
overview_path = create_webp_overview(COG_transparent_path)
RGB_path_list, true_color_path = get_RGB(COG_transparent_path)


# Create a STACItem object
stac_item = STACItem(
    evalscript=evalscript,
    bounding_box=request['input']['bounds']['bbox'],
    time_range={
        "start_datetime": request['input']['data'][0]['dataFilter']['timeRange']['from'],
        "end_datetime": request['input']['data'][0]['dataFilter']['timeRange']['to'],
    },
    url=url,
    request=request,
    COG_path=COG_path,
    RGB_paths=RGB_path_list,
    true_color_path = true_color_path,  # Path to the saved image
    overview_path = overview_path,
    thumbnail_path = thumbnail_path
)

