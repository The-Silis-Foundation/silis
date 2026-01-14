# Proof Of Concept POC Version 17 - Quick Start Guide 

## Initial Setup and Pre-Requisites

**The following setup and installations must be done for the functioning of the code**

````
# Update 
sudo apt-get update

# Python installation
sudo apt install python3


# Core EDA tools
sudo apt install iverilog gtkwave yosys graphviz

# Optional (for better schematics)
sudo apt install nodejs npm
sudo npm install -g netlistsvg
sudo apt install librsvg2-bin

# Python dependencies
sudo apt-get install python3-pil.imagetk
sudo apt install python3-tk
pip install pillow
````
# Running POC V17

Run the script by
`python3 pocv17.py`

# Workflow tutorial

### 1. Write Your Verilog

- Press **Ctrl+N** for new file

<img width="960" height="603" alt="ctrls_s" src="https://github.com/user-attachments/assets/dbe83c0f-ab20-40d8-8711-904b4882bfb8" />

- Write your module (auto-indent on `begin`, `module`, etc.)
- Press **Ctrl+S** to save

---

### 2. Simulate (F1)
- **F1** compiles and runs your testbench
- Automatically injects `$dumpfile` if missing
- Creates organized project structure: `[module]_project/source/`
- Watches terminal for compilation errors
  
- Before F1: Files scattered in root directory  <img width="963" height="603" alt="unauto_mgnt" src="https://github.com/user-attachments/assets/7f89795a-326c-43fa-84c3-763f141c6991" />

- After F1: Organized into module_project/source/ <img width="964" height="600" alt="auto_mgnt2" src="https://github.com/user-attachments/assets/0c4d3a1d-305d-4d15-9927-c9fd333289bd" />

---

### 3. View Waveforms (F2)
- **F2** opens GTKWave with your .vcd file

- ![WhatsApp Image 2026-01-13 at 00 00 18](https://github.com/user-attachments/assets/8213b2d9-4677-4789-b1b2-0c7b80619f4e)

- Auto-finds most recent simulation output
- **Known issue**: If F2 doesn't work, manually double-click the .vcd file in the file explorer

---

### 4. Generate Schematic (F3)
- **F3** creates visual schematic from your RTL
  
- <img width="960" height="599" alt="schematicview" src="https://github.com/user-attachments/assets/3e79c969-84bd-4b7d-8339-1f81f9e05190" />

- Uses NetlistSVG (if installed) or falls back to Graphviz
- Zoomable viewer with mouse drag + scroll

---

### 5. Synthesize (F4) 
- Add .lib file path to your settings
- **F4** runs full synthesis flow using Yosys
  
- <img width="966" height="607" alt="settings" src="https://github.com/user-attachments/assets/cbc90f4d-7129-495f-a407-2f7b225439ef" />

- Opens Constraint Wizard for timing/area targets (optional)
  
- <img width="962" height="603" alt="cwiz" src="https://github.com/user-attachments/assets/18d6eaab-e184-491c-b62d-0292914ad27b" />

- Requires PDK .lib file (set in Settings ⚙)
- Generates netlist in `netlist/` folder

---

## Keyboard Shortcuts

### Global
- **F1** - Compile & Simulate
- **F2** - Open Waveforms
- **F3** - Generate Schematic  
- **F4** - Run Synthesis
- **Ctrl+N** - New File
- **Ctrl+S** - Save File

### Superkey Mode (Press `` ` `` then...)
The toolbar turns **cyan** when active. Then press:
- **C** - Focus Code Editor
- **X** - Focus Terminal
- **V** - Focus File Explorer  
- **Z** - Focus Schematic Viewer
- **S** - Toggle Terminal Mode (SHELL ↔ SIM)

*Timeout: 1 second after pressing `` ` ``*

### File Explorer
- **Enter** - Open file or expand folder
- **Escape** - Go up one directory
- **Ctrl+Z / Ctrl+Y** - Navigate back/forward
- **Delete** - Delete selected file
- **Right-click** - Context menu (Delete/Rename)

### Terminal
- **Tab** - Autocomplete file paths
- **[SHELL] mode** - Run system commands, `cd` support
- **[SIM] mode** - Send input to running simulation

### Schematic Viewer
- **+/-** - Keyboard zoom
- **Arrow keys** - Keyboard Pan
- **Mouse drag** - Pan
- **Scroll wheel** - Zoom

## Project Structure (Auto-Generated)

When you hit F1/F4, silis creates:
````
your_module_project/
├── source/          # Your .v files get moved here
│   ├── module.v
│   └── tb_module.v
├── netlist/         # Synthesis outputs
│   └── module_netlist.v
└── reports/         # Logs, area reports, etc.
````

## Troubleshooting

**"Syntax Error" on F1**
- Check the terminal output for line numbers
- Make sure your module name matches the filename

**Synthesis fails (F4)**
- Verify PDK .lib path in Settings (⚙)
- Check `reports/synthesis.log` for details

**Schematic is blank**
- Install NetlistSVG: `npm install -g netlistsvg`
- Or use Graphviz fallback (change in Settings)

**Terminal not responding**
- Toggle mode with `` ` `` + **S**
- Make sure you're in [SHELL] mode for commands


---

### Managed by **DevCtrl**, Version Control Environment for silis development

---

**Version**: POC V17 (Stable)  
**Last Updated**: 13th of January 2026  
**Status**: Experimental - breaking changes expected in future POCs  

For the latest unstable features, [check experimentals](https://github.com/JeromeAntonyRobin/silis/tree/main/experimental)

