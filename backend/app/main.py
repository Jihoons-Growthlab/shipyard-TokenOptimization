from fastapi import FastAPI

from . import errors
from .routers import approvals, auth, common, dashboard, drawings, hulls, me, plans, progress, users

app = FastAPI(title="SWP Shipyard")
errors.install(app)
for module in (common, auth, me, hulls, plans, progress, drawings, approvals, users, dashboard):
    app.include_router(module.router)
