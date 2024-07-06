from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from PIL import Image
import urllib.request
import os
import math
from io import BytesIO

app = FastAPI()

class GoogleMapDownloader:
    """
        A class which generates high resolution google maps images given
        a longitude, latitude and zoom level
    """

    def __init__(self, lat, lng, zoom=12):
        """
            GoogleMapDownloader Constructor

            Args:
                lat:    The latitude of the location required
                lng:    The longitude of the location required
                zoom:   The zoom level of the location required, ranges from 0 - 23
                        defaults to 12
        """
        self._lat = lat
        self._lng = lng
        self._zoom = zoom

    def getXY(self):
        """
            Generates an X,Y tile coordinate based on the latitude, longitude 
            and zoom level

            Returns:    An X,Y tile coordinate
        """
        
        tile_size = 256

        # Use a left shift to get the power of 2
        # i.e. a zoom level of 2 will have 2^2 = 4 tiles
        numTiles = 1 << self._zoom

        # Find the x_point given the longitude
        point_x = (tile_size / 2 + self._lng * tile_size / 360.0) * numTiles // tile_size

        # Convert the latitude to radians and take the sine
        sin_y = math.sin(self._lat * (math.pi / 180.0))

        # Calculate the y coordinate
        point_y = ((tile_size / 2) + 0.5 * math.log((1+sin_y)/(1-sin_y)) * -(tile_size / (2 * math.pi))) * numTiles // tile_size

        return int(point_x), int(point_y)

    def generateImage(self, **kwargs):
        """
            Generates an image by stitching a number of google map tiles together.
            
            Args:
                start_x:        The top-left x-tile coordinate
                start_y:        The top-left y-tile coordinate
                tile_width:     The number of tiles wide the image should be -
                                defaults to 5
                tile_height:    The number of tiles high the image should be -
                                defaults to 5
            Returns:
                A high-resolution Google Map image.
        """

        start_x = kwargs.get('start_x', None)
        start_y = kwargs.get('start_y', None)
        tile_width = kwargs.get('tile_width', 5)
        tile_height = kwargs.get('tile_height', 5)

        # Check that we have x and y tile coordinates
        if start_x is None or start_y is None:
            center_x, center_y = self.getXY()
            # Adjust start_x and start_y to center the coordinates
            start_x = center_x - tile_width // 2
            start_y = center_y - tile_height // 2

        # Determine the size of the image
        width, height = 256 * tile_width, 256 * tile_height

        # Create a new image of the size required
        map_img = Image.new('RGB', (width, height))

        for x in range(0, tile_width):
            for y in range(0, tile_height):
                url = 'https://mt0.google.com/vt?lyrs=s&x=' + str(start_x + x) + '&y=' + str(start_y + y) + '&z=' + str(self._zoom)

                current_tile = str(x) + '-' + str(y) + '.png'
                urllib.request.urlretrieve(url, current_tile)

                im = Image.open(current_tile)
                map_img.paste(im, (x * 256, y * 256))

                os.remove(current_tile)

        # Resize the final image to 1280x720
        map_img = map_img.resize((1280, 720), Image.Resampling.LANCZOS)

        return map_img

@app.get("/imagery")
def get_map(lat: float, lng: float, zoom: int = Query(12, ge=0, le=23)):
    try:
        gmd = GoogleMapDownloader(lat, lng, zoom)
        img = gmd.generateImage(tile_width=5, tile_height=3)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
