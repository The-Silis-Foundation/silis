"""
tb_detector.py
Multi-paradigm testbench and verification methodology sniffer for Silis EDA.
Inspects Python (.py), SystemVerilog (.sv, .v), and VHDL (.vhd, .vhdl) testbenches
to detect whether UVM, pyuvm/cocotb, OSVVM, or procedural testing is utilized,
and extracts the static hierarchy/topology.
"""

import os
import re
import ast
import glob

# Supported Methodology Tags
METH_PYUVM = "pyuvm"
METH_COCOTB = "cocotb"
METH_SV_UVM = "sv_uvm"
METH_OSVVM = "osvvm"
METH_UVVM = "uvvm"
METH_PROCEDURAL = "procedural"


class TestbenchDetector:
    """
    Scans project testbenches and returns the active verification methodology
    along with the component hierarchy tree.
    """

    @classmethod
    def detect_project(cls, project_root, project_config=None):
        """
        Scans project directory or explicit project_config tb_files.
        Returns a dict:
          {
            "methodology": METH_*,
            "tb_file": path,
            "top_component": name,
            "hierarchy": { ... tree structure ... }
          }
        """
        tb_files = []
        if project_config and project_config.get("tb_files"):
            for tf in project_config["tb_files"]:
                abs_tf = tf if os.path.isabs(tf) else os.path.join(project_root, tf)
                if os.path.exists(abs_tf):
                    tb_files.append(abs_tf)

        # Fallback discovery if not explicitly set in config
        if not tb_files:
            search_dirs = [
                os.path.join(project_root, "tb"),
                os.path.join(project_root, "rtl"),
                os.path.join(project_root, "source"),
                project_root
            ]
            for sdir in search_dirs:
                if os.path.exists(sdir):
                    if sdir == os.path.join(project_root, "tb"):
                        # In dedicated tb/ directory, all test source files are testbenches
                        for ext in ("*.v", "*.sv", "*.py", "*.vhd", "*.vhdl"):
                            tb_files += glob.glob(os.path.join(sdir, ext))
                    tb_files += glob.glob(os.path.join(sdir, "tb_*.v"))
                    tb_files += glob.glob(os.path.join(sdir, "*_tb.v"))
                    tb_files += glob.glob(os.path.join(sdir, "test_*.v"))
                    tb_files += glob.glob(os.path.join(sdir, "tb_*.sv"))
                    tb_files += glob.glob(os.path.join(sdir, "*_tb.sv"))
                    tb_files += glob.glob(os.path.join(sdir, "test_*.sv"))
                    tb_files += glob.glob(os.path.join(sdir, "tb_*.py"))
                    tb_files += glob.glob(os.path.join(sdir, "test_*.py"))
                    tb_files += glob.glob(os.path.join(sdir, "*_tb.py"))
                    tb_files += glob.glob(os.path.join(sdir, "tb_*.vhd"))
                    tb_files += glob.glob(os.path.join(sdir, "*_tb.vhd"))
                    tb_files += glob.glob(os.path.join(sdir, "test_*.vhd"))
                    tb_files += glob.glob(os.path.join(sdir, "tb_*.vhdl"))

        tb_files = list(set(tb_files))
        if not tb_files:
            return {
                "methodology": METH_PROCEDURAL,
                "tb_file": None,
                "top_component": None,
                "hierarchy": []
            }

        # Sort tb_files so actual test environments and testbenches are analyzed before interfaces/items
        def _tb_priority(f):
            b = os.path.basename(f).lower()
            if "_if" in b or "interface" in b or "_item" in b:
                return 10
            if "pkg" in b or "package" in b:
                return 8
            if "top" in b:
                return 1
            if "_tb" in b or "tb_" in b:
                return 2
            if "test" in b:
                return 3
            return 5
        sorted_tb_files = sorted(tb_files, key=_tb_priority)

        # Analyze files in priority order; select first with valid hierarchy or non-procedural methodology
        best_res = None
        for tf in sorted_tb_files:
            res = cls.analyze_file(tf)
            if res.get("hierarchy"):
                return res
            if not best_res and res.get("methodology") != METH_PROCEDURAL:
                best_res = res

        return best_res or cls.analyze_file(sorted_tb_files[0])

    @classmethod
    def analyze_file(cls, file_path):
        """Analyzes a specific testbench file by extension and content."""
        if not os.path.exists(file_path):
            return {
                "methodology": METH_PROCEDURAL,
                "tb_file": file_path,
                "top_component": None,
                "hierarchy": []
            }

        ext = os.path.splitext(file_path)[1].lower()
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            content = ""

        if ext == ".py":
            return cls._analyze_python(file_path, content)
        elif ext in [".vhd", ".vhdl"]:
            return cls._analyze_vhdl(file_path, content)
        else:
            return cls._analyze_verilog_sv(file_path, content)

    @classmethod
    def _analyze_python(cls, file_path, content):
        """Detects pyuvm and cocotb and parses AST class hierarchy."""
        is_pyuvm = bool(re.search(r'\b(?:from\s+pyuvm|import\s+pyuvm)\b', content))
        is_cocotb = bool(re.search(r'\b(?:import\s+cocotb|from\s+cocotb)\b', content))

        methodology = METH_PYUVM if is_pyuvm else (METH_COCOTB if is_cocotb else METH_PROCEDURAL)
        
        hierarchy = []
        top_comp = None

        try:
            tree = ast.parse(content, filename=file_path)
            classes = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    base_names = []
                    for b in node.bases:
                        if isinstance(b, ast.Name):
                            base_names.append(b.id)
                        elif isinstance(b, ast.Attribute):
                            base_names.append(b.attr)
                    classes[node.name] = {
                        "name": node.name,
                        "line": node.lineno,
                        "bases": base_names,
                        "children": []
                    }

            # Inspect build_phase / __init__ for component instantiations
            inst_regex = re.compile(r'self\.(\w+)\s*=\s*(\w+)\s*\(')
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name in classes:
                    for child_node in ast.walk(node):
                        if isinstance(child_node, ast.FunctionDef) and child_node.name in ["build_phase", "__init__"]:
                            # Read function source lines
                            func_text = ast.get_source_segment(content, child_node) or ""
                            for m in inst_regex.finditer(func_text):
                                inst_name, cls_name = m.groups()
                                if cls_name in classes:
                                    classes[node.name]["children"].append({
                                        "instance": inst_name,
                                        "class": cls_name,
                                        "line": classes[cls_name]["line"]
                                    })

            # Identify top test class
            for cname, cinfo in classes.items():
                if any("test" in b.lower() for b in cinfo["bases"]) or cname.lower().endswith("test"):
                    top_comp = cname
                    hierarchy.append(cls._build_py_tree_node(cinfo, classes))
                    break

            if not hierarchy and classes:
                # Fallback to first class
                first_k = list(classes.keys())[0]
                top_comp = first_k
                hierarchy.append(cls._build_py_tree_node(classes[first_k], classes))
        except Exception as e:
            print(f"[tb_detector] Python AST parse error: {e}")

        return {
            "methodology": methodology,
            "tb_file": file_path,
            "top_component": top_comp or os.path.basename(file_path),
            "hierarchy": hierarchy
        }

    @classmethod
    def _build_py_tree_node(cls, cinfo, classes_map, visited=None):
        if visited is None: visited = set()
        visited.add(cinfo["name"])

        node = {
            "name": cinfo["name"],
            "type": ", ".join(cinfo["bases"]) if cinfo["bases"] else "class",
            "line": cinfo.get("line", 1),
            "children": []
        }
        for ch in cinfo.get("children", []):
            ch_cls = ch["class"]
            if ch_cls in classes_map and ch_cls not in visited:
                child_node = cls._build_py_tree_node(classes_map[ch_cls], classes_map, visited)
                child_node["name"] = f"{ch['instance']} ({ch_cls})"
                node["children"].append(child_node)
            else:
                node["children"].append({
                    "name": f"{ch['instance']} ({ch_cls})",
                    "type": "component",
                    "line": ch.get("line", 1),
                    "children": []
                })
        return node

    @classmethod
    def _analyze_verilog_sv(cls, file_path, content):
        """Detects SystemVerilog UVM / SVA vs Standard Procedural Verilog."""
        is_sv_uvm = bool(
            re.search(r'`include\s+["<]uvm_macros\.svh[">]', content) or
            re.search(r'\bimport\s+uvm_pkg::\*', content) or
            re.search(r'\bextends\s+uvm_', content)
        )

        methodology = METH_SV_UVM if is_sv_uvm else METH_PROCEDURAL
        hierarchy = []
        top_name = None

        if is_sv_uvm:
            # Parse all SV UVM class declarations with precise char bounds
            class_pattern = re.compile(r'\bclass\s+(\w+)(?:\s*#\s*\(.*?\))?\s+extends\s+(\w+);')
            classes = {}
            matches = list(class_pattern.finditer(content))
            for i, m in enumerate(matches):
                cname, base = m.group(1), m.group(2)
                start_pos = m.start()
                endclass_m = re.search(r'\bendclass\b', content[start_pos:])
                end_pos = start_pos + endclass_m.end() if endclass_m else len(content)
                if i + 1 < len(matches) and matches[i+1].start() < end_pos:
                    inter_end = re.search(r'\bendclass\b', content[start_pos:matches[i+1].start()])
                    if inter_end:
                        end_pos = start_pos + inter_end.end()
                classes[cname] = {
                    "name": cname,
                    "base": base,
                    "line": content[:start_pos].count('\n') + 1,
                    "start": start_pos,
                    "end": end_pos,
                    "instantiations": []
                }

            # Find create() calls and attribute to enclosing class
            create_regex = re.compile(r'(\w+)\s*=\s*(\w+)::type_id::create\s*\(\s*["\'](\w+)["\']')
            for m in create_regex.finditer(content):
                var_name, cls_name, inst_name = m.groups()
                pos = m.start()
                for cname, cinfo in classes.items():
                    if cinfo["start"] <= pos <= cinfo["end"]:
                        cinfo["instantiations"].append((inst_name, cls_name, var_name))
                        break

            # Recursively build hierarchy tree starting from top test
            def build_tree(cls_name, inst_label=None):
                cinfo = classes.get(cls_name, {})
                node_name = inst_label if inst_label else f"{cls_name} ({cinfo.get('base', 'uvm_component')})"
                node = {
                    "name": node_name,
                    "type": cinfo.get("base", "uvm_component"),
                    "line": cinfo.get("line", 1),
                    "children": []
                }
                for inst_name, sub_cls_name, var_name in cinfo.get("instantiations", []):
                    if sub_cls_name in classes:
                        child_node = build_tree(sub_cls_name, f"{inst_name} ({sub_cls_name})")
                        node["children"].append(child_node)
                    else:
                        node["children"].append({
                            "name": f"{inst_name} ({sub_cls_name})",
                            "type": classes.get(sub_cls_name, {}).get("base", "uvm_component"),
                            "line": cinfo.get("line", 1),
                            "children": []
                        })
                return node

            top_test = None
            for cname, cinfo in classes.items():
                if "test" in cinfo["base"].lower() or cname.lower().endswith("test"):
                    top_test = cname
                    break
            if not top_test and classes:
                top_test = list(classes.keys())[-1]

            if top_test:
                hierarchy = [build_tree(top_test)]
                top_name = top_test

        else:
            # Procedural Verilog module & instance scan
            mod_match = re.search(r'\bmodule\s+(\w+)', content)
            if mod_match:
                top_name = mod_match.group(1)
                line = content[:mod_match.start()].count('\n') + 1
                top_node = {
                    "name": top_name,
                    "type": "module",
                    "line": line,
                    "children": []
                }
                inst_matches = re.finditer(r'\b([a-zA-Z_]\w*)\s+([a-zA-Z_]\w*)\s*\((?!\s*input|\s*output)', content)
                keywords = {'module', 'endmodule', 'reg', 'wire', 'logic', 'integer', 'time', 'initial', 'always', 'begin', 'end', 'task', 'function'}
                for im in inst_matches:
                    cell_type, inst_name = im.groups()
                    if cell_type.lower() not in keywords and inst_name.lower() not in keywords:
                        iline = content[:im.start()].count('\n') + 1
                        top_node["children"].append({
                            "name": f"{inst_name} ({cell_type})",
                            "type": "instance",
                            "line": iline,
                            "children": []
                        })
                hierarchy.append(top_node)

        return {
            "methodology": methodology,
            "tb_file": file_path,
            "top_component": top_name or os.path.basename(file_path),
            "hierarchy": hierarchy
        }
    @classmethod
    def _analyze_vhdl(cls, file_path, content):
        """Detects OSVVM / UVVM vs Procedural VHDL testbenches."""
        is_osvvm = bool(
            re.search(r'\blibrary\s+osvvm\b', content, re.IGNORECASE) or
            re.search(r'\buse\s+osvvm\.', content, re.IGNORECASE) or
            re.search(r'\bAlertLogPkg\b', content, re.IGNORECASE) or
            re.search(r'\bCoveragePkg\b', content, re.IGNORECASE)
        )
        is_uvvm = bool(
            re.search(r'\blibrary\s+uvvm\b', content, re.IGNORECASE) or
            re.search(r'\buse\s+uvvm_', content, re.IGNORECASE)
        )

        methodology = METH_OSVVM if is_osvvm else (METH_UVVM if is_uvvm else METH_PROCEDURAL)
        hierarchy = []
        top_name = None

        ent_match = re.search(r'\bentity\s+(\w+)\s+is\b', content, re.IGNORECASE)
        if ent_match:
            top_name = ent_match.group(1)
            line = content[:ent_match.start()].count('\n') + 1
            top_node = {
                "name": top_name,
                "type": "entity",
                "line": line,
                "children": []
            }

            # Find architecture components or OSVVM packages utilized
            if is_osvvm:
                for pkg in ["AlertLogPkg", "CoveragePkg", "RandomPkg", "ScoreboardPkg_slv"]:
                    if re.search(rf'\b{pkg}\b', content, re.IGNORECASE):
                        top_node["children"].append({
                            "name": f"OSVVM: {pkg}",
                            "type": "package",
                            "line": line,
                            "children": []
                        })

            # Detect testbench processes
            proc_matches = re.finditer(r'\b(?:(\w+)\s*:\s*)?process\b', content, re.IGNORECASE)
            for pm in proc_matches:
                pname = pm.group(1) or "TestProcess"
                pline = content[:pm.start()].count('\n') + 1
                top_node["children"].append({
                    "name": f"{pname} (process)",
                    "type": "process",
                    "line": pline,
                    "children": []
                })

            hierarchy.append(top_node)

        return {
            "methodology": methodology,
            "tb_file": file_path,
            "top_component": top_name or os.path.basename(file_path),
            "hierarchy": hierarchy
        }
