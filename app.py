from litestar import Controller, Litestar, Response
from litestar.handlers import get
from litestar.openapi.config import OpenAPIConfig
from litestar.openapi.plugins import SwaggerRenderPlugin


class GeneralController(Controller):
    path = '/'

    @get('/hello')
    async def say_hello(self) -> Response:
        return Response(content={'message': 'Hello !'})


app = Litestar(
    route_handlers=[
        GeneralController,
    ],
    openapi_config=OpenAPIConfig(
        title='CodeBrachio',
        description='CodeBrachio',
        version='0.0.1',
        render_plugins=[SwaggerRenderPlugin()],
    ),
)
