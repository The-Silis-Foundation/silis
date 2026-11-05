import bisect

class FastVcdTracker:
    """
    Lightweight, high-speed VCD parser and indexer for real-time
    net value lookups at arbitrary timestamps.
    """
    def __init__(self, path):
        self.path = path
        self.var_aliases = {} # sym -> [(full_path, name, width)]
        self.name_history = {} # name -> [(time_ps, value_str)]
        self.name_widths = {} # name -> width_int
        self.timescale_mult = 1.0 # factor to convert VCD ticks into picoseconds (ps)
        self._parse()

    def _parse(self):
        try:
            with open(self.path, 'r', errors='ignore') as f:
                scope = []
                # Header definition phase
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith('$timescale'):
                        # e.g. 1ns, 1ps, 10ps, 100fs
                        val_str = ""
                        for sub in f:
                            sub = sub.strip()
                            if '$end' in sub:
                                val_str += " " + sub.replace('$end', '')
                                break
                            val_str += " " + sub
                        self.timescale_mult = self._parse_timescale(val_str)
                    elif line.startswith('$scope'):
                        parts = line.split()
                        if len(parts) >= 3:
                            scope.append(parts[2])
                    elif line.startswith('$upscope'):
                        if scope:
                            scope.pop()
                    elif line.startswith('$var'):
                        parts = line.split()
                        if len(parts) >= 5:
                            try:
                                width = int(parts[2])
                            except Exception:
                                width = 1
                            sym = parts[3]
                            name = parts[4]
                            full = '.'.join(scope + [name])
                            if sym not in self.var_aliases:
                                self.var_aliases[sym] = []
                            self.var_aliases[sym].append((full, name, width))
                    elif '$enddefinitions' in line:
                        break

                # Value change recording phase
                history = {s: [] for s in self.var_aliases}
                curr_time = 0

                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if line[0] == '#':
                        curr_time = int(line[1:])
                    elif line[0] in 'bBrR':
                        parts = line.split()
                        val = parts[0][1:]
                        sym = parts[1]
                        if sym in history:
                            history[sym].append((curr_time, val))
                    elif line[0] in '01xXzZ':
                        val = line[0]
                        sym = line[1:]
                        if sym in history:
                            history[sym].append((curr_time, val))

                # Track alias resolution depth for short names
                short_source_depth = {}
                for sym, aliases in self.var_aliases.items():
                    hist = history.get(sym, [])
                    if not hist:
                        continue
                    for full, short, width in aliases:
                        # Full hierarchical path
                        self.name_history[full] = hist
                        self.name_widths[full] = width

                        # Short leaf name: prioritize higher-level scope (shallower hierarchy depth)
                        # e.g. tb_ripple_carry_adder.uut.Cin (depth 3) takes precedence over FA0.cin (depth 4)
                        depth = len(full.split('.'))
                        if short not in self.name_history or depth < short_source_depth.get(short, 999):
                            self.name_history[short] = hist
                            self.name_widths[short] = width
                            short_source_depth[short] = depth
        except Exception as e:
            print(f"[FastVcdTracker] Error parsing {self.path}: {e}")

    def _parse_timescale(self, s):
        s = s.strip().lower()
        # default to 1ps
        if '100fs' in s: return 0.1
        if '10fs' in s: return 0.01
        if '1fs' in s: return 0.001
        if '1ps' in s: return 1.0
        if '10ps' in s: return 10.0
        if '100ps' in s: return 100.0
        if '1ns' in s: return 1000.0
        if '10ns' in s: return 10000.0
        if '100ns' in s: return 100000.0
        if '1us' in s: return 1000000.0
        if '1ms' in s: return 1000000000.0
        return 1.0

    def get_all_values_at_ps(self, time_ps):
        """
        Returns a dict of { name: value_str } for all signals at time_ps,
        properly zero-padded to each net's declared bit-width.
        """
        if not self.name_history:
            return {}
        tick = int(time_ps / self.timescale_mult) if self.timescale_mult > 0 else int(time_ps)
        results = {}
        for name, hist in self.name_history.items():
            if '.' in name: # only collect base/leaf net names for schematic matching
                continue
            idx = bisect.bisect_right(hist, (tick, '\uffff'))
            if idx == 0:
                raw_val = hist[0][1]
            else:
                raw_val = hist[idx - 1][1]
            
            width = self.name_widths.get(name, 1)
            # Pad binary string to net width if multibit and pure 0/1
            if width > 1 and all(c in '01' for c in raw_val):
                val = raw_val.zfill(width)
            else:
                val = raw_val
            results[name] = val
        return results
