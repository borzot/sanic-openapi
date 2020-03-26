import pytest
from sanic import Sanic

import sanic_openapi


@pytest.fixture()
def app():
    app = Sanic("test")
    app.blueprint(sanic_openapi.swagger_blueprint)
    yield app
