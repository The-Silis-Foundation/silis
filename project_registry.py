"""
project_registry.py
Centralized Project Registry for Silis ASIC Framework.
Bridges CLI and GUI project lifecycles so projects created or executed in either
environment are immediately visible, searchable, and manageable in the other.
"""

import os
import json
import time

REGISTRY_FILE = os.path.expanduser("~/.silis_recent.json")
MAX_RECENT = 25


def _normalize_project_path(path_or_file):
    """Returns absolute path to the project root directory."""
    if not path_or_file:
        return None
    abs_path = os.path.abspath(os.path.expanduser(str(path_or_file)))
    if os.path.isfile(abs_path):
        if abs_path.endswith(".silisproj"):
            return os.path.dirname(abs_path)
        # Check if parent contains silis.silisproj
        parent = os.path.dirname(abs_path)
        if os.path.isfile(os.path.join(parent, "silis.silisproj")):
            return parent
        return parent
    return abs_path


def register_project(path_or_file):
    """
    Registers a project directory in the global Silis registry (~/.silis_recent.json).
    Ensures the project is at index 0 (most recently used).
    Works interchangeably for both GUI and CLI invocations.
    """
    proj_dir = _normalize_project_path(path_or_file)
    if not proj_dir or not os.path.isdir(proj_dir):
        return False

    recent = []
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    recent = [os.path.abspath(os.path.expanduser(p)) for p in data if isinstance(p, str)]
        except Exception:
            recent = []

    # Remove if already present so it moves to front
    recent = [p for p in recent if os.path.abspath(p) != proj_dir]
    recent.insert(0, proj_dir)

    # Prune non-existent paths while keeping up to MAX_RECENT
    valid_recent = []
    for p in recent:
        if os.path.isdir(p) and p not in valid_recent:
            valid_recent.append(p)
            if len(valid_recent) >= MAX_RECENT:
                break

    try:
        tmp_file = f"{REGISTRY_FILE}.tmp.{os.getpid()}"
        with open(tmp_file, "w") as f:
            json.dump(valid_recent, f, indent=2)
        os.replace(tmp_file, REGISTRY_FILE)
        return True
    except Exception:
        try:
            with open(REGISTRY_FILE, "w") as f:
                json.dump(valid_recent, f, indent=2)
            return True
        except Exception:
            return False


def unregister_project(path_or_file):
    """Removes a project from the registry."""
    proj_dir = _normalize_project_path(path_or_file)
    if not proj_dir or not os.path.exists(REGISTRY_FILE):
        return False

    try:
        with open(REGISTRY_FILE, "r") as f:
            recent = json.load(f)
        recent = [p for p in recent if os.path.abspath(p) != proj_dir]
        with open(REGISTRY_FILE, "w") as f:
            json.dump(recent, f, indent=2)
        return True
    except Exception:
        return False


def get_registered_project_paths():
    """Returns list of existing project directory paths from the registry."""
    if not os.path.exists(REGISTRY_FILE):
        return []
    try:
        with open(REGISTRY_FILE, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [os.path.abspath(p) for p in data if isinstance(p, str) and os.path.isdir(p)]
    except Exception:
        pass
    return []


def get_registered_projects():
    """
    Returns list of rich project metadata dictionaries for all registered projects.
    Schema per item:
      {
        "name": str,
        "top": str,
        "pdk": str,
        "path": str,
        "proj_file": str,
        "macros": list,
        "has_netlist": bool,
        "has_def": bool,
        "mtime": float
      }
    """
    paths = get_registered_project_paths()
    projects = []
    for p in paths:
        proj_file = os.path.join(p, "silis.silisproj")
        name = os.path.basename(p)
        top = "top"
        pdk = "sky130"
        macros = []

        if os.path.isfile(proj_file):
            try:
                with open(proj_file, "r") as f:
                    cfg = json.load(f)
                name = cfg.get("project_name", name)
                top = cfg.get("top_module", top)
                pdk = cfg.get("pdk", pdk)
                macros = cfg.get("macros", [])
            except Exception:
                pass

        has_netlist = os.path.isfile(os.path.join(p, "netlist", f"{top}_netlist.v"))
        has_def = os.path.isfile(os.path.join(p, "results", "temp.def")) or os.path.isfile(os.path.join(p, "results", "final_routed.def"))

        try:
            mtime = os.path.getmtime(proj_file) if os.path.isfile(proj_file) else os.path.getmtime(p)
        except Exception:
            mtime = 0.0

        projects.append({
            "name": name,
            "top": top,
            "pdk": pdk,
            "path": p,
            "proj_file": proj_file if os.path.isfile(proj_file) else None,
            "macros": macros,
            "has_netlist": has_netlist,
            "has_def": has_def,
            "mtime": mtime
        })
    return projects


def find_registered_project(query):
    """
    Resolves a query (path, project name, or top module name) against the registry.
    Returns the absolute path to silis.silisproj or the project directory if found,
    or None if not found.
    """
    if not query:
        return None

    # 1. Exact path match
    norm = os.path.abspath(os.path.expanduser(query))
    if os.path.isfile(norm) and norm.endswith(".silisproj"):
        register_project(norm)
        return norm
    if os.path.isdir(norm):
        cand = os.path.join(norm, "silis.silisproj")
        if os.path.isfile(cand):
            register_project(norm)
            return cand

    # 2. Check registered projects by name / directory / top module
    q = query.strip().lower()
    for proj in get_registered_projects():
        p_name = proj["name"].lower()
        p_top = proj["top"].lower()
        p_base = os.path.basename(proj["path"]).lower()
        if q in [p_name, p_top, p_base]:
            if proj["proj_file"] and os.path.isfile(proj["proj_file"]):
                register_project(proj["path"])
                return proj["proj_file"]
            elif os.path.isdir(proj["path"]):
                register_project(proj["path"])
                return proj["path"]

    return None


def get_most_recent_project():
    """Returns the most recently registered project or None."""
    projs = get_registered_projects()
    if projs:
        return projs[0]
    return None
