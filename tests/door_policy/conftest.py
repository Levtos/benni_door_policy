"""Lädt die HA-freien Dateien (const.py, policy.py) als synthetisches Paket.

policy.py nutzt ``from .const import ...``; über das synthetische Paket
``bdp_pure_pkg`` löst das auf die geladene const.py auf — so laufen die
Pure-Logic-Tests ohne installiertes Home Assistant.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PKG_DIR = os.path.join(ROOT, "custom_components", "benni_door_policy")

pkg_name = "bdp_pure_pkg"
pkg = types.ModuleType(pkg_name)
pkg.__path__ = [PKG_DIR]
sys.modules[pkg_name] = pkg


def _load(modname: str, filename: str):
    spec = importlib.util.spec_from_file_location(
        f"{pkg_name}.{modname}", os.path.join(PKG_DIR, filename)
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"{pkg_name}.{modname}"] = mod
    spec.loader.exec_module(mod)
    return mod


const = _load("const", "const.py")
policy = _load("policy", "policy.py")

sys.modules["bdp_const"] = const
sys.modules["bdp_policy"] = policy
