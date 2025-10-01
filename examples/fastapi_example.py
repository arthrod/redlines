"""Example FastAPI application exposing the Redlines API routes.

Run with:
    uvicorn examples.fastapi_example:app --reload
"""

from fastapi import FastAPI

from redlines.api import RedlinesAPI

api = RedlinesAPI()
app: FastAPI = api.create_app()
