#include "SchematicRouter.h"
#include <fstream>
#include <iostream>
#include <algorithm>
#include <cmath>
#include <map>
#include <set>
#include <vector>
#include <string>
#include <queue>
#include <QRectF>
#include <QPointF>
#include <QLineF>
#include "json.hpp"

using json = nlohmann::json;

namespace {
    constexpr float GRID = 16.0f;
    
    float snap(float v) {
        return std::round(v / GRID) * GRID;
    }

    std::string clean_instance_name(const std::string& name) {
        std::string res = name;
        std::replace(res.begin(), res.end(), '\\', '/');
        size_t pos = res.find_last_of('/');
        if (pos != std::string::npos) {
            return res.substr(pos + 1);
        }
        return res;
    }

    struct Port {
        std::string name;
        std::string direction;
        bool is_left;
        float x = 0;
        float y = 0;
        float get_anchor_x(float block_x) const {
            return block_x + x + (is_left ? 0 : 10);
        }
        float get_anchor_y(float block_y) const {
            return block_y + y + 5;
        }
    };

    struct Block {
        std::string raw_name;
        std::string type_name;
        std::string short_id;
        bool is_top;
        float x = 0;
        float y = 0;
        float w = 0;
        float h = 0;
        std::map<std::string, Port> ports;
        
        // For topological sort
        int depth = 0;
        std::vector<Block*> dependencies;

        Block(std::string name, std::string t_name, bool top = false)
            : raw_name(name), type_name(t_name), is_top(top) {
            short_id = clean_instance_name(name);
        }

        void add_port(const std::string& p_name, const std::string& dir, bool left) {
            Port p;
            p.name = p_name;
            p.direction = dir;
            p.is_left = left;
            ports[p_name] = p;
        }

        void layout_ports() {
            std::vector<Port*> left_ports;
            std::vector<Port*> right_ports;
            for (auto& kv : ports) {
                if (kv.second.is_left) left_ports.push_back(&kv.second);
                else right_ports.push_back(&kv.second);
            }
            int max_ports = std::max(left_ports.size(), right_ports.size());
            h = snap(std::max(64.0f, max_ports * 20.0f + 40.0f));
            
            float title_width = short_id.length() * 9.0f; // Approx width
            w = snap(std::max(160.0f, title_width + 40.0f));

            float ly = snap(35.0f);
            for (auto* p : left_ports) {
                p->x = -5.0f;
                p->y = ly;
                ly += snap(20.0f);
            }
            float ry = snap(35.0f);
            for (auto* p : right_ports) {
                p->x = w - 5.0f;
                p->y = ry;
                ry += snap(20.0f);
            }
        }
        
        QRectF sceneBoundingRect() const {
            return QRectF(x, y, w, h);
        }
    };

    struct Segment {
        int uid;
        char type; // 'H' or 'V'
        float x1, x2; // For 'H'
        float y;      // For 'H'
        float x;      // For 'V'
        float y1, y2; // For 'V'
        bool is_pin;
        float x_min, x_max, y_min, y_max;
    };
    
    bool is_keepout_collision(float x1, float y1, float x2, float y2, const QPointF* ignore_pt, float halo, const std::vector<Block*>& all_blocks, size_t num_core_blocks) {
        if (num_core_blocks > 500) return false;
        float sx1 = std::min(x1, x2);
        float sx2 = std::max(x1, x2);
        float sy1 = std::min(y1, y2);
        float sy2 = std::max(y1, y2);
        
        for (const auto* b : all_blocks) {
            QRectF br = b->sceneBoundingRect();
            if (ignore_pt && br.contains(*ignore_pt)) continue;
            
            float bx1 = br.left() - halo;
            float by1 = br.top() - halo;
            float bx2 = br.right() + halo;
            float by2 = br.bottom() + halo;
            
            if (!(sx2 < bx1 || sx1 > bx2 || sy2 < by1 || sy1 > by2)) {
                return true;
            }
        }
        return false;
    }
}

SchematicRouter::SchematicRouter(SchematicViewer* viewer)
    : viewer_(viewer) {
}

void SchematicRouter::parse_and_draw_json(const std::string& json_path, const std::string& target_module, const std::string& mode, int channel_spacing) {
    if (!viewer_) return;
    viewer_->clear();
    
    std::ifstream f(json_path);
    if (!f.is_open()) {
        std::cerr << "Could not open json file: " << json_path << std::endl;
        return;
    }
    
    json data;
    try {
        f >> data;
    } catch (const std::exception& e) {
        std::cerr << "JSON parse error: " << e.what() << std::endl;
        return;
    }

    if (!data.contains("modules") || !data["modules"].contains(target_module)) {
        return;
    }

    auto& mod = data["modules"][target_module];
    
    std::vector<Block> allocated_blocks; // To manage memory
    std::vector<Block*> all_blocks;
    std::vector<Segment> segments;
    std::vector<QPointF> junctions;
    std::vector<int> junction_types;
    
    if (mode == "top") {
        allocated_blocks.emplace_back(target_module, target_module, true);
        Block& block = allocated_blocks.back();
        if (mod.contains("ports")) {
            for (auto it = mod["ports"].begin(); it != mod["ports"].end(); ++it) {
                std::string dir = it.value().value("direction", "input");
                block.add_port(it.key(), dir, dir == "input");
            }
        }
        block.layout_ports();
        all_blocks.push_back(&block);
        
        std::vector<float> b_x, b_y, b_w, b_h;
        std::vector<std::string> b_names, b_types;
        std::vector<bool> b_tops;
        for (auto* b : all_blocks) {
            b_x.push_back(b->x); b_y.push_back(b->y);
            b_w.push_back(b->w); b_h.push_back(b->h);
            b_names.push_back(b->short_id); b_types.push_back(b->type_name);
            b_tops.push_back(b->is_top);
        }
        std::vector<float> p_x, p_y;
        std::vector<std::string> p_names, p_dirs;
        std::vector<bool> p_lefts;
        for (auto* b : all_blocks) {
            for (auto& kv : b->ports) {
                p_x.push_back(b->x + kv.second.x);
                p_y.push_back(b->y + kv.second.y);
                p_names.push_back(kv.second.name);
                p_dirs.push_back(kv.second.direction);
                p_lefts.push_back(kv.second.is_left);
            }
        }
        viewer_->load_blocks(b_x, b_y, b_w, b_h, b_names, b_types, b_tops);
        viewer_->load_ports(p_x, p_y, p_names, p_dirs, p_lefts);
        viewer_->fit_in_view();
        return;
    } 
    else if (mode == "block" || mode == "gate") {
        allocated_blocks.reserve(2000); // Reserve enough to avoid reallocation breaking pointers
        allocated_blocks.emplace_back("INPUTS", "BOUNDARY", true);
        Block* in_boundary = &allocated_blocks.back();
        allocated_blocks.emplace_back("OUTPUTS", "BOUNDARY", true);
        Block* out_boundary = &allocated_blocks.back();
        
        if (mod.contains("ports")) {
            for (auto it = mod["ports"].begin(); it != mod["ports"].end(); ++it) {
                std::string dir = it.value().value("direction", "input");
                if (dir == "input") in_boundary->add_port(it.key(), "output", false);
                else out_boundary->add_port(it.key(), "input", true);
            }
        }
        in_boundary->layout_ports();
        out_boundary->layout_ports();
        
        std::vector<Block*> core_blocks;
        std::map<std::string, Block*> block_map;
        
        if (mod.contains("cells")) {
            for (auto it = mod["cells"].begin(); it != mod["cells"].end(); ++it) {
                std::string c_type = it.value().value("type", "unknown");
                allocated_blocks.emplace_back(it.key(), c_type);
                Block* b = &allocated_blocks.back();
                block_map[it.key()] = b;
                
                if (it.value().contains("port_directions")) {
                    for (auto p_it = it.value()["port_directions"].begin(); p_it != it.value()["port_directions"].end(); ++p_it) {
                        std::string p_dir = p_it.value().get<std::string>();
                        b->add_port(p_it.key(), p_dir, p_dir == "input");
                    }
                }
                b->layout_ports();
                core_blocks.push_back(b);
            }
        }
        
        // Build netlist dependencies for topological sort
        // A block depends on another if it consumes its output
        std::map<std::string, std::vector<Block*>> signal_drivers; // bit -> driver blocks
        
        if (mod.contains("ports")) {
            for (auto it = mod["ports"].begin(); it != mod["ports"].end(); ++it) {
                std::string dir = it.value().value("direction", "input");
                if (dir == "input" && it.value().contains("bits")) {
                    for (auto& bit : it.value()["bits"]) {
                        std::string bit_str = bit.is_number() ? std::to_string(bit.get<int>()) : bit.get<std::string>();
                        signal_drivers[bit_str].push_back(in_boundary);
                    }
                }
            }
        }
        
        for (auto* b : core_blocks) {
            if (mod["cells"].contains(b->raw_name)) {
                auto& c_data = mod["cells"][b->raw_name];
                if (c_data.contains("connections") && c_data.contains("port_directions")) {
                    for (auto it = c_data["connections"].begin(); it != c_data["connections"].end(); ++it) {
                        std::string p_name = it.key();
                        std::string dir = c_data["port_directions"].value(p_name, "input");
                        if (dir == "output") {
                            for (auto& bit : it.value()) {
                                std::string bit_str = bit.is_number() ? std::to_string(bit.get<int>()) : bit.get<std::string>();
                                signal_drivers[bit_str].push_back(b);
                            }
                        }
                    }
                }
            }
        }
        
        for (auto* b : core_blocks) {
            if (mod["cells"].contains(b->raw_name)) {
                auto& c_data = mod["cells"][b->raw_name];
                if (c_data.contains("connections") && c_data.contains("port_directions")) {
                    for (auto it = c_data["connections"].begin(); it != c_data["connections"].end(); ++it) {
                        std::string p_name = it.key();
                        std::string dir = c_data["port_directions"].value(p_name, "input");
                        if (dir == "input") {
                            for (auto& bit : it.value()) {
                                std::string bit_str = bit.is_number() ? std::to_string(bit.get<int>()) : bit.get<std::string>();
                                if (signal_drivers.count(bit_str)) {
                                    for (auto* driver : signal_drivers[bit_str]) {
                                        if (driver != b) { // Avoid self loops
                                            b->dependencies.push_back(driver);
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        
        all_blocks.push_back(in_boundary);
        all_blocks.push_back(out_boundary);
        for (auto* b : core_blocks) all_blocks.push_back(b);

        // Force-Directed Physics Placement
        float canvas_size = std::max(2000.0f, std::sqrt((float)core_blocks.size()) * 1200.0f);
        for (auto* b : core_blocks) {
            b->x = (rand() % (int)canvas_size);
            b->y = (rand() % (int)canvas_size);
        }
        in_boundary->x = 0; in_boundary->y = canvas_size / 2.0f;
        out_boundary->x = canvas_size; out_boundary->y = canvas_size / 2.0f;

        float K = 0.05f;
        float C = 5000000.0f;

        for (int iter = 0; iter < 500; ++iter) {
            std::map<Block*, std::pair<float, float>> forces;
            for (auto* b : all_blocks) forces[b] = {0.0f, 0.0f};

            // Repulsion
            for (size_t i = 0; i < all_blocks.size(); ++i) {
                for (size_t j = i + 1; j < all_blocks.size(); ++j) {
                    Block* b1 = all_blocks[i];
                    Block* b2 = all_blocks[j];
                    float dx = b1->x - b2->x;
                    float dy = b1->y - b2->y;
                    float dist_sq = dx*dx + dy*dy;
                    if (dist_sq < 1.0f) dist_sq = 1.0f;
                    float dist = std::sqrt(dist_sq);
                    float force = C / dist_sq;
                    float fx = force * (dx / dist);
                    float fy = force * (dy / dist);

                    forces[b1].first += fx;
                    forces[b1].second += fy;
                    forces[b2].first -= fx;
                    forces[b2].second -= fy;
                }
            }

            // Attraction
            for (auto* b : core_blocks) {
                for (auto* dep : b->dependencies) {
                    float dx = dep->x - b->x;
                    float dy = dep->y - b->y;
                    float dist = std::sqrt(dx*dx + dy*dy);
                    if (dist < 1.0f) dist = 1.0f;
                    float force = K * dist;
                    float fx = force * (dx / dist);
                    float fy = force * (dy / dist);

                    forces[b].first += fx;
                    forces[b].second += fy;
                    forces[dep].first -= fx;
                    forces[dep].second -= fy;
                }
            }

            // Flow Anchor
            forces[in_boundary].first += 0.5f * (0.0f - in_boundary->x);
            forces[in_boundary].second += 0.5f * ((canvas_size / 2.0f) - in_boundary->y);
            forces[out_boundary].first += 0.5f * (canvas_size - out_boundary->x);
            forces[out_boundary].second += 0.5f * ((canvas_size / 2.0f) - out_boundary->y);

            for (auto* b : core_blocks) {
                forces[b].first += 5.0f; // Gently to the right
            }

            // Update
            for (auto* b : all_blocks) {
                b->x += forces[b].first * 0.1f;
                b->y += forces[b].second * 0.1f;
            }
        }

        // Snap to grid
        for (auto* b : all_blocks) {
            b->x = snap(b->x);
            b->y = snap(b->y);
        }
        
        // --- ROUTING ---
        struct SrcData { std::set<std::pair<float, float>> sinks; std::vector<std::string> bits; };
        struct Interval { float min_val, max_val; int uid; };
        
        std::map<int, bool> uid_is_bus;
        std::map<const Segment*, std::vector<float>> v_crossings;
        std::map<std::pair<std::pair<float, float>, std::vector<std::pair<float, float>>>, std::vector<std::string>> route_groups;
        
        segments.clear();
        junctions.clear();
        junction_types.clear();
        uid_is_bus.clear();
        v_crossings.clear();
        route_groups.clear();
        
        std::map<std::pair<float, float>, SrcData> _src_map;
        std::map<std::string, QPointF> bit_sources;
        std::map<std::string, std::vector<QPointF>> bit_sinks;
            
        if (mod.contains("ports")) {
            for (auto it = mod["ports"].begin(); it != mod["ports"].end(); ++it) {
                std::string dir = it.value().value("direction", "input");
                if (it.value().contains("bits")) {
                    for (auto& bit : it.value()["bits"]) {
                        std::string bit_str = bit.is_number() ? std::to_string(bit.get<int>()) : bit.get<std::string>();
                        if (dir == "input") {
                            auto& pt = in_boundary->ports[it.key()];
                            bit_sources[bit_str] = QPointF(snap(pt.get_anchor_x(in_boundary->x)), snap(pt.get_anchor_y(in_boundary->y)));
                        } else {
                            auto& pt = out_boundary->ports[it.key()];
                            bit_sinks[bit_str].push_back(QPointF(snap(pt.get_anchor_x(out_boundary->x)), snap(pt.get_anchor_y(out_boundary->y))));
                        }
                    }
                }
            }
        }
            
        for (auto* b : core_blocks) {
            if (mod["cells"].contains(b->raw_name)) {
                auto& c_data = mod["cells"][b->raw_name];
                if (c_data.contains("connections") && c_data.contains("port_directions")) {
                    for (auto it = c_data["connections"].begin(); it != c_data["connections"].end(); ++it) {
                        std::string p_name = it.key();
                        std::string dir = c_data["port_directions"].value(p_name, "input");
                        if (b->ports.count(p_name)) {
                            auto& pt = b->ports[p_name];
                            QPointF anchor(snap(pt.get_anchor_x(b->x)), snap(pt.get_anchor_y(b->y)));
                            for (auto& bit : it.value()) {
                                std::string bit_str = bit.is_number() ? std::to_string(bit.get<int>()) : bit.get<std::string>();
                                if (dir == "output") bit_sources[bit_str] = anchor;
                                else bit_sinks[bit_str].push_back(anchor);
                            }
                        }
                    }
                }
            }
        }
            
        float min_y = 1e9, max_y = -1e9;
        for (auto* b : all_blocks) {
            min_y = std::min(min_y, b->y);
            max_y = std::max(max_y, b->y + b->h);
        }
            
        for (auto& kv : bit_sources) {
            auto src_key = std::make_pair(kv.second.x(), kv.second.y());
            _src_map[src_key].bits.push_back(kv.first);
            for (auto& s : bit_sinks[kv.first]) {
                _src_map[src_key].sinks.insert({s.x(), s.y()});
            }
        }
            
        for (auto& kv : _src_map) {
            std::vector<std::pair<float, float>> sink_keys(kv.second.sinks.begin(), kv.second.sinks.end());
            std::sort(sink_keys.begin(), sink_keys.end());
            route_groups[{kv.first, sink_keys}] = kv.second.bits;
        }
            
        std::map<float, std::vector<Interval>> occupied_h_lanes;
        std::map<float, std::vector<Interval>> occupied_v_lanes;
            
        auto is_h_lane_free = [&](float y, float x1, float x2, int cur_uid) {
            float x_min = std::min(x1, x2);
            float x_max = std::max(x1, x2);
            auto it_low = occupied_h_lanes.lower_bound(y - (GRID - 2));
            auto it_high = occupied_h_lanes.upper_bound(y + (GRID - 2));
            for (auto it = it_low; it != it_high; ++it) {
                for (const auto& iv : it->second) {
                    if (iv.uid != cur_uid && !(x_max < iv.min_val || x_min > iv.max_val)) return false;
                }
            }
            return true;
        };

        auto is_v_lane_free = [&](float x, float y1, float y2, int cur_uid) {
            float y_min = std::min(y1, y2);
            float y_max = std::max(y1, y2);
            auto it_low = occupied_v_lanes.lower_bound(x - (GRID - 2));
            auto it_high = occupied_v_lanes.upper_bound(x + (GRID - 2));
            for (auto it = it_low; it != it_high; ++it) {
                for (const auto& iv : it->second) {
                    if (iv.uid != cur_uid && !(y_max < iv.min_val || y_min > iv.max_val)) return false;
                }
            }
            return true;
        };

        auto add_h_seg = [&](int cur_uid, float x1, float x2, float y, bool is_pin) {
            if (std::abs(x1 - x2) < 0.1f) return;
            segments.push_back({cur_uid, 'H', x1, x2, y, 0, 0, 0, is_pin, std::min(x1, x2), std::max(x1, x2), y, y});
            occupied_h_lanes[y].push_back({std::min(x1, x2), std::max(x1, x2), cur_uid});
        };

        auto add_v_seg = [&](int cur_uid, float x, float y1, float y2, bool is_pin) {
            if (std::abs(y1 - y2) < 0.1f) return;
            segments.push_back({cur_uid, 'V', 0, 0, 0, x, y1, y2, is_pin, x, x, std::min(y1, y2), std::max(y1, y2)});
            occupied_v_lanes[x].push_back({std::min(y1, y2), std::max(y1, y2), cur_uid});
        };

        auto find_free_v_lane = [&](float pref_x, float y1, float y2, int cur_uid) {
            float x = pref_x;
            int step = 1;
            const int MAX_STEPS = 6;
            while (!is_v_lane_free(x, y1, y2, cur_uid)) {
                float offset_val = std::floor(step / 2.0f + 0.5f) * GRID;
                if (step % 2 != 0) x = pref_x - offset_val;
                else x = pref_x + offset_val;
                step++;
                
                if (step > MAX_STEPS) {
                    int crowd_left = 0, crowd_right = 0;
                    for (int i = 1; i <= 5; i++) {
                        if (!is_v_lane_free(pref_x - i * GRID, y1, y2, cur_uid)) crowd_left++;
                        if (!is_v_lane_free(pref_x + i * GRID, y1, y2, cur_uid)) crowd_right++;
                    }
                    if (crowd_left <= crowd_right) {
                        pref_x -= 5 * GRID;
                    } else {
                        pref_x += 5 * GRID;
                    }
                    x = pref_x;
                    step = 1;
                }
            }
            return x;
        };

        auto find_free_h_lane = [&](float pref_y, float x1, float x2, int cur_uid) {
            float y = pref_y;
            int step = 1;
            const int MAX_STEPS = 6;
            while (!is_h_lane_free(y, x1, x2, cur_uid)) {
                float offset_val = std::floor(step / 2.0f + 0.5f) * GRID;
                if (step % 2 != 0) y = pref_y - offset_val;
                else y = pref_y + offset_val;
                step++;
                
                if (step > MAX_STEPS) {
                    int crowd_up = 0, crowd_down = 0;
                    for (int i = 1; i <= 5; i++) {
                        if (!is_h_lane_free(pref_y - i * GRID, x1, x2, cur_uid)) crowd_up++;
                        if (!is_h_lane_free(pref_y + i * GRID, x1, x2, cur_uid)) crowd_down++;
                    }
                    if (crowd_up <= crowd_down) {
                        pref_y -= 5 * GRID;
                    } else {
                        pref_y += 5 * GRID;
                    }
                    y = pref_y;
                    step = 1;
                }
            }
            return y;
        };

        int uid = 0;
        float global_up = snap(min_y - 100.0f);
        float global_down = snap(max_y + 100.0f);
        
        for (auto& kv : route_groups) {
            uid++;
            uid_is_bus[uid] = kv.second.size() > 1;
            QPointF src(kv.first.first.first, kv.first.first.second);
            std::vector<QPointF> sinks;
            for (auto& sk : kv.first.second) sinks.push_back(QPointF(sk.first, sk.second));
            
            if (sinks.empty()) continue;
            
            // Check if any sink is backward
            bool has_forward = false;
            bool has_backward = false;
            float max_forward_x = src.x();
            
            for (auto& sink : sinks) {
                if (sink.x() <= src.x()) has_backward = true;
                else {
                    has_forward = true;
                    if (sink.x() > max_forward_x) max_forward_x = sink.x();
                }
            }
            
            float trunk_y = src.y();
            float trunk_start_x = src.x();
            float trunk_end_x = snap(max_forward_x - 3 * GRID);
            if (trunk_end_x < trunk_start_x + GRID) trunk_end_x = trunk_start_x + GRID;
            
            if (has_forward) {
                add_h_seg(uid, trunk_start_x, trunk_end_x, trunk_y, false);
            }
            
            for (size_t sink_idx = 0; sink_idx < sinks.size(); ++sink_idx) {
                QPointF sink = sinks[sink_idx];
                
                if (sink.x() > src.x()) {
                    // Forward route: Orthogonal tap
                    float pref_tap_x = snap(sink.x() - 3 * GRID);
                    if (pref_tap_x < src.x() + GRID) pref_tap_x = snap(src.x() + GRID);
                    
                    float tap_x = find_free_v_lane(pref_tap_x, trunk_y, sink.y(), uid);
                    
                    add_h_seg(uid, trunk_start_x, tap_x, trunk_y, false);
                    add_v_seg(uid, tap_x, trunk_y, sink.y(), false);
                    add_h_seg(uid, tap_x, sink.x(), sink.y(), true);
                } else {
                    // Feedback loop: Route up/down to global highway
                    float pref_h_way = (uid % 2 == 0) ? global_up : global_down;
                    
                    float pref_up_tap_x = snap(src.x() + 2 * GRID);
                    float pref_down_tap_x = snap(sink.x() - 3 * GRID);
                    
                    float up_tap_x = find_free_v_lane(pref_up_tap_x, src.y(), pref_h_way, uid);
                    float down_tap_x = find_free_v_lane(pref_down_tap_x, pref_h_way, sink.y(), uid);
                    float h_way = find_free_h_lane(pref_h_way, up_tap_x, down_tap_x, uid);
                    
                    add_h_seg(uid, src.x(), up_tap_x, src.y(), false);
                    add_v_seg(uid, up_tap_x, src.y(), h_way, false);
                    add_h_seg(uid, up_tap_x, down_tap_x, h_way, false);
                    add_v_seg(uid, down_tap_x, h_way, sink.y(), false);
                    add_h_seg(uid, down_tap_x, sink.x(), sink.y(), true);
                }
            }
        }
        

        for (const auto& h : segments) {
            if (h.type != 'H') continue;
            for (const auto& v : segments) {
                if (v.type != 'V') continue;
                float ix = v.x, iy = h.y;
                if (ix >= h.x_min && ix <= h.x_max && iy >= v.y_min && iy <= v.y_max) {
                    bool h_is_bus = uid_is_bus[h.uid];
                    bool v_is_bus = uid_is_bus[v.uid];
                    int j_type = 0; // 0: wire-wire, 1: bus-bus, 2: wire-bus
                    if (h_is_bus && v_is_bus) j_type = 1;
                    else if (h_is_bus || v_is_bus) j_type = 2;

                    if (h.uid == v.uid) {
                        if (!(std::abs(ix - h.x1) < 1.0f || std::abs(ix - h.x2) < 1.0f) || 
                            !(std::abs(iy - v.y1) < 1.0f || std::abs(iy - v.y2) < 1.0f)) {
                            junctions.push_back(QPointF(ix, iy));
                            junction_types.push_back(j_type);
                        }
                    } else {
                        bool h_endpoint = (std::abs(ix - h.x1) < 1.0f || std::abs(ix - h.x2) < 1.0f);
                        bool v_endpoint = (std::abs(iy - v.y1) < 1.0f || std::abs(iy - v.y2) < 1.0f);
                        if (h_endpoint || v_endpoint) {
                            junctions.push_back(QPointF(ix, iy));
                            junction_types.push_back(j_type);
                        } else {
                            if (ix > h.x_min && ix < h.x_max && iy > v.y_min && iy < v.y_max) {
                                v_crossings[&v].push_back(iy);
                            }
                        }
                    }
                }
            }
        }

        // LOAD TO VIEWER
        std::vector<float> b_x, b_y, b_w, b_h;
        std::vector<std::string> b_names, b_types;
        std::vector<bool> b_tops;
        for (auto* b : all_blocks) {
            b_x.push_back(b->x); b_y.push_back(b->y);
            b_w.push_back(b->w); b_h.push_back(b->h);
            b_names.push_back(b->short_id); b_types.push_back(b->type_name);
            b_tops.push_back(b->is_top);
        }
        
        std::vector<float> p_x, p_y;
        std::vector<std::string> p_names, p_dirs;
        std::vector<bool> p_lefts;
        for (auto* b : all_blocks) {
            for (auto& kv : b->ports) {
                p_x.push_back(b->x + kv.second.x);
                p_y.push_back(b->y + kv.second.y);
                p_names.push_back(kv.second.name);
                p_dirs.push_back(kv.second.direction);
                p_lefts.push_back(kv.second.is_left);
            }
        }
        
        std::vector<float> d_x, d_y;
        std::vector<std::string> d_text;
        for (auto& kv : route_groups) {
            d_x.push_back(kv.first.first.first);
            d_y.push_back(kv.first.first.second);
            d_text.push_back("[" + std::to_string(kv.second.size()) + "]");
            for (auto& sk : kv.first.second) {
                d_x.push_back(sk.first);
                d_y.push_back(sk.second);
                d_text.push_back("");
            }
        }
        
        std::vector<float> j_x, j_y;
        for (auto& pt : junctions) {
            j_x.push_back(pt.x());
            j_y.push_back(pt.y());
        }
        
        std::vector<float> w_x1, w_y1, w_x2, w_y2;
        std::vector<bool> w_bus, w_gap;
        for (auto& seg : segments) {
            bool is_bus = uid_is_bus[seg.uid];
            if (seg.type == 'H') {
                w_x1.push_back(seg.x1); w_y1.push_back(seg.y);
                w_x2.push_back(seg.x2); w_y2.push_back(seg.y);
                w_bus.push_back(is_bus); w_gap.push_back(false);
            } else {
                std::vector<float> cross_ys = v_crossings[&seg];
                float start_y = seg.y1, end_y = seg.y2;
                float dir = end_y > start_y ? 1.0f : -1.0f;
                std::sort(cross_ys.begin(), cross_ys.end(), [dir](float a, float b){ return a * dir < b * dir; });
                
                float curr_y = start_y;
                for (float cy : cross_ys) {
                    if (std::abs(cy - start_y) < 5.0f || std::abs(cy - end_y) < 5.0f) continue;
                    float hop_start = cy - (4.0f * dir);
                    float hop_end = cy + (4.0f * dir);
                    
                    w_x1.push_back(seg.x); w_y1.push_back(curr_y);
                    w_x2.push_back(seg.x); w_y2.push_back(hop_start);
                    w_bus.push_back(is_bus); w_gap.push_back(false);
                    
                    w_x1.push_back(seg.x); w_y1.push_back(hop_start);
                    w_x2.push_back(seg.x); w_y2.push_back(hop_end);
                    w_bus.push_back(is_bus); w_gap.push_back(true);
                    
                    curr_y = hop_end;
                }
                w_x1.push_back(seg.x); w_y1.push_back(curr_y);
                w_x2.push_back(seg.x); w_y2.push_back(end_y);
                w_bus.push_back(is_bus); w_gap.push_back(false);
            }
        }
        
        viewer_->load_blocks(b_x, b_y, b_w, b_h, b_names, b_types, b_tops);
        viewer_->load_ports(p_x, p_y, p_names, p_dirs, p_lefts);
        viewer_->load_junctions(j_x, j_y, junction_types);
        viewer_->load_dots(d_x, d_y, d_text);
        viewer_->load_wires(w_x1, w_y1, w_x2, w_y2, w_bus, w_gap);
        viewer_->fit_in_view();
    }
}
