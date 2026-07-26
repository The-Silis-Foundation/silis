import os

filepath = "/home/jerome/silis/silis.py"
with open(filepath, "r") as f:
    code = f.read()

replacements = {
    # 1. Fix Floorplanner place command
    'place_cell -inst_name {item.name}_inst -origin {{{item.pos().x()} {item.pos().y()}}} -orient R0 -status PLACED': 
    'place_inst -name {item.name}_inst -origin {{{item.pos().x()} {item.pos().y()}}} -orientation R0 -status PLACED',
    
    # 2. SynthesisTab styling
    'ctrl = QFrame(); ctrl.setStyleSheet("background: #f6f8fa; border-radius: 4px; padding: 5px; border: 1px solid #d0d7de;")': 
    'ctrl = QFrame(); ctrl.setStyleSheet("border-radius: 4px; padding: 5px; border: 1px solid gray;")',
    
    'self.lbl_pdk = QLabel("Active PDK: Sky130A"); self.lbl_pdk.setStyleSheet("font-weight:bold; color:#24292f;")':
    'self.lbl_pdk = QLabel("Active PDK: Sky130A"); self.lbl_pdk.setStyleSheet("font-weight:bold;")',
    
    'btn_style = "QPushButton { background: #ffffff; color: #24292f; border: 1px solid #d0d7de; padding: 5px 15px; border-radius: 3px; } QPushButton:hover { background: #f3f4f6; }"':
    'btn_style = "QPushButton { border: 1px solid gray; padding: 5px 15px; border-radius: 3px; }"',
    
    'run_style = "QPushButton { background: #2da44e; color: white; border: 1px solid #2da44e; padding: 5px 15px; border-radius: 3px; font-weight: bold; } QPushButton:hover { background: #2c974b; }"':
    'run_style = "QPushButton { border: 1px solid gray; padding: 5px 15px; border-radius: 3px; font-weight: bold; }"',
    
    'self.log_tabs.setStyleSheet("QTabWidget::pane { border: 0; } QTabBar::tab { background: #f6f8fa; color: #57606a; padding: 8px; border: 1px solid #e1e4e8; border-bottom: none; } QTabBar::tab:selected { background: #fff; color: #24292f; border-top: 2px solid #fd8c73; }")':
    'self.log_tabs.setStyleSheet("")',
    
    'self.log_main.setStyleSheet("background:#0d1117; color:#c9d1d9; font-family:Consolas; border:none;")':
    'self.log_main.setStyleSheet("font-family:Consolas; border:none;")',
    
    'self.list_err.setStyleSheet("background:#ffffff; color:#cf222e; font-family:Consolas; border:1px solid #d0d7de; padding: 5px;")':
    'self.list_err.setStyleSheet("color:#cf222e; font-family:Consolas; border:1px solid gray; padding: 5px;")',
    
    'right_col.setStyleSheet("background: #f6f8fa; border-left: 1px solid #d0d7de;")':
    'right_col.setStyleSheet("border-left: 1px solid gray;")',
    
    'self.card_status.setStyleSheet("background:#eaeef2; color:#57606a; font-size:14px; font-weight:bold; padding:10px; border-radius:6px; border: 1px solid #d0d7de;")':
    'self.card_status.setStyleSheet("font-size:14px; font-weight:bold; padding:10px; border-radius:6px; border: 1px solid gray;")',
    
    'v_style = "font-weight:bold; font-size:12px; color: #24292f;"':
    'v_style = "font-weight:bold; font-size:12px;"',
    
    'self.preview.setStyleSheet("font-family:Consolas; font-size:8pt; background:#ffffff; color:#333; border:1px solid #d0d7de;")':
    'self.preview.setStyleSheet("font-family:Consolas; font-size:8pt; border:1px solid gray;")',
    
    'btn_save = QPushButton("Save .rpt File"); btn_save.setStyleSheet("background:#fff; border:1px solid #ccc; padding:5px;")':
    'btn_save = QPushButton("Save .rpt File"); btn_save.setStyleSheet("border:1px solid gray; padding:5px;")',
    
    # 3. BackendWidget styling
    'self.layer_list.setStyleSheet("QListWidget { font-size: 10px; border: none; background: #f0f0f0; }")':
    'self.layer_list.setStyleSheet("QListWidget { font-size: 10px; border: none; }")',
    
    'self.term_log.setStyleSheet("background: #101010; color: #00FF00; font-family: Consolas; border: none;")':
    'self.term_log.setStyleSheet("font-family: Consolas; border: none;")',
    
    'self.term_in.setStyleSheet("background: #202020; color: white; border-top: 1px solid #444; font-family: Consolas; padding: 5px;")':
    'self.term_in.setStyleSheet("font-family: Consolas; padding: 5px; border-top: 1px solid gray;")',
    
    'self.ribbon = QFrame(); self.ribbon.setStyleSheet("background: #f0f0f0; border-bottom: 1px solid #ccc;"); self.ribbon.setFixedHeight(40)':
    'self.ribbon = QFrame(); self.ribbon.setStyleSheet("border-bottom: 1px solid gray;"); self.ribbon.setFixedHeight(40)',
    
    'sidebar = QFrame(); sidebar.setFixedWidth(140); sidebar.setStyleSheet("background: #e8e8e8; border-right: 1px solid #aaa;")':
    'sidebar = QFrame(); sidebar.setFixedWidth(140); sidebar.setStyleSheet("border-right: 1px solid gray;")'
}

for k, v in replacements.items():
    code = code.replace(k, v)

with open(filepath, "w") as f:
    f.write(code)

print("Done")
