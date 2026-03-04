#!/usr/bin/env python

import uvicorn

from qupboard_graphql.api.app import get_app


def main():
    app = get_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
