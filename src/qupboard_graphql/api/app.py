"""
FastAPI application factory for qupboard_graphql.

Assembles the REST router, GraphQL router, and root/health-check router into
a single FastAPI application.  A custom OpenAPI schema is injected so that the
GraphQL endpoint appears correctly in the generated docs.
"""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from qupboard_graphql.api.graphql import graphql_router
from qupboard_graphql.api.rest import rest_router
from qupboard_graphql.api.root import root_router
from qupboard_graphql.config import settings


def _custom_openapi(app: FastAPI) -> dict:
    """Build and cache a custom OpenAPI schema that includes the GraphQL endpoint.

    The GraphQL endpoint is not automatically discovered by FastAPI's OpenAPI
    generator, so it is injected manually under ``settings.GRAPHQL_PATH``.

    Args:
        app: The FastAPI application whose schema is being constructed.

    Returns:
        The OpenAPI schema dictionary, cached on ``app.openapi_schema`` after
        the first call.
    """
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    schema.setdefault("paths", {})[settings.GRAPHQL_PATH] = {
        "get": {
            "tags": ["GraphQL"],
            "summary": "GraphQL API",
            "description": (
                "This API exposes a GraphQL endpoint. "
                f"Use the interactive GraphiQL IDE at "
                f"[`{settings.GRAPHQL_PATH}`]({settings.GRAPHQL_PATH}) "
                f"to explore and test queries."
            ),
            "responses": {"200": {"description": "Opens the GraphiQL interactive query editor."}},
        }
    }
    app.openapi_schema = schema
    return schema


def get_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Registers all routers (root, REST, GraphQL) and installs the custom
    OpenAPI schema builder.

    Returns:
        A fully-configured :class:`fastapi.FastAPI` application instance.
    """
    app = FastAPI()
    app.include_router(root_router, prefix="")
    app.include_router(rest_router, prefix=settings.REST_PATH)
    app.include_router(graphql_router, prefix=settings.GRAPHQL_PATH)
    app.openapi = lambda: _custom_openapi(app)
    return app
