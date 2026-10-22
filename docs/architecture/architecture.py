import os
import ast
import re
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))

edges = []
nodes = set()

# Known C++ engines
ENGINES = {
    'terminal_engine': 'terminal/bindings_terminal.cpp',
    'peeker_engine': 'backendflow/siliconpeeker/peeker_engine.cpp',
    'fast_layout_viewer': 'backendflow/fast_viewer/bindings_viewer.cpp',
    'schematic_engine': 'schematicviewer/fast_schem_viewer/bindings_schematic.cpp',
    'gds3d_engine': 'third-party/GDS3D/bindings_gds3d.cpp'
}

def resolve_py_module(module_name, current_dir):
    parts = module_name.split('.')
    path_from_root = os.path.join(ROOT, *parts) + '.py'
    if os.path.exists(path_from_root): return path_from_root
    path_from_root_init = os.path.join(ROOT, *parts, '__init__.py')
    if os.path.exists(path_from_root_init): return path_from_root_init
    path_from_curr = os.path.join(current_dir, *parts) + '.py'
    if os.path.exists(path_from_curr): return path_from_curr
    return None

def scan_python(filepath):
    if filepath in nodes: return
    nodes.add(filepath)
    rel_path = os.path.relpath(filepath, ROOT)
    current_dir = os.path.dirname(filepath)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. HTML dependencies
    html_matches = re.findall(r'[\'"]([^\'"]+\.html)[\'"]', content)
    for html in html_matches:
        html_path = os.path.normpath(os.path.join(current_dir, html))
        if os.path.exists(html_path):
            edges.append((rel_path, os.path.relpath(html_path, ROOT), "load HTML"))
            scan_html(html_path)

    # 2. Python imports
    try:
        tree = ast.parse(content, filename=filepath)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ENGINES:
                        cpp_file = ENGINES[alias.name]
                        edges.append((rel_path, cpp_file, "pybind11"))
                        scan_cpp(os.path.join(ROOT, cpp_file))
                    else:
                        resolved = resolve_py_module(alias.name, current_dir)
                        if resolved:
                            edges.append((rel_path, os.path.relpath(resolved, ROOT), "import"))
                            scan_python(resolved)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    if node.module in ENGINES:
                        cpp_file = ENGINES[node.module]
                        edges.append((rel_path, cpp_file, "pybind11"))
                        scan_cpp(os.path.join(ROOT, cpp_file))
                    else:
                        resolved = resolve_py_module(node.module, current_dir)
                        if resolved:
                            edges.append((rel_path, os.path.relpath(resolved, ROOT), "from import"))
                            scan_python(resolved)
    except Exception:
        pass

def scan_cpp(filepath):
    if filepath in nodes: return
    nodes.add(filepath)
    rel_path = os.path.relpath(filepath, ROOT)
    current_dir = os.path.dirname(filepath)
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        includes = re.findall(r'#include\s+"([^"]+)"', content)
        for inc in includes:
            inc_path = os.path.normpath(os.path.join(current_dir, inc))
            if os.path.exists(inc_path):
                edges.append((rel_path, os.path.relpath(inc_path, ROOT), "include"))
                scan_cpp(inc_path)
    except Exception:
        pass

def scan_html(filepath):
    if filepath in nodes: return
    nodes.add(filepath)
    rel_path = os.path.relpath(filepath, ROOT)
    current_dir = os.path.dirname(filepath)
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        scripts = re.findall(r'<script[^>]+src=[\'"]([^\'"]+\.js)[\'"]', content)
        for script in scripts:
            script_path = os.path.normpath(os.path.join(current_dir, script))
            if os.path.exists(script_path):
                edges.append((rel_path, os.path.relpath(script_path, ROOT), "script src"))
                # Register the JS node
                nodes.add(script_path)
    except Exception:
        pass

if __name__ == "__main__":
    scan_python(os.path.join(ROOT, 'silis.py'))
    
    dot_file = os.path.join(ROOT, 'architecture.dot')
    with open(dot_file, 'w') as f:
        f.write('digraph G {\n')
        f.write('  rankdir=LR;\n')
        f.write('  node [style=filled, fontname="Helvetica", fontsize=10];\n')
        f.write('  edge [fontname="Helvetica", fontsize=8];\n')
        
        for n in nodes:
            rel = os.path.relpath(n, ROOT)
            color = "lightblue"
            if rel.endswith('.cpp') or rel.endswith('.h'): color = "lightgreen"
            elif rel.endswith('.html'): color = "lightsalmon"
            elif rel.endswith('.js'): color = "lightyellow"
            f.write(f'  "{rel}" [fillcolor={color}, shape=box];\n')
            
        for src, dst, label in edges:
            f.write(f'  "{src}" -> "{dst}" [label="{label}"];\n')
            
        f.write('}\n')
        
    print("Generating architecture.png...")
    subprocess.run(["dot", "-Tpng", dot_file, "-o", "architecture.png"])
    print("Done! Diagram saved to architecture.png")
