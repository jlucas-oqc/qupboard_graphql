#!/usr/bin/env python
"""
Entry point for running the qupboard_graphql service with Uvicorn.

Usage::

    python -m qupboard_graphql.main
    # or, if installed as a script:
    qupboard
"""

import uvicorn

from qupboard_graphql.api.app import get_app


def main():
    """Create the FastAPI application and serve it with Uvicorn.

    Binds to all interfaces (``0.0.0.0``) on port ``8000``.  To use a
    different host or port, call ``uvicorn`` directly::

        uvicorn qupboard_graphql.api.app:get_app --host 127.0.0.1 --port 9000 --factory
    """
    app = get_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
