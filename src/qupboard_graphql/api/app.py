from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from qupboard_graphql.api.graphql import graphql_router
from qupboard_graphql.api.rest import rest_router
from qupboard_graphql.api.root import root_router
from qupboard_graphql.config import settings
from qupboard_graphql.db.database import Base
from qupboard_graphql.db.session import get_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=get_engine())
    yield


def _custom_openapi(app: FastAPI) -> dict:
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


def get_app():
    app = FastAPI(lifespan=lifespan)
    app.include_router(root_router, prefix="")
    app.include_router(rest_router, prefix=settings.REST_PATH)
    app.include_router(graphql_router, prefix=settings.GRAPHQL_PATH)
    app.openapi = lambda: _custom_openapi(app)
    return app
