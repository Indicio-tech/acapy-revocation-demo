#!/usr/bin/env python
"""Process swagger"""

import json
import os
from typing import Dict, List, Union
import yaml


with open(os.environ.get("SWAGGER_JSON", "/tmp/swagger.json")) as in_file:
    swagger = json.load(in_file)


def walk(value: Union[List, Dict, int, str]):
    if isinstance(value, list):
        for item in value:
            walk(item)
        return
    if isinstance(value, dict):
        if "200" in value:
            if "description" not in value["200"] or not value["200"]["description"]:
                value["200"]["description"] = ""
        if "201" in value:
            if "description" not in value["201"] or not value["201"]["description"]:
                value["201"]["description"] = ""
        for item in value.values():
            walk(item)
        return


walk(swagger)

for tag in swagger["tags"]:
    if "externalDocs" not in tag:
        tag["externalDocs"] = {}
    if tag["externalDocs"] and "url" not in tag["externalDocs"]:
        tag["externalDocs"]["url"] = ""

print(yaml.dump(swagger))
