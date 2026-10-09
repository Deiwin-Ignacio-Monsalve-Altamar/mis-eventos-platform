"""Configure interactive API documentation."""

from pathlib import Path

import yaml
from flasgger import Swagger


def init_swagger(app):
    """Load the OpenAPI specification and register Swagger UI."""
    specification_path = Path(__file__).with_name("openapi.yaml")

    with specification_path.open(encoding="utf-8") as specification_file:
        template = yaml.safe_load(specification_file)

    app.config["SWAGGER"] = {
        "openapi": "3.0.3",
        "uiversion": 3,
        "title": template["info"]["title"],
        "version": template["info"]["version"],
        "description": template["info"].get("description", ""),
    }

    Swagger(app, template=template)
