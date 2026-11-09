"""Hermie tab backend, mounted by the Hermes dashboard at /api/plugins/hermie/.

The dashboard imports this file on its own, outside the plugin package, so
the engine is loaded by path. Auth is the dashboard's job, not ours.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

try:
    from fastapi import APIRouter, Body, HTTPException
except Exception:  # lets the unit tests import this without dashboard deps
    class HTTPException(Exception):  # type: ignore[no-redef]
        def __init__(self, status_code, detail=""):
            super().__init__(detail)
            self.status_code, self.detail = status_code, detail

    def Body(default=None, **_kwargs):  # type: ignore[no-redef]
        return default

    class APIRouter:  # type: ignore[no-redef]
        def get(self, *_args, **_kwargs):
            return lambda fn: fn

        post = get

router = APIRouter()
_ENGINE_NAME = "hermie_dashboard_engine"


def _engine():
    module = sys.modules.get(_ENGINE_NAME)
    if module is None:
        path = Path(__file__).resolve().parent.parent / "hermie.py"
        spec = importlib.util.spec_from_file_location(_ENGINE_NAME, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[_ENGINE_NAME] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(_ENGINE_NAME, None)
            raise
    return module


@router.get("/pet")
def get_pet():
    return _engine().snapshot()


@router.post("/action")
def post_action(payload: dict = Body(...)):
    engine = _engine()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object")
    try:
        engine.interact(payload.get("action"), payload.get("name"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return engine.snapshot()
