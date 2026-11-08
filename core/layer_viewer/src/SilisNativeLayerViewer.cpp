// ==============================================================================
// Silis Native Layer Viewer Canvas
//
// Heartfelt compliments, tribute, and attribution to the incredible OpenROAD
// Project community and contributors (The OpenROAD Authors / Precision Innovations).
// Based on and inspired by the battle-tested architecture and visual precision
// of OpenROAD's LayoutViewer (layoutViewer.cpp / displayControls.cpp).
// ==============================================================================

#include "SilisNativeLayerViewer.h"
#include <QPainter>
#include <QPaintEvent>
#include <QWheelEvent>
#include <QMouseEvent>
#include <QFontDatabase>
#include <QApplication>
#include <algorithm>
#include <cmath>

SilisNativeLayerViewer::SilisNativeLayerViewer(QWidget* parent)
    : QWidget(parent) {
    setAttribute(Qt::WA_OpaquePaintEvent);
    setAttribute(Qt::WA_NoSystemBackground);
    setMouseTracking(true);

    // Exact OpenROAD default color palette (from DisplayControls::techInit)
    // Seeded with VRL Brown palette: #00F, #F00, #0D0, etc.
    layer_colors_["li1"]  = QColor(126, 126, 255, 180); // Cut 0 / local interconnect
    layer_colors_["met1"] = QColor(0, 0, 254, 180);     // Metal 1 (Pure Deep Blue)
    layer_colors_["via"]  = QColor(255, 126, 126, 190); // Cut via (mcon/via)
    layer_colors_["met2"] = QColor(254, 0, 0, 180);     // Metal 2 (Pure Bright Red)
    layer_colors_["via2"] = QColor(255, 180, 126, 190); // Cut via2
    layer_colors_["met3"] = QColor(9, 221, 0, 180);     // Metal 3 (Vibrant Green)
    layer_colors_["via3"] = QColor(126, 255, 180, 190); // Cut via3
    layer_colors_["met4"] = QColor(190, 244, 81, 180);   // Metal 4 (Lime Yellow-Green)
    layer_colors_["via4"] = QColor(255, 255, 126, 190); // Cut via4
    layer_colors_["met5"] = QColor(222, 33, 96, 180);    // Metal 5 (Deep Rose / Magenta)
    layer_colors_["vias"] = QColor(255, 126, 126, 190); // Cut vias alias

    // Explicit GF180MCU layer name aliases
    layer_colors_["Metal1"] = QColor(0, 0, 254, 180);
    layer_colors_["Metal2"] = QColor(254, 0, 0, 180);
    layer_colors_["Metal3"] = QColor(9, 221, 0, 180);
    layer_colors_["Metal4"] = QColor(190, 244, 81, 180);
    layer_colors_["Metal5"] = QColor(222, 33, 96, 180);
    layer_colors_["Via1"]   = QColor(255, 126, 126, 190);
    layer_colors_["Via2"]   = QColor(255, 126, 126, 190);
    layer_colors_["Via3"]   = QColor(255, 126, 126, 190);
    layer_colors_["Via4"]   = QColor(255, 126, 126, 190);

    // Explicit ASAP7 layer name aliases
    layer_colors_["M1"]   = QColor(0, 0, 254, 180);
    layer_colors_["M2"]   = QColor(254, 0, 0, 180);
    layer_colors_["M3"]   = QColor(9, 221, 0, 180);
    layer_colors_["M4"]   = QColor(190, 244, 81, 180);
    layer_colors_["M5"]   = QColor(222, 33, 96, 180);
    layer_colors_["VIA1"] = QColor(255, 126, 126, 190);
    layer_colors_["VIA2"] = QColor(255, 126, 126, 190);
    layer_colors_["VIA3"] = QColor(255, 126, 126, 190);

    // Default: all layers visible
    for (auto& kv : layer_colors_) {
        layer_visible_[kv.first] = true;
    }
}

void SilisNativeLayerViewer::clear() {
    layers_.clear();
    instances_.clear();
    inst_name_index_.clear();
    selected_inst_name_.clear();
    selected_rect_ = QRectF();
    multi_selected_rects_.clear();
    power_rails_.clear();
    selected_power_net_.clear();
    selected_power_rects_.clear();
    flightlines_.clear();
    rubber_band_ = QRect();
    rubber_band_showing_ = false;
    clear_ruler();
    update();
}

void SilisNativeLayerViewer::set_core(float x, float y, float w, float h) {
    core_rect_ = QRectF(x, y, w, h);
    fit_in_view();
}

void SilisNativeLayerViewer::set_dbu(float dbu) {
    if (dbu > 0.0f) dbu_ = dbu;
}

void SilisNativeLayerViewer::load_layer_shapes(const std::string& layer_name,
                                              const std::vector<float>& x,
                                              const std::vector<float>& y,
                                              const std::vector<float>& w,
                                              const std::vector<float>& h) {
    size_t count = std::min({x.size(), y.size(), w.size(), h.size()});
    std::vector<LayerShape>& shapes = layers_[layer_name];
    shapes.resize(count);
    for (size_t i = 0; i < count; ++i) {
        shapes[i] = {x[i], y[i], w[i], h[i]};
    }
    update();
}

void SilisNativeLayerViewer::load_power_rails(const std::vector<float>& x,
                                           const std::vector<float>& y,
                                           const std::vector<float>& w,
                                           const std::vector<float>& h,
                                           const std::vector<std::string>& net_names,
                                           const std::vector<std::string>& layer_names) {
    size_t count = std::min({x.size(), y.size(), w.size(), h.size(), net_names.size()});
    power_rails_.clear();
    power_rails_.reserve(count);
    for (size_t i = 0; i < count; ++i) {
        PowerRailSegment seg;
        seg.rect = QRectF(x[i], y[i], w[i], h[i]);
        seg.net_name = net_names[i];
        seg.layer_name = (i < layer_names.size()) ? layer_names[i] : "";
        power_rails_.push_back(seg);
    }
    update();
}

void SilisNativeLayerViewer::set_layer_visible(const std::string& layer_name, bool visible) {
    layer_visible_[layer_name] = visible;
    update();
}

void SilisNativeLayerViewer::set_all_layers_visible(bool visible) {
    for (auto& kv : layer_visible_) {
        kv.second = visible;
    }
    update();
}

void SilisNativeLayerViewer::load_instances(const std::vector<float>& x,
                                           const std::vector<float>& y,
                                           const std::vector<float>& w,
                                           const std::vector<float>& h,
                                           const std::vector<std::string>& names,
                                           const std::vector<std::string>& masters,
                                           const std::vector<bool>& is_macro,
                                           const std::vector<int>& categories) {
    size_t count = std::min({x.size(), y.size(), w.size(), h.size(), names.size()});
    instances_.clear();
    inst_name_index_.clear();
    instances_.reserve(count);

    for (size_t i = 0; i < count; ++i) {
        PlacedInst inst;
        inst.rect = QRectF(x[i], y[i], w[i], h[i]);
        inst.name = names[i];
        inst.master = (i < masters.size()) ? masters[i] : "";
        inst.is_macro = (i < is_macro.size()) ? is_macro[i] : false;
        if (i < categories.size()) {
            inst.category = categories[i];
        } else {
            inst.category = inst.is_macro ? 1 : 0;
        }
        inst_name_index_[names[i]] = instances_.size();
        instances_.push_back(inst);
    }
    update();
}

void SilisNativeLayerViewer::set_power_cells_visible(bool visible) {
    show_power_cells_ = visible;
    update();
}

void SilisNativeLayerViewer::set_std_cells_visible(bool visible) {
    show_std_cells_ = visible;
    update();
}

void SilisNativeLayerViewer::set_macros_visible(bool visible) {
    show_macros_ = visible;
    update();
}

void SilisNativeLayerViewer::select_instance(const std::string& name) {
    selected_inst_name_ = name;
    multi_selected_rects_.clear();
    selected_power_net_.clear();
    selected_power_rects_.clear();
    auto it = inst_name_index_.find(name);
    if (it != inst_name_index_.end()) {
        selected_rect_ = instances_[it->second].rect;
    } else {
        selected_rect_ = QRectF();
    }
    update();
}

void SilisNativeLayerViewer::select_instances(const std::vector<std::string>& names) {
    selected_inst_name_.clear();
    selected_rect_ = QRectF();
    multi_selected_rects_.clear();
    selected_power_net_.clear();
    selected_power_rects_.clear();
    for (const auto& name : names) {
        auto it = inst_name_index_.find(name);
        if (it != inst_name_index_.end()) {
            multi_selected_rects_.push_back(instances_[it->second].rect);
        }
    }
    if (!multi_selected_rects_.empty()) {
        selected_rect_ = multi_selected_rects_.front();
        if (!names.empty()) selected_inst_name_ = names.front();
    }
    update();
}

void SilisNativeLayerViewer::select_power_net(const std::string& net_name) {
    selected_inst_name_.clear();
    selected_rect_ = QRectF();
    multi_selected_rects_.clear();
    selected_power_net_ = net_name;
    selected_power_rects_.clear();
    for (const auto& pr : power_rails_) {
        if (pr.net_name == net_name) {
            selected_power_rects_.push_back(pr.rect);
        }
    }
    update();
}

void SilisNativeLayerViewer::clear_selection() {
    selected_inst_name_.clear();
    selected_rect_ = QRectF();
    multi_selected_rects_.clear();
    selected_power_net_.clear();
    selected_power_rects_.clear();
    clear_flightlines();
    update();
}

void SilisNativeLayerViewer::set_flightlines(const std::vector<float>& x1,
                                            const std::vector<float>& y1,
                                            const std::vector<float>& x2,
                                            const std::vector<float>& y2) {
    size_t count = std::min({x1.size(), y1.size(), x2.size(), y2.size()});
    flightlines_.clear();
    flightlines_.reserve(count);
    for (size_t i = 0; i < count; ++i) {
        flightlines_.push_back({x1[i], y1[i], x2[i], y2[i]});
    }
    update();
}

void SilisNativeLayerViewer::clear_flightlines() {
    flightlines_.clear();
    update();
}

void SilisNativeLayerViewer::fit_in_view() {
    if (core_rect_.isNull() || width() <= 0 || height() <= 0) return;
    double scale_x = (width() * 0.90) / core_rect_.width();
    double scale_y = (height() * 0.90) / core_rect_.height();
    zoom_factor_ = std::min(scale_x, scale_y);
    pan_offset_ = QPointF(0, 0);
    update();
}

void SilisNativeLayerViewer::pan_to(float x, float y, float target_zoom) {
    if (target_zoom > 0.0f) zoom_factor_ = target_zoom;
    pan_offset_.setX(core_rect_.center().x() - x);
    pan_offset_.setY(core_rect_.center().y() - y);
    update();
}

void SilisNativeLayerViewer::zoom_to_box(const QRectF& dbu_box) {
    if (dbu_box.width() <= 0 || dbu_box.height() <= 0 || width() <= 0 || height() <= 0) return;
    double scale_x = (width() * 0.90) / dbu_box.width();
    double scale_y = (height() * 0.90) / dbu_box.height();
    zoom_factor_ = std::min(scale_x, scale_y);
    pan_offset_.setX(core_rect_.center().x() - dbu_box.center().x());
    pan_offset_.setY(core_rect_.center().y() - dbu_box.center().y());
    update();
}

void SilisNativeLayerViewer::set_ruler_active(bool active) {
    ruler_active_ = active;
    if (!active) clear_ruler();
    setCursor(active ? Qt::CrossCursor : Qt::ArrowCursor);
}

void SilisNativeLayerViewer::clear_ruler() {
    ruler_has_start_ = false;
    update();
}

QPointF SilisNativeLayerViewer::screen_to_world(const QPointF& screen_pt) const {
    double center_x = width() / 2.0;
    double center_y = height() / 2.0;
    double wx = (screen_pt.x() - center_x) / zoom_factor_ - pan_offset_.x() + core_rect_.center().x();
    double wy = -(screen_pt.y() - center_y) / zoom_factor_ - pan_offset_.y() + core_rect_.center().y();
    return QPointF(wx, wy);
}

QPointF SilisNativeLayerViewer::world_to_screen(const QPointF& world_pt) const {
    double center_x = width() / 2.0;
    double center_y = height() / 2.0;
    double sx = (world_pt.x() - core_rect_.center().x() + pan_offset_.x()) * zoom_factor_ + center_x;
    double sy = -(world_pt.y() - core_rect_.center().y() + pan_offset_.y()) * zoom_factor_ + center_y;
    return QPointF(sx, sy);
}

void SilisNativeLayerViewer::paintEvent(QPaintEvent* /*event*/) {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing, false);

    // Exact OpenROAD Canvas Background: Deep Pitch Black (#000000)
    p.fillRect(rect(), QColor(0, 0, 0));

    if (core_rect_.isNull()) {
        p.setPen(QColor(120, 120, 120));
        p.drawText(rect(), Qt::AlignCenter, "OpenROAD Native Layout Viewer\nNo DEF / LEF Layout Loaded");
        return;
    }

    // Viewport transform
    p.save();
    p.translate(width() / 2.0, height() / 2.0);
    p.scale(zoom_factor_, -zoom_factor_);
    p.translate(-core_rect_.center().x() + pan_offset_.x(),
                -core_rect_.center().y() + pan_offset_.y());

    // 1. Draw Die / Core Boundary
    p.setPen(QPen(QColor(100, 100, 100), 1.0 / zoom_factor_));
    p.setBrush(QColor(10, 10, 10));
    p.drawRect(core_rect_);

    // Screen bounds in DBU world coordinates for viewport culling
    double view_half_w = (width() / 2.0) / zoom_factor_;
    double view_half_h = (height() / 2.0) / zoom_factor_;
    double cx = core_rect_.center().x() - pan_offset_.x();
    double cy = core_rect_.center().y() - pan_offset_.y();
    double min_x = cx - view_half_w;
    double max_x = cx + view_half_w;
    double min_y = cy - view_half_h;
    double max_y = cy + view_half_h;

    // 2. Render Placed Macros, Power Cells & Standard Cells (OpenROAD style outlines)
    double min_cell_dim = 1.0 / zoom_factor_;

    // 2a. Draw Standard Logic Cells (Steel Blue)
    if (show_std_cells_) {
        p.setPen(QPen(QColor(80, 140, 200, 160), 1.0 / zoom_factor_));
        p.setBrush(QColor(40, 90, 140, 60));
        for (const auto& inst : instances_) {
            if (inst.is_macro || inst.category == 2) continue;
            // Viewport frustum culling
            if (inst.rect.right() < min_x || inst.rect.left() > max_x ||
                inst.rect.top() < min_y || inst.rect.bottom() > max_y) continue;
            if (inst.rect.width() >= min_cell_dim || inst.rect.height() >= min_cell_dim) {
                p.drawRect(inst.rect);
            }
        }
    }

    // 2b. Draw Power Category Cells: tapcell, welltap, decap, power_switch, level_shifter (Vivid Amber / Gold)
    if (show_power_cells_) {
        p.setPen(QPen(QColor(245, 190, 30, 220), 1.0 / zoom_factor_));
        p.setBrush(QColor(210, 145, 20, 170));
        for (const auto& inst : instances_) {
            if (inst.category == 2) {
                // Viewport frustum culling
                if (inst.rect.right() < min_x || inst.rect.left() > max_x ||
                    inst.rect.top() < min_y || inst.rect.bottom() > max_y) continue;
                if (inst.rect.width() >= min_cell_dim || inst.rect.height() >= min_cell_dim) {
                    p.drawRect(inst.rect);
                }
            }
        }
    }

    // 2c. Draw Macros (OpenROAD style orange-brown blocks)
    if (show_macros_) {
        for (const auto& inst : instances_) {
            if (!inst.is_macro && inst.category != 1) continue;
            // Viewport frustum culling
            if (inst.rect.right() < min_x || inst.rect.left() > max_x ||
                inst.rect.top() < min_y || inst.rect.bottom() > max_y) continue;
            p.setPen(QPen(QColor(230, 130, 20), 1.5 / zoom_factor_));
            p.setBrush(QColor(60, 40, 20, 180));
            p.drawRect(inst.rect);
        }
    }

    // 3. Render Metal & Via Layers in Authentic OpenROAD Stacking Order
    std::vector<std::string> render_order = {
        "nwell", "pwell", "li1", "vias",
        "met1", "via", "met2", "via2", "met3", "via3", "met4", "via4", "met5",
        "Metal1", "Via1", "Metal2", "Via2", "Metal3", "Via3", "Metal4", "Via4", "Metal5",
        "M1", "VIA1", "M2", "VIA2", "M3", "VIA3", "M4", "VIA4", "M5"
    };
    // Append any dynamically loaded layers not already in render_order
    for (const auto& kv : layers_) {
        if (std::find(render_order.begin(), render_order.end(), kv.first) == render_order.end()) {
            render_order.push_back(kv.first);
        }
    }

    // Default layer colors for generic PDKs
    static const std::vector<QColor> fallback_palette = {
        QColor(0, 0, 254, 180),     // Blue (M1)
        QColor(254, 0, 0, 180),     // Red (M2)
        QColor(9, 221, 0, 180),     // Green (M3)
        QColor(190, 244, 81, 180),  // Yellow-Green (M4)
        QColor(222, 33, 96, 180),   // Magenta (M5)
        QColor(255, 126, 126, 190)  // Vias
    };
    double min_screen_dim = 1.0 / zoom_factor_; // Shapes smaller than 1px screen space are culled

    for (const auto& lname : render_order) {
        auto it_vis = layer_visible_.find(lname);
        if (it_vis != layer_visible_.end() && !it_vis->second) continue;

        auto it_layer = layers_.find(lname);
        if (it_layer == layers_.end() || it_layer->second.empty()) continue;

        QColor color;
        auto it_col = layer_colors_.find(lname);
        if (it_col != layer_colors_.end()) {
            color = it_col->second;
        } else {
            // Hash layer name deterministically to fallback palette
            size_t h_idx = std::hash<std::string>{}(lname) % fallback_palette.size();
            color = fallback_palette[h_idx];
        }
        p.setPen(Qt::NoPen);
        p.setBrush(color);

        for (const auto& s : it_layer->second) {
            // Viewport frustum culling
            if (s.x + s.w < min_x || s.x > max_x || s.y + s.h < min_y || s.y > max_y) continue;

            // Draw shape, ensuring minimum 1px visible footprint on canvas so sub-micron vias/cuts remain visible
            double sw = std::max(static_cast<double>(s.w), 1.0 / zoom_factor_);
            double sh = std::max(static_cast<double>(s.h), 1.0 / zoom_factor_);
            p.drawRect(QRectF(s.x, s.y, sw, sh));
        }
    }

    // 4. Render Flightlines (Net connectivity)
    if (!flightlines_.empty()) {
        p.setPen(QPen(QColor(255, 255, 0, 230), 1.5 / zoom_factor_, Qt::DashLine));
        for (const auto& fl : flightlines_) {
            p.drawLine(QPointF(fl.x1, fl.y1), QPointF(fl.x2, fl.y2));
        }
    }

    // 5. Render Selected Highlight Boxes (Single or Multi-select or Power Rails)
    if (!selected_power_rects_.empty()) {
        // Highlight entire power rail net in glowing electric yellow
        p.setPen(QPen(QColor(255, 235, 59), 2.0 / zoom_factor_));
        p.setBrush(QColor(255, 235, 59, 120));
        for (const auto& pr : selected_power_rects_) {
            p.drawRect(pr);
        }
    } else if (!multi_selected_rects_.empty()) {
        p.setPen(QPen(QColor(255, 255, 255), 1.5 / zoom_factor_));
        p.setBrush(QColor(255, 255, 255, 35));
        for (const auto& mr : multi_selected_rects_) {
            p.drawRect(mr);
        }
    } else if (!selected_rect_.isNull()) {
        p.setPen(QPen(QColor(255, 255, 255), 2.0 / zoom_factor_));
        p.setBrush(QColor(255, 255, 255, 40));
        p.drawRect(selected_rect_);

        p.setPen(QPen(QColor(255, 220, 0), 1.0 / zoom_factor_, Qt::DotLine));
        p.setBrush(Qt::NoBrush);
        p.drawRect(selected_rect_.adjusted(-3.0 / zoom_factor_, -3.0 / zoom_factor_, 3.0 / zoom_factor_, 3.0 / zoom_factor_));
    }

    p.restore();

    // 6. EXACT OPENROAD MARQUEE RUBBERBAND (White outline, zero fill, drawn in screen-space)
    if (rubber_band_showing_) {
        p.setPen(QPen(Qt::white, 1, Qt::SolidLine));
        p.setBrush(Qt::NoBrush);
        p.drawRect(rubber_band_.normalized());
    }

    // 7. Screen-space HUD & Ruler Overlay
    if (ruler_active_ && ruler_has_start_) {
        QPointF s1 = world_to_screen(ruler_start_);
        QPointF s2 = world_to_screen(ruler_current_);

        p.setPen(QPen(QColor(255, 50, 50), 2.0));
        p.drawLine(s1, s2);
        p.setBrush(QColor(255, 50, 50));
        p.drawEllipse(s1, 4, 4);
        p.drawEllipse(s2, 4, 4);

        double dx = std::abs(ruler_current_.x() - ruler_start_.x()) / dbu_;
        double dy = std::abs(ruler_current_.y() - ruler_start_.y()) / dbu_;
        double dist = std::sqrt(dx * dx + dy * dy);

        QString ruler_str = QString("L: %1 µm  (dx: %2 µm, dy: %3 µm)")
                                .arg(dist, 0, 'f', 3)
                                .arg(dx, 0, 'f', 3)
                                .arg(dy, 0, 'f', 3);

        QFont font = QFontDatabase::systemFont(QFontDatabase::SystemFont::FixedFont);
        font.setPointSize(9);
        p.setFont(font);

        QRect text_rect = p.fontMetrics().boundingRect(ruler_str).adjusted(-6, -4, 6, 4);
        text_rect.moveCenter(QPoint((s1.x() + s2.x()) / 2, (s1.y() + s2.y()) / 2 - 14));

        p.setPen(Qt::NoPen);
        p.setBrush(QColor(10, 10, 12, 220));
        p.drawRoundedRect(text_rect, 4, 4);

        p.setPen(QColor(255, 255, 255));
        p.drawText(text_rect, Qt::AlignCenter, ruler_str);
    }

    // 8. EXACT OPENROAD SCALE BAR HUD (Bottom-Left distance bracket |_| in screen coordinates)
    {
        // Compute nice metric target length in world units (e.g., 10, 20, 50, 100, 200, 500, 1000 µm)
        double target_screen_px = 120.0;
        double world_units_for_target = (target_screen_px / zoom_factor_) / dbu_; // in µm
        
        // Find closest 1, 2, 5 * 10^k
        double power = std::pow(10.0, std::floor(std::log10(world_units_for_target)));
        double mantissa = world_units_for_target / power;
        double nice_units = 1.0;
        if (mantissa >= 5.0) nice_units = 5.0;
        else if (mantissa >= 2.0) nice_units = 2.0;
        else nice_units = 1.0;
        double bar_microns = nice_units * power;
        double bar_px = bar_microns * dbu_ * zoom_factor_;

        if (bar_px > 10.0 && bar_px < width()) {
            double x_start = 20.0;
            double y_base = height() - 25.0;
            double tick_h = 7.0;

            // Draw OpenROAD |_| scale bracket
            p.setPen(QPen(Qt::white, 2.0));
            // Left tick
            p.drawLine(QPointF(x_start, y_base - tick_h), QPointF(x_start, y_base));
            // Horizontal bar
            p.drawLine(QPointF(x_start, y_base), QPointF(x_start + bar_px, y_base));
            // Right tick
            p.drawLine(QPointF(x_start + bar_px, y_base - tick_h), QPointF(x_start + bar_px, y_base));

            // Dimension text label
            QString scale_str;
            if (bar_microns >= 1000.0) {
                scale_str = QString("%1 mm").arg(bar_microns / 1000.0, 0, 'g', 3);
            } else if (bar_microns >= 1.0) {
                scale_str = QString("%1 µm").arg(bar_microns, 0, 'f', (bar_microns == std::floor(bar_microns)) ? 0 : 1);
            } else {
                scale_str = QString("%1 nm").arg(bar_microns * 1000.0, 0, 'f', 0);
            }

            QFont scale_font = QFontDatabase::systemFont(QFontDatabase::SystemFont::FixedFont);
            scale_font.setPointSize(8);
            scale_font.setBold(true);
            p.setFont(scale_font);
            p.setPen(Qt::white);
            p.drawText(QRectF(x_start, y_base - tick_h - 14.0, bar_px, 14.0), Qt::AlignCenter, scale_str);
        }
    }
}

void SilisNativeLayerViewer::wheelEvent(QWheelEvent* event) {
    double old_zoom = zoom_factor_;
    if (event->angleDelta().y() > 0) {
        zoom_factor_ *= 1.25;
    } else {
        zoom_factor_ /= 1.25;
    }
    zoom_factor_ = std::max(1e-4, std::min(100.0, zoom_factor_));

    QPointF mouse_pos = event->position();
    double center_x = width() / 2.0;
    double center_y = height() / 2.0;
    pan_offset_.rx() += (mouse_pos.x() - center_x) * (1.0 / zoom_factor_ - 1.0 / old_zoom);
    pan_offset_.ry() -= (mouse_pos.y() - center_y) * (1.0 / zoom_factor_ - 1.0 / old_zoom);

    update();
}

void SilisNativeLayerViewer::mousePressEvent(QMouseEvent* event) {
    mouse_press_pos_ = event->position().toPoint();
    QPointF wpos = screen_to_world(event->position());

    if (ruler_active_ && event->button() == Qt::LeftButton) {
        if (!ruler_has_start_) {
            ruler_start_ = wpos;
            ruler_current_ = wpos;
            ruler_has_start_ = true;
        } else {
            ruler_current_ = wpos;
        }
        update();
        return;
    }

    // Exact OpenROAD Middle-Click Drag / Alt-Drag Panning
    if (event->button() == Qt::MiddleButton || (event->modifiers() & Qt::AltModifier)) {
        is_panning_ = true;
        last_mouse_pos_ = event->position();
        setCursor(Qt::ClosedHandCursor);
        return;
    }

    // Exact OpenROAD Left/Right Drag Marquee Setup
    rubber_band_.setTopLeft(mouse_press_pos_);
    rubber_band_.setBottomRight(mouse_press_pos_);
    rubber_band_showing_ = false;
}

void SilisNativeLayerViewer::mouseMoveEvent(QMouseEvent* event) {
    if (ruler_active_ && ruler_has_start_) {
        ruler_current_ = screen_to_world(event->position());
        update();
        return;
    }

    if (is_panning_) {
        QPointF delta = event->position() - last_mouse_pos_;
        pan_offset_.rx() += delta.x() / zoom_factor_;
        pan_offset_.ry() -= delta.y() / zoom_factor_;
        last_mouse_pos_ = event->position();
        update();
        return;
    }

    // Exact OpenROAD Rubberband expansion logic
    if (!rubber_band_.isNull()) {
        rubber_band_.setBottomRight(event->position().toPoint());
        const QRect norm = rubber_band_.normalized();
        if (norm.width() >= 4 && norm.height() >= 4) {
            rubber_band_showing_ = true;
            setCursor(Qt::CrossCursor);
            update();
        }
    }
}

void SilisNativeLayerViewer::mouseReleaseEvent(QMouseEvent* event) {
    if (is_panning_) {
        is_panning_ = false;
        unsetCursor();
        return;
    }

    const QRect rubber_rect = rubber_band_.normalized();
    rubber_band_ = QRect();

    if (rubber_band_showing_) {
        rubber_band_showing_ = false;
        unsetCursor();
        update();

        // Convert rubberband to DBU world coordinates
        QPointF p_tl = screen_to_world(rubber_rect.topLeft());
        QPointF p_br = screen_to_world(rubber_rect.bottomRight());
        float x1 = std::min(p_tl.x(), p_br.x());
        float x2 = std::max(p_tl.x(), p_br.x());
        float y1 = std::min(p_tl.y(), p_br.y());
        float y2 = std::max(p_tl.y(), p_br.y());
        QRectF box(x1, y1, x2 - x1, y2 - y1);

        if (event->button() == Qt::LeftButton) {
            // Select all objects intersecting the marquee box (Multi-Select)
            std::vector<std::string> hit_names;
            for (size_t i = 0; i < instances_.size(); ++i) {
                if (box.intersects(instances_[i].rect)) {
                    hit_names.push_back(instances_[i].name);
                }
            }

            if (!hit_names.empty()) {
                select_instances(hit_names);
                const auto& first_hit = instances_[inst_name_index_[hit_names.front()]];
                emit instance_clicked(QString::fromStdString(first_hit.name),
                                      QString::fromStdString(first_hit.master),
                                      first_hit.rect.x(), first_hit.rect.y(), first_hit.rect.width(), first_hit.rect.height());
            } else {
                clear_selection();
            }
            emit area_selected(x1, y1, x2, y2);
        } else if (event->button() == Qt::RightButton) {
            // Exact OpenROAD behavior: Right-Click Marquee Zooms into region
            zoom_to_box(box);
        }
        return;
    }

    // Single Click (No Drag)
    if (event->button() == Qt::LeftButton) {
        QPointF wpos = screen_to_world(event->position());
        int best_hit = -1;
        double best_area = 1e20;

        for (size_t i = 0; i < instances_.size(); ++i) {
            const auto& inst = instances_[i];
            if (inst.rect.contains(wpos)) {
                double area = inst.rect.width() * inst.rect.height();
                if (area < best_area) {
                    best_area = area;
                    best_hit = static_cast<int>(i);
                }
            }
        }

        if (best_hit >= 0) {
            const auto& hit = instances_[best_hit];
            select_instance(hit.name);
            emit instance_clicked(QString::fromStdString(hit.name),
                                  QString::fromStdString(hit.master),
                                  hit.rect.x(), hit.rect.y(), hit.rect.width(), hit.rect.height());
        } else {
            // Check if user clicked on a Power Rail / Strap
            int best_rail = -1;
            double best_rail_area = 1e20;
            for (size_t i = 0; i < power_rails_.size(); ++i) {
                const auto& pr = power_rails_[i];
                if (pr.rect.contains(wpos)) {
                    double area = pr.rect.width() * pr.rect.height();
                    if (area < best_rail_area) {
                        best_rail_area = area;
                        best_rail = static_cast<int>(i);
                    }
                }
            }

            if (best_rail >= 0) {
                const auto& hit_rail = power_rails_[best_rail];
                select_power_net(hit_rail.net_name);
                emit power_rail_clicked(QString::fromStdString(hit_rail.net_name),
                                        QString::fromStdString(hit_rail.layer_name),
                                        hit_rail.rect.x(), hit_rail.rect.y(),
                                        hit_rail.rect.width(), hit_rail.rect.height());
            } else {
                clear_selection();
                emit canvas_clicked(wpos.x(), wpos.y());
            }
        }
    }
}
