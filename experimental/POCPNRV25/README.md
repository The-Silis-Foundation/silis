# Proof Of Concept PnR Version 25 - Quick Start Guide

## INITIAL SETUP AND PRE-REQUISITES

### The following setup and installations must be done for the functioning of the code

```
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

```
### NOTE: OpenROAD has to be installed locally!

## Running POC PnR V25


Run the script by `python3 pocpnrv25.py`

# Workflow tutorial

### 1. Write Your Verilog

- Press **Ctrl+N** for new file

-   ![newfile25](https://github.com/user-attachments/assets/ed59a78f-0db7-44d9-b9cd-cca71d5fc443)


- Write your module (auto-indent on `begin`, `module`, etc.)
- Press **Ctrl+S** to save
- save your .sdc file in the name `module.sdc` in `/netlist` directory
---

### 2. Simulate (F1)
- **F1** compiles and runs your testbench
- Creates organized project structure: `[module]_project/source/`
- Watches terminal for compilation errors
  
- Before F1: Files scattered in root directory  <img width="3838" height="2052" alt="image" src="https://github.com/user-attachments/assets/c3e3ecec-8405-4749-ae5d-4a0d0a9488ac" />


- After F1: Organized into module_project/source/ <img width="3843" height="2160" alt="image" src="https://github.com/user-attachments/assets/b36a187d-1a6f-4543-bbaf-1f8b089a80cd" />


---

### 3. View Waveforms (F2)

- **F2** opens signalpeeker (built-in waveform viewer) with your .vcd file with optons to view with GTKWave

- ![signalpeekerex](https://github.com/user-attachments/assets/f65bcd87-3db8-4266-84a3-419af0323d0d)

- **Keybinds**
  - `w` and `s` for navigating up and down
  - `a` and `d` for moving cursor left and right
  - up and down arrow for zoom in and zoom out

- Auto-finds .vcd file in project root folder


---

### 4. Generate Schematic (F3)
- **F3** creates visual schematic from your RTL
  
- ![schem25](https://github.com/user-attachments/assets/305c04cd-041a-47c1-b53f-e57151b56c69)


- Uses NetlistSVG (if installed) or falls back to Graphviz
- Zoomable viewer with mouse drag + scroll

---

### 5. Synthesize (F4) 

- **F4** opens PDK manager, click "add new", pick your .lib, .lef, .tlef , .tech (for magic), .gds files for your PDK and save under the name of your preference, this config will be saved 
  
- PDK Manager <img width="2814" height="1869" alt="PDKManager" src="https://github.com/user-attachments/assets/ec1150e2-847a-4dfb-9f74-faaffd37573e" />


- Run synthesis by clicking f4 again <img width="1599" height="895" alt="image" src="https://github.com/user-attachments/assets/f31bb021-d69c-4ef4-84d9-909320b8bf9d" />


- Requires PDK files said above (set in Settings ⚙)
- Generates netlist in `netlist/` folder

---

# Backend & Physical Design Tutorial

The Backend module in Silis acts as a GUI wrapper for the OpenROAD flow, giving you granular control over the physical design process from Netlist to GDSII.

### 1. The Physical Design Flow
Navigate to the **Backend** workspace using the toolbar or `Superkey + 2`. The flow is divided into linear stages located on the top ribbon.

**Standard Flow:**
* **Init:** Loads your synthesized netlist (`.v`), technology LEFs, and timing libraries (`.lib`).
* **Floorplan:** Defines the die area (default 400x400um) and core utilization.
* **Tapcells:** Inserts well-tap cells to prevent latch-up.
* **PDN:** Generates the Power Distribution Network (VDD/VSS grids).
* **IO Pins:** Places input/output pins on the boundary.
* **Place:** Performs Global Placement (coarse) followed by Detailed Placement (legalization).
* **CTS:** Synthesizes the Clock Tree to minimize skew and insertion delay.
* **Route:** Performs Global Routing and Detailed Routing using TritonRoute.
* **GDS:** Streams out the final GDSII file for manufacturing.
- <img width="1602" height="900" alt="image" src="https://github.com/user-attachments/assets/e225f181-3dc3-45e1-bba9-b3c70ba03182" />

**Interactive Tcl Execution:**
Silis does not blindly execute commands. When you click a flow step (e.g., "Floorplan"), the IDE opens a **Command Confirmation Dialog**.
- <img width="1599" height="902" alt="image" src="https://github.com/user-attachments/assets/ac4837cf-f78b-433c-a253-b620ea2c4d81" />

* **Review:** See the exact Tcl command Silis is about to send to OpenROAD.
* **Edit:** You can manually modify parameters (e.g., changing `-density 0.6` to `-density 0.7` in the placement step) before execution.
* **Confirm:** Pressing OK sends the custom command directly to the live OpenROAD shell.

### 2. Visualization Tools

**SiliconPeeker (Live Floorplan)**
Located in the "Live Floorplan (DEF)" tab, this viewer renders the chip state in real-time as you progress through the flow.
- <img width="3838" height="2160" alt="image" src="https://github.com/user-attachments/assets/afb85cd9-aaa9-40f7-94b8-1dba00d94aec" />


* **Real-time Updates:** Automatically refreshes after every flow step.
* **Layer Controls:** Toggle visibility for Cells, Pins, Nets (Flylines), and Power Rails via the sidebar.
* **Heatmap Overlay:** Click the **Heatmap** button to overlay a cell density map. This "organic" view helps identify congestion hotspots where placement density is too high, predicting potential routing violations. <img width="3838" height="2160" alt="image" src="https://github.com/user-attachments/assets/18af6493-b3dd-4e96-8b3d-0f8c3542d32a" />



**Integrated GDS Viewer**
Located in the "Final Chip (GDS)" tab, this tool renders the manufacturing output.
- <img width="3838" height="2052" alt="image" src="https://github.com/user-attachments/assets/babbbafd-ebe6-4d4c-923f-be023e7eb419" />

* **LOD Optimization:** Uses Level-of-Detail rendering to efficiently display millions of polygons without lagging the UI. Small details are simplified when zoomed out.
* **Layer Browser:** The sidebar populates with all GDS layers found in the file. You can toggle specific metal or via layers to inspect the layout structure.
* **Navigation:** Supports standard mouse-drag panning and scroll-wheel zooming.

### 3. PDK Management (Volare Integration)
Silis includes a dedicated GUI for **Volare**, the open-source PDK version manager. This allows you to manage SkyWater130 and GF180MCU versions without touching the command line.

**Accessing Volare:**
1.  Open **Settings** (Gear Icon).
2.  Navigate to the **Volare (PDK Version Control)** tab.
 - ![volareint](https://github.com/user-attachments/assets/f17f09df-8b55-4d4c-bbea-d5baca0bcb82)

**Features:**
* **Target PDK Family:** Switch between `sky130` and `gf180mcu`.
* **Version Management:**
    * **List Installed:** Shows all PDK versions currently on your machine.
    * **List Remote:** Fetches available versions from the Open_PDKs repository.
    * **Show Active:** Highlights the version currently selected for builds.
* **One-Click Actions:**
    * **Enable Version:** Switch the active PDK pointer to a specific hash/tag.
    * **Build/Install:** Download and compile a specific PDK version automatically.
    * **Prune Old:** Frees up disk space by removing unused PDK versions.
