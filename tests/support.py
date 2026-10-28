"""Load selected production definitions without installing Home Assistant."""
from __future__ import annotations

import ast
import asyncio
import logging
import math
import sys
from types import ModuleType
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from unicodedata import category

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "pcs_ghl"


def load_definitions(filename, names, namespace):
    """Compile definitions from the checked-out production file, never copies."""
    path = COMPONENT / filename
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.name in names
    ]
    found = {node.name for node in nodes}
    if found != set(names):
        raise AssertionError(f"Missing production definitions in {filename}: {set(names) - found}")
    future = ast.ImportFrom(
        module="__future__", names=[ast.alias(name="annotations")], level=0
    )
    module = ast.fix_missing_locations(ast.Module(body=[future, *nodes], type_ignores=[]))
    exec(compile(module, str(path), "exec"), namespace)


def production_namespace():
    """Provide standard dependencies; HA-dependent integration setup stays isolated."""
    module = ModuleType(f"ghl_regression_target_{len(sys.modules)}")
    sys.modules[module.__name__] = module
    namespace = module.__dict__
    namespace.update({
        "CONF_HOST": "host",
        "asyncio": asyncio,
        "math": math,
        "_LOGGER": logging.getLogger("ghl-regression"),
        "perf_counter": perf_counter,
        "category": category,
        "dataclass": dataclass,
        "field": field,
        "datetime": datetime,
        "timedelta": timedelta,
        "timezone": timezone,
        "defaultdict": defaultdict,
        "DeviceInfo": lambda **kwargs: kwargs,
    })
    const = COMPONENT / "const.py"
    exec(compile(const.read_bytes(), str(const), "exec"), namespace)
    load_definitions(
        "functions.py",
        {"has_control_characters", "is_valid_description", "parse_pointcount", "device_info"},
        namespace,
    )
    load_definitions(
        "api.py", {"GHLAPIError", "GHLConnectionError", "GHLCommandUncertainError", "GHLAPI"},
        namespace,
    )
    return namespace
