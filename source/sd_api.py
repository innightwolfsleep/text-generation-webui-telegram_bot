import json
import requests
import os
import io
import random
import base64
from PIL import Image, PngImagePlugin


class SdApi:
    def __init__(self, url="", sd_config_file_path=""):
        if url.startswith("http"):
            self.url = url
        else:
            self.url = "http://127.0.0.1:7860"
        if os.path.exists(sd_config_file_path):
            with open(sd_config_file_path, "r") as sd_config_file:
                self.payload = json.loads(sd_config_file.read())
        else:
            self.payload = {"prompt": "", "steps": 15}

    def txt_to_image(self, prompt: str):
        payload = self.payload.copy()
        payload["prompt"] = prompt
        response = requests.post(url=f"{self.url}/sdapi/v1/txt2img", json=payload)

        response_json = response.json()

        output_files = []
        for i in response_json["images"]:
            image = Image.open(io.BytesIO(base64.b64decode(i.split(",", 1)[0])))

            png_payload = {"image": "data:image/png;base64," + i}
            response2 = requests.post(url=f"{self.url}/sdapi/v1/png-info", json=png_payload)
            output_file = str(random.random()) + ".png"
            png_info = PngImagePlugin.PngInfo()
            png_info.add_text("parameters", response2.json().get("info"))
            image.save(output_file, pnginfo=png_info)
            output_files.append(output_file)
        return output_files
