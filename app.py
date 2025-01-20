from litestar import Litestar
from litestar.openapi.config import OpenAPIConfig
from litestar.openapi.plugins import SwaggerRenderPlugin

from apps.codebrachio.controllers import GitHubController

app = Litestar(
    route_handlers=[
        GitHubController,
    ],
    openapi_config=OpenAPIConfig(
        title='CodeBrachio',
        description='CodeBrachio',
        version='0.0.1',
        render_plugins=[SwaggerRenderPlugin()],
    ),
)
