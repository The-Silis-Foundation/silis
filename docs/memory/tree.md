silis
├── ATTRIBUTION.md
├── backend_studio_plan.md
├── CITATION.cff
├── CONTRIBUTING.md
├── core
│   ├── assets
│   │   ├── banneriguess.png
│   │   └── silisicon.png
│   ├── backendflow
│   │   ├── def_viewer_cpp
│   │   │   ├── CMakeLists.txt
│   │   │   ├── LayoutViewer.cpp
│   │   │   ├── LayoutViewer.h
│   │   │   ├── main.cpp
│   │   │   ├── RenderThread.cpp
│   │   │   └── RenderThread.h
│   │   ├── design_exporter.py
│   │   ├── fast_viewer
│   │   │   ├── bindings.cpp
│   │   │   ├── CMakeLists.txt
│   │   │   ├── FastLayoutViewer.cpp
│   │   │   ├── fast_layout_viewer.cpython-312-x86_64-linux-gnu.so
│   │   │   ├── FastLayoutViewer.h
│   │   │   ├── generate_viewer.py
│   │   │   ├── silis_custom_embed.py
│   │   │   ├── test_cpp_box_raster.py
│   │   │   └── test_cpp_raster.py
│   │   ├── floorplanner
│   │   │   ├── floorplanner.py
│   │   │   ├── floorplanner.py.bak_before_fps
│   │   │   ├── floorplanner.py.bak_before_ioplacer_fix
│   │   │   ├── floorplanner.py.bak_before_merge
│   │   │   ├── floorplanner.py.bak_pre_fps
│   │   │   ├── floorplanner.py.bak_pre_fps_full
│   │   │   ├── __init__.py
│   │   │   ├── ioplacer.py
│   │   │   ├── ioplacer.py.bak_before_overhaul
│   │   │   ├── ioplacer.py.bak_pre_fps
│   │   │   ├── power_domain_manager.py
│   │   │   ├── region_autoplacer.py
│   │   │   ├── silis_fp.tcl
│   │   │   ├── test_density.py
│   │   │   └── test_region.py
│   │   ├── flow
│   │   │   ├── backendflow.py
│   │   │   ├── backendflow.py.bak_pre_fps_full
│   │   │   ├── cts.tcl
│   │   │   ├── __init__.py
│   │   │   ├── io_pins.tcl
│   │   │   ├── pdn.tcl
│   │   │   ├── place.tcl
│   │   │   ├── route.tcl
│   │   │   └── tapcells.tcl
│   │   ├── gds_snapshot.py
│   │   ├── gdsviewer
│   │   │   ├── gds3d.py
│   │   │   └── __init__.py
│   │   ├── __init__.py
│   │   ├── macro_exporter.py
│   │   ├── power
│   │   │   └── upf_engine.py
│   │   ├── shims
│   │   │   └── openroad_upf_shim.tcl
│   │   ├── signoff_flow.py
│   │   ├── signoff_report.py
│   │   └── siliconpeeker
│   │       ├── fast_layout_viewer.cpython-312-x86_64-linux-gnu.so
│   │       ├── __init__.py
│   │       └── peeker.py
│   ├── cli
│   │   ├── flow.py
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── project.py
│   │   ├── tui_editor.py
│   │   └── tui_repl.py
│   ├── clocktreeviewer
│   │   ├── bindings_clocktree.cpp
│   │   ├── clocktree_engine.cpython-312-x86_64-linux-gnu.so
│   │   ├── ClockTreeViewer.cpp
│   │   ├── ClockTreeViewer.h
│   │   └── CMakeLists.txt
│   ├── config.py
│   ├── design_explorer.py
│   ├── dft
│   │   ├── dft_engine.py
│   │   ├── dft_viewer.py
│   │   ├── __init__.py
│   │   └── scandef.py
│   ├── editor
│   │   ├── bindings_editor.cpp
│   │   ├── CMakeLists.txt
│   │   ├── colorconfig.json
│   │   ├── editor_engine.cpython-312-x86_64-linux-gnu.so
│   │   ├── editor.py
│   │   ├── __init__.py
│   │   ├── markdown_preview.html
│   │   ├── marked.min.js
│   │   ├── mermaid.min.js
│   │   ├── monaco.html
│   │   ├── MonacoViewer.cpp
│   │   ├── MonacoViewer.h
│   │   └── vs -> /home/eatheswar/silisfoundation/silis/third-party/monaco/node_modules/monaco-editor/min/vs
│   ├── gui_shared_webengine.py
│   ├── __init__.py
│   ├── intake
│   │   ├── conversion_runner.py
│   │   ├── dependency_graph.py
│   │   ├── __init__.py
│   │   ├── intake_dialog.py
│   │   ├── port_extractor.py
│   │   ├── source_scanner.py
│   │   ├── tb_runner.py
│   │   └── top_finder.py
│   ├── lvs
│   │   ├── lvs_engine.py
│   │   └── lvs_viewer.py
│   ├── pdkmanagers
│   │   ├── __init__.py
│   │   ├── macro
│   │   │   ├── __init__.py
│   │   │   ├── ipcatalog.py
│   │   │   └── openram_studio.py
│   │   ├── pdk
│   │   │   ├── __init__.py
│   │   │   └── manager.py
│   │   └── volare.py
│   ├── project_registry.py
│   ├── projectwizard
│   │   ├── codes.py
│   │   └── __init__.py
│   ├── qt_setup.py
│   ├── schematicviewer
│   │   ├── bindings_schematic.cpp
│   │   ├── CMakeLists.txt
│   │   ├── digitaljs.html
│   │   ├── dotschemmaker.py
│   │   ├── graphiccanvas.py
│   │   ├── __init__.py
│   │   ├── json.hpp
│   │   ├── schematic_engine.cpython-312-x86_64-linux-gnu.so
│   │   ├── SchematicViewer.cpp
│   │   ├── SchematicViewer.h
│   │   ├── web
│   │   │   ├── schematic_webview.css
│   │   │   ├── schematic_webview.js
│   │   │   └── yosys_bridge.js
│   │   ├── YosysWorker.cpp
│   │   └── YosysWorker.h
│   ├── sdk
│   │   ├── exceptions.py
│   │   ├── floorplan.py
│   │   ├── __init__.py
│   │   ├── layout.py
│   │   ├── opendb_bridge.py
│   │   ├── pipeline.py
│   │   ├── power.py
│   │   ├── project.py
│   │   ├── report.py
│   │   ├── sc_bridge.py
│   │   ├── sdc.py
│   │   ├── timing.py
│   │   └── viewers.py
│   ├── sdk_installer.py
│   ├── setup_wizard.py
│   ├── signalpeeker
│   │   ├── code.py
│   │   ├── __init__.py
│   │   ├── server.py
│   │   ├── vcd_tracker.py
│   │   └── web
│   │       └── rohd
│   ├── simulation
│   │   ├── gls_engine.py
│   │   └── gls_viewer.py
│   ├── synthengine
│   │   ├── bindings_synth.cpp
│   │   ├── CMakeLists.txt
│   │   ├── synth_engine.cpython-312-x86_64-linux-gnu.so
│   │   ├── SynthOrchestrator.cpp
│   │   ├── SynthOrchestrator.h
│   │   ├── TimingAnalyzer.cpp
│   │   └── TimingAnalyzer.h
│   ├── synthesisscripts
│   │   ├── __init__.py
│   │   └── synthesisthread.py
│   ├── tapeout
│   │   ├── fill_engine.py
│   │   └── manifest_viewer.py
│   ├── terminal
│   │   ├── bindings_terminal.cpp
│   │   ├── CMakeLists.txt
│   │   ├── __init__.py
│   │   ├── terminal_engine.cpython-312-x86_64-linux-gnu.so
│   │   ├── terminal.py
│   │   ├── TerminalViewer.cpp
│   │   ├── TerminalViewer.h
│   │   ├── TerminalWidget.cpp
│   │   └── TerminalWidget.h
│   ├── updater
│   │   └── delta_updater.py
│   └── verification
│       ├── tb_detector.py
│       ├── tb_detector.py.bak_pre_sim_fix
│       ├── verificationprt.py
│       └── verification_report_generator.py
├── docs
│   ├── architecture
│   │   ├── architecture.dot
│   │   ├── architecture.png
│   │   └── architecture.py
│   ├── book
│   │   ├── 01_architecture_overview.md
│   │   ├── 02_python_sdk_reference.md
│   │   ├── 03_cli_reference.md
│   │   ├── 04_siliconcompiler_compatibility.md
│   │   ├── 05_advanced_floorplanning.md
│   │   ├── 06_polyglot_and_formal.md
│   │   └── 07_reference_examples.md
│   ├── Capability.md
│   ├── INDEX.md
│   ├── memory
│   │   ├── architecture_map.md
│   │   ├── CODEBASE_KNOWLEDGE.md
│   │   ├── EDA_DOWNSTREAM_PLAYBOOK.md
│   │   ├── eda_error_registry.json
│   │   ├── SYMBOL_INDEX.json
│   │   └── tree.md
│   ├── OPENROAD_FLOW_REFERENCE.md
│   ├── OPENROAD_VISUAL_ASSETS_MAP.md
│   ├── reference
│   │   ├── run_gemm_pentium_e2e.py
│   │   └── run_pure_python_sdk.py
│   └── SILIS_PYTHON_SDK_MANUAL.md
├── examples
│   └── cpp_macro_to_sv_chip
│       ├── chip_top_proj
│       │   ├── merge_magic.tcl
│       │   ├── netlist
│       │   ├── reports
│       │   ├── results
│       │   ├── run_cts.tcl
│       │   ├── run_drc.tcl
│       │   ├── run_floorplan.tcl
│       │   ├── run_init.tcl
│       │   ├── run_iopins.tcl
│       │   ├── run_pdn.tcl
│       │   ├── run_place.tcl
│       │   ├── run_route.tcl
│       │   ├── run_tapcells.tcl
│       │   ├── silis.silisproj
│       │   ├── source
│       │   ├── sta.tcl
│       │   └── synth.ys
│       ├── chip_top.sdc
│       ├── chip_top.sv
│       ├── cpp_macro_to_sv_chip.py
│       ├── reports
│       │   └── sys.log
│       ├── simple_alu.cpp
│       ├── simple_alu_macro_proj
│       │   ├── merge_magic.tcl
│       │   ├── netlist
│       │   ├── reports
│       │   ├── results
│       │   ├── run_cts.tcl
│       │   ├── run_floorplan.tcl
│       │   ├── run_init.tcl
│       │   ├── run_iopins.tcl
│       │   ├── run_pdn.tcl
│       │   ├── run_place.tcl
│       │   ├── run_route.tcl
│       │   ├── run_tapcells.tcl
│       │   ├── silis.silisproj
│       │   ├── source
│       │   ├── sta.tcl
│       │   └── synth.ys
│       └── simple_alu.v
├── GOVERNANCE.md
├── __init__.py
├── LICENSE
├── MAINTAINERS.md
├── packaging
│   ├── AppRun
│   ├── build_appimage.sh
│   ├── silis.desktop
│   └── silisicon.png
├── README.md
├── reports
│   └── sys.log
├── silis.py
├── tests
│   ├── launch_gui_window.py
│   ├── launch_standalone_layout.py
│   ├── launch_visible_layout.py
│   ├── run_full_pipeline.py
│   ├── run_pure_python_sdk.py
│   ├── silis
│   │   └── projects
│   │       └── sram_soc_quad_pure_sdk
│   ├── test_fastroute_via.tcl
│   ├── test_sdk_capabilities.py
│   ├── test_sdk_enquiry.py
│   ├── test_sdk.py
│   ├── test_via_gen.tcl
│   └── verify_everything.py
└── TRADEMARK.md

59 directories, 249 files
