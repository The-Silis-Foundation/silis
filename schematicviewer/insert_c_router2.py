import sys

with open("blockdiagram.py", "r") as f:
    lines = f.readlines()

new_lines = []
in_layout = False
indent = ""

for i, line in enumerate(lines):
    if 'col_x = 300' in line and not in_layout:
        in_layout = True
        new_lines.append('            channel_spacing_v = 400\n')
        new_lines.append('            while True:\n')
        indent = "    "
        new_lines.append(indent + line)
        continue
        
    if in_layout:
        if 'col_x += max_w_in_col + 400' in line:
            new_lines.append(indent + line.replace('400', 'channel_spacing_v'))
            continue
            
        if 'if len(blocks) <= 500:' in line and 'v_crossings = {}' in lines[i-1]:
            # Insert C router integration right before the Python bypass
            c_router_code = """
                if len(blocks) > 500:
                    import ctypes, os
                    class CSegment(ctypes.Structure):
                        _fields_ = [("uid", ctypes.c_int), ("is_h", ctypes.c_int), 
                                    ("x1", ctypes.c_int), ("x2", ctypes.c_int), 
                                    ("y1", ctypes.c_int), ("y2", ctypes.c_int),
                                    ("x_min", ctypes.c_int), ("x_max", ctypes.c_int),
                                    ("y_min", ctypes.c_int), ("y_max", ctypes.c_int)]
                    class CRect(ctypes.Structure):
                        _fields_ = [("left", ctypes.c_int), ("top", ctypes.c_int), 
                                    ("right", ctypes.c_int), ("bottom", ctypes.c_int)]
                                    
                    try:
                        fast_router = ctypes.CDLL(os.path.join(os.path.dirname(__file__), "fast_router.so"))
                        fast_router.space_out_channels_v.restype = ctypes.c_int
                        fast_router.space_out_channels_h.restype = ctypes.c_int
                        
                        c_segs = (CSegment * len(segments))()
                        for idx, s in enumerate(segments):
                            c_segs[idx].uid = s['uid']
                            c_segs[idx].is_h = 1 if s['type'] == 'H' else 0
                            c_segs[idx].x1 = int(s.get('x1', s.get('x', 0)))
                            c_segs[idx].x2 = int(s.get('x2', s.get('x', 0)))
                            c_segs[idx].y1 = int(s.get('y1', s.get('y', 0)))
                            c_segs[idx].y2 = int(s.get('y2', s.get('y', 0)))
                            
                            c_segs[idx].x_min = min(c_segs[idx].x1, c_segs[idx].x2)
                            c_segs[idx].x_max = max(c_segs[idx].x1, c_segs[idx].x2)
                            c_segs[idx].y_min = min(c_segs[idx].y1, c_segs[idx].y2)
                            c_segs[idx].y_max = max(c_segs[idx].y1, c_segs[idx].y2)
                            
                        c_rects = (CRect * len(all_blocks))()
                        for idx, b in enumerate(all_blocks):
                            br = b.sceneBoundingRect()
                            c_rects[idx].left = int(br.left())
                            c_rects[idx].top = int(br.top())
                            c_rects[idx].right = int(br.right())
                            c_rects[idx].bottom = int(br.bottom())
                            
                        fail_v = fast_router.space_out_channels_v(c_segs, len(segments), c_rects, len(all_blocks))
                        fail_h = fast_router.space_out_channels_h(c_segs, len(segments), c_rects, len(all_blocks))
                        
                        if fail_v or fail_h:
                            print(f"[ROUTER] Collision detected during un-overlapping. Expanding spacing to {channel_spacing_v + 400} and retrying...")
                            channel_spacing_v += 400
                            # Clear old geometry
                            for b in all_blocks:
                                b.setPos(0, 0)
                            raise Exception("RetryLayout")
                            
                        for idx, s in enumerate(segments):
                            if s['type'] == 'H':
                                s['y'] = c_segs[idx].y1
                            else:
                                s['x'] = c_segs[idx].x1
                    except Exception as e:
                        if str(e) == "RetryLayout":
                            pass # Caught by outer loop
                        else:
                            print(f"Failed to run C router: {e}")
            """
            for cl in c_router_code.split('\n'):
                if cl.strip(): new_lines.append(indent + cl + '\n')
            
        if 'svg_out.append(\'</svg>\')' in line:
            new_lines.append(indent + line)
            new_lines.append(indent + '                break\n')
            continue
            
        if line.strip() == "":
            new_lines.append("\n")
        elif "except Exception as e:" in line:
            # We reached the end of the try block! Stop indenting!
            in_layout = False
            indent = ""
            new_lines.append(indent + line)
        else:
            # Check for the RetryLayout exception being thrown
            if 'raise Exception("RetryLayout")' in line:
                 new_lines.append(indent + line)
            else:
                 new_lines.append(indent + line)
    else:
        new_lines.append(line)

# Let's fix the retry loop catching mechanism. The easiest way is to use a try/except inside the while True loop.
# Actually, if we just `continue` the while loop, it will jump to the top of `while True:`.
# Oh! But `continue` is inside the `for iteration in range(MAX_ITERS)`!
# If it `continue`s inside `MAX_ITERS`, it won't restart the `while True:`!
# That's why I need a custom exception:
# try:
#     for iteration in range(MAX_ITERS):
#         ...
#         raise Exception("RetryLayout")
# except Exception as e:
#     if str(e) == "RetryLayout": continue

# Let's write this correctly!
