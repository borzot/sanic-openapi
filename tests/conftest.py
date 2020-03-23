import pytest
from sanic import Sanic

import sanic_openapi


@pytest.fixture()
def app():
    app = Sanic("test")
    app.blueprint(sanic_openapi.swagger_blueprint)
    yield app

    # Clean up | can't check definitions field cause of clean up
    #sanic_openapi.swagger.definitions = {}