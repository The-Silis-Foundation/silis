#include "FastLayoutViewer.h"
#include <QPainter>
#include <QWheelEvent>
#include <QMouseEvent>
#include <QPen>
#include <cmath>

FastLayoutViewer::FastLayoutViewer(QWidget* parent) 
    : QWidget(parent), zoom_factor_(1.0), is_panning_(false) {
    lod_std_cells_ = 0.03f;
    lod_nets_ = 0.05f;
    setMouseTracking(true);
    setAttribute(Qt::WA_OpaquePaintEvent); // Skip default background drawing for raw speed
}

void FastLayoutViewer::clear() {
    std_cells_.clear();
    tap_cells_.clear();
    macros_.clear();
    macro_names_.clear();
    pins_.clear();
    pin_names_.clear();
    power_.clear();
    signals_.clear();
    regions_.clear();
    region_names_.clear();
    voltage_islands_.clear();
    voltage_island_vals_.clear();
    voltage_island_names_.clear();
    blockages_.clear();
    heatmap_data_.clear();
    heatmap_mode_ = 0;
    hover_active_ = false;
    ruler_has_start_ = false;
    core_rect_ = QRectF();
    highlight_rect_ = QRectF();
    highlight_name_.clear();
    update();
}

void FastLayoutViewer::set_lod(float std_cell_threshold, float nets_threshold) {
    lod_std_cells_ = std_cell_threshold;
    lod_nets_ = nets_threshold;
    update();
}

void FastLayoutViewer::set_core(float x, float y, float w, float h) {
    core_rect_ = QRectF(x, y, w, h);
    update();
}

void FastLayoutViewer::load_std_cells(const std::vector<float>& x, const std::vector<float>& y, 
                                     const std::vector<float>& w, const std::vector<float>& h) {
    std_cells_.reserve(std_cells_.size() + x.size());
    for(size_t i=0; i<x.size(); ++i) std_cells_.emplace_back(x[i], y[i], w[i], h[i]);
    update();
}

void FastLayoutViewer::load_cells_flat(const float* data, size_t count) {
    std_cells_.reserve(std_cells_.size() + count);
    for (size_t i = 0; i < count; ++i) {
        size_t base = i * 4;
        std_cells_.emplace_back(data[base], data[base + 1], data[base + 2], data[base + 3]);
    }
    update();
}

void FastLayoutViewer::load_tap_cells(const std::vector<float>& x, const std::vector<float>& y, 
                                      const std::vector<float>& w, const std::vector<float>& h) {
    tap_cells_.reserve(tap_cells_.size() + x.size());
    for(size_t i=0; i<x.size(); ++i) tap_cells_.emplace_back(x[i], y[i], w[i], h[i]);
    update();
}

void FastLayoutViewer::load_macros(const std::vector<float>& x, const std::vector<float>& y, 
                                   const std::vector<float>& w, const std::vector<float>& h,
                                   const std::vector<std::string>& names) {
    size_t count = x.size();
    macros_.reserve(macros_.size() + count);
    macro_names_.reserve(macro_names_.size() + count);
    for (size_t i = 0; i < count; ++i) {
        macros_.emplace_back(x[i], y[i], w[i], h[i]);
        if (i < names.size()) macro_names_.push_back(names[i]);
        else macro_names_.push_back("");
    }
    update();
}

void FastLayoutViewer::load_pins(const std::vector<float>& x, const std::vector<float>& y, 
                                 const std::vector<float>& w, const std::vector<float>& h,
                                 const std::vector<std::string>& names) {
    size_t count = x.size();
    pins_.reserve(pins_.size() + count);
    pin_names_.reserve(pin_names_.size() + count);
    for (size_t i = 0; i < count; ++i) {
        pins_.emplace_back(x[i], y[i], w[i], h[i]);
        if (i < names.size()) pin_names_.push_back(names[i]);
        else pin_names_.push_back("");
    }
    update();
}

void FastLayoutViewer::load_power(const std::vector<float>& x, const std::vector<float>& y, 
                                  const std::vector<float>& w, const std::vector<float>& h) {
    size_t count = x.size();
    power_.reserve(power_.size() + count);
    for (size_t i = 0; i < count; ++i) {
        power_.emplace_back(x[i], y[i], w[i], h[i]);
    }
    update();
}

void FastLayoutViewer::load_signals(const std::vector<float>& x1, const std::vector<float>& y1, 
                                    const std::vector<float>& x2, const std::vector<float>& y2) {
    size_t count = x1.size();
    signals_.reserve(signals_.size() + count);
    for (size_t i = 0; i < count; ++i) {
        signals_.emplace_back(x1[i], y1[i], x2[i], y2[i]);
    }
    update();
}

void FastLayoutViewer::load_regions(const std::vector<float>& x, const std::vector<float>& y, 
                                    const std::vector<float>& w, const std::vector<float>& h,
                                    const std::vector<std::string>& names) {
    size_t count = x.size();
    regions_.reserve(regions_.size() + count);
    region_names_.reserve(region_names_.size() + count);
    for (size_t i = 0; i < count; ++i) {
        regions_.emplace_back(x[i], y[i], w[i], h[i]);
        if (i < names.size()) region_names_.push_back(names[i]);
        else region_names_.push_back("");
    }
    update();
}

void FastLayoutViewer::load_voltage_islands(const std::vector<float>& x, const std::vector<float>& y, 
                                            const std::vector<float>& w, const std::vector<float>& h,
                                            const std::vector<float>& voltages,
                                            const std::vector<std::string>& names) {
    size_t count = x.size();
    voltage_islands_.reserve(voltage_islands_.size() + count);
    voltage_island_vals_.reserve(voltage_island_vals_.size() + count);
    voltage_island_names_.reserve(voltage_island_names_.size() + count);
    for (size_t i = 0; i < count; ++i) {
        voltage_islands_.emplace_back(x[i], y[i], w[i], h[i]);
        voltage_island_vals_.push_back(i < voltages.size() ? voltages[i] : 1.8f);
        voltage_island_names_.push_back(i < names.size() ? names[i] : "");
    }
    update();
}

void FastLayoutViewer::load_blockages(const std::vector<float>& x, const std::vector<float>& y, 
                                      const std::vector<float>& w, const std::vector<float>& h) {
    size_t count = x.size();
    blockages_.reserve(blockages_.size() + count);
    for (size_t i = 0; i < count; ++i) {
        blockages_.emplace_back(x[i], y[i], w[i], h[i]);
    }
    update();
}

void FastLayoutViewer::set_heatmap(int mode, const std::vector<float>& data, int grid_w, int grid_h) {
    heatmap_mode_ = mode;
    heatmap_data_ = data;
    hover_active_ = false;
    if (grid_w > 0 && grid_h > 0) {
        heatmap_grid_w_ = grid_w;
        heatmap_grid_h_ = grid_h;
    } else {
        // Auto-detect square grid dimension if possible
        int sz = (int)data.size();
        int root = (int)std::round(std::sqrt(sz));
        if (root * root == sz && root > 0) {
            heatmap_grid_w_ = root;
            heatmap_grid_h_ = root;
        } else {
            heatmap_grid_w_ = 160;
            heatmap_grid_h_ = 160;
        }
    }
    update();
}

void FastLayoutViewer::set_heatmap_bounds(float x, float y, float w, float h) {
    heatmap_rect_ = QRectF(x, y, w, h);
    update();
}

void FastLayoutViewer::fit_in_view() {
    if (core_rect_.isNull() || core_rect_.width() == 0 || core_rect_.height() == 0) return;
    double scale_x = width() / (core_rect_.width() * 1.1);
    double scale_y = height() / (core_rect_.height() * 1.1);
    zoom_factor_ = std::min(scale_x, scale_y);
    pan_offset_ = QPointF(0, 0); // Center
    update();
}

void FastLayoutViewer::paintEvent(QPaintEvent* event) {
    QPainter painter(this);
    // Pure black EDA canvas background
    painter.fillRect(rect(), QColor(0, 0, 0));
    painter.setRenderHint(QPainter::Antialiasing, false);  
    
    painter.translate(rect().center());
    painter.scale(zoom_factor_, -zoom_factor_); // Y is flipped in CAD vs Screen
    painter.translate(-core_rect_.center());
    painter.translate(pan_offset_);

    // Calculate visible viewport for Culling
    QTransform transform = painter.transform();
    QTransform inv = transform.inverted();
    QRectF viewport = inv.mapRect(QRectF(rect()));

    // Draw Core Box
    QPen core_pen(QColor(100, 100, 100));
    core_pen.setCosmetic(true);
    painter.setPen(core_pen);
    painter.setBrush(Qt::NoBrush);
    painter.drawRect(core_rect_);
    
    // Draw Power Rails (Orange/Yellow)
    QPen pwr_pen(Qt::NoPen);
    painter.setPen(pwr_pen);
    painter.setBrush(QColor(255, 170, 0, 150));
    
    std::vector<QRectF> visible_pwr;
    visible_pwr.reserve(power_.size() / 10);
    for (const auto& r : power_) {
        if (r.intersects(viewport)) visible_pwr.push_back(r);
    }
    painter.drawRects(visible_pwr.data(), visible_pwr.size());
    
    // Draw Signal Routes
    if (!signals_.empty() && zoom_factor_ > lod_nets_) {
        QPen sig_pen(QColor(65, 105, 225, 200)); // Royal Blue
        sig_pen.setCosmetic(true);
        painter.setPen(sig_pen);
        
        std::vector<QLineF> visible_sigs;
        visible_sigs.reserve(signals_.size() / 10);
        for (const auto& l : signals_) {
            if (viewport.contains(l.p1()) || viewport.contains(l.p2())) {
                visible_sigs.push_back(l);
            } else {
                double rx = std::min(l.p1().x(), l.p2().x());
                double ry = std::min(l.p1().y(), l.p2().y());
                double rw = std::max(0.001, std::abs(l.p2().x() - l.p1().x()));
                double rh = std::max(0.001, std::abs(l.p2().y() - l.p1().y()));
                if (viewport.intersects(QRectF(rx, ry, rw, rh))) {
                    visible_sigs.push_back(l);
                }
            }
        }
        painter.drawLines(visible_sigs.data(), visible_sigs.size());
    }

    // Draw Standard Cells (Solid cyan-ish with dark border)
    QPen std_pen(QColor(0, 50, 100, 100));
    std_pen.setCosmetic(true);
    painter.setPen(std_pen);
    painter.setBrush(QColor(76, 201, 240, 255));
    
    if (zoom_factor_ > lod_std_cells_) {
        std::vector<QRectF> visible_std;
        visible_std.reserve(std_cells_.size() / 10);
        for (const auto& r : std_cells_) {
            if (r.intersects(viewport)) visible_std.push_back(r);
        }
        painter.drawRects(visible_std.data(), visible_std.size());
    }

    // Draw Tap Cells / Power Category Cells (Amber / Gold)
    if (zoom_factor_ > lod_std_cells_) {
        QPen tap_pen(QColor(245, 190, 30, 200));
        tap_pen.setCosmetic(true);
        painter.setPen(tap_pen);
        painter.setBrush(QColor(210, 145, 20, 220));
        std::vector<QRectF> visible_tap;
        visible_tap.reserve(tap_cells_.size() / 10);
        for (const auto& r : tap_cells_) {
            if (r.intersects(viewport)) visible_tap.push_back(r);
        }
        painter.drawRects(visible_tap.data(), visible_tap.size());
    }

    // Draw Macros (Bright Orange/Red, solid)
    QPen macro_pen(QColor(255, 100, 50));
    macro_pen.setCosmetic(true);
    painter.setPen(macro_pen);
    painter.setBrush(QColor(255, 120, 70, 255));
    
    std::vector<QRectF> visible_macros;
    for (const auto& r : macros_) {
        if (r.intersects(viewport)) visible_macros.push_back(r);
    }
    painter.drawRects(visible_macros.data(), visible_macros.size());

    // Draw Regions
    QPen reg_pen(QColor(255, 255, 0, 200)); // Yellow outline
    reg_pen.setCosmetic(true);
    painter.setPen(reg_pen);
    painter.setBrush(QColor(255, 255, 0, 30)); // very transparent yellow
    painter.drawRects(regions_.data(), regions_.size());

    // Draw Voltage Islands (EDA voltage-level mapped palette)
    for (size_t vi = 0; vi < voltage_islands_.size(); ++vi) {
        float volt = vi < voltage_island_vals_.size() ? voltage_island_vals_[vi] : 1.8f;
        QColor v_color;
        if (volt >= 2.5f) v_color = QColor(181, 137, 0);       // Amber (#b58900)
        else if (volt >= 1.6f) v_color = QColor(38, 139, 210);  // Cyan (#268bd2)
        else if (volt >= 0.8f) v_color = QColor(108, 113, 196); // Slate indigo (#6c71c4)
        else v_color = QColor(42, 161, 152);                   // Muted teal (#2aa198)

        QPen vi_pen(v_color, 2.0f);
        vi_pen.setStyle(Qt::DashDotLine);
        vi_pen.setCosmetic(true);
        painter.setPen(vi_pen);
        painter.setBrush(QColor(v_color.red(), v_color.green(), v_color.blue(), 45));
        painter.drawRect(voltage_islands_[vi]);
    }
    
    // Draw Pins with minimum visible screen threshold (at least 6px across)
    QPen pin_pen(QColor(255, 255, 255, 220));
    pin_pen.setCosmetic(true);
    painter.setPen(pin_pen);
    painter.setBrush(QColor(255, 50, 50, 255));

    double min_screen_size = 6.0;
    double min_world_size = min_screen_size / zoom_factor_;

    std::vector<QRectF> visible_pins;
    visible_pins.reserve(pins_.size());
    for (const auto& pr : pins_) {
        double pw = pr.width();
        double ph = pr.height();
        if (pw < min_world_size || ph < min_world_size) {
            double dw = std::max(pw, min_world_size);
            double dh = std::max(ph, min_world_size);
            QPointF center = pr.center();
            visible_pins.emplace_back(center.x() - dw/2.0, center.y() - dh/2.0, dw, dh);
        } else {
            visible_pins.push_back(pr);
        }
    }
    painter.drawRects(visible_pins.data(), visible_pins.size());

    // Draw Text with LOD checks (only show names when sufficiently zoomed in)
    painter.save();
    painter.scale(1.0 / zoom_factor_, -1.0 / zoom_factor_);
    painter.setPen(QPen(Qt::black));
    
    // Macro names: only when macro height on screen is >= 24 pixels
    for (size_t i = 0; i < macros_.size(); i++) {
        if (!macro_names_[i].empty() && (macros_[i].height() * zoom_factor_ >= 24.0)) {
            QPointF p = macros_[i].center();
            double sx = p.x() * zoom_factor_;
            double sy = p.y() * -zoom_factor_;
            painter.drawText(sx - 20, sy, QString::fromStdString(macro_names_[i]));
        }
    }
    
    // Pin names: only when deeply zoomed in (zoom_factor_ > 1.2)
    if (zoom_factor_ > 1.2) {
        for (size_t i = 0; i < pins_.size(); i++) {
            if (!pin_names_[i].empty()) {
                QPointF p = pins_[i].center();
                double sx = p.x() * zoom_factor_;
                double sy = p.y() * -zoom_factor_;
                painter.drawText(sx - 10, sy, QString::fromStdString(pin_names_[i]));
            }
        }
    }

    // Region names: only when region height on screen is >= 24 pixels
    for (size_t i = 0; i < regions_.size(); i++) {
        if (!region_names_[i].empty() && (regions_[i].height() * zoom_factor_ >= 24.0)) {
            QPointF p = regions_[i].center();
            double sx = p.x() * zoom_factor_;
            double sy = p.y() * -zoom_factor_;
            painter.setPen(QPen(Qt::yellow));
            painter.drawText(sx - 20, sy, QString::fromStdString(region_names_[i]));
        }
    }

    // Voltage Island names: displayed with voltage-level label
    for (size_t i = 0; i < voltage_islands_.size(); i++) {
        if (voltage_islands_[i].height() * zoom_factor_ >= 20.0) {
            QPointF p = voltage_islands_[i].center();
            double sx = p.x() * zoom_factor_;
            double sy = p.y() * -zoom_factor_;
            float volt = i < voltage_island_vals_.size() ? voltage_island_vals_[i] : 1.8f;
            QString v_lbl = QString("%1 (%2V)").arg(QString::fromStdString(voltage_island_names_[i])).arg(volt, 0, 'f', 2);
            painter.setPen(QPen(QColor(220, 220, 220)));
            painter.drawText(sx - 30, sy, v_lbl);
        }
    }
    painter.restore();

    // Draw Highlight Bounding Box (for search / focus)
    if (!highlight_rect_.isNull() && highlight_rect_.width() > 0) {
        QPen hl_pen(QColor(255, 215, 0, 240), 3.0f / zoom_factor_);
        hl_pen.setCosmetic(true);
        painter.setPen(hl_pen);
        painter.setBrush(QColor(255, 235, 59, 90));
        painter.drawRect(highlight_rect_);

        if (!highlight_name_.empty()) {
            painter.save();
            painter.scale(1.0 / zoom_factor_, -1.0 / zoom_factor_);
            QPointF p = highlight_rect_.center();
            double sx = p.x() * zoom_factor_;
            double sy = p.y() * -zoom_factor_;
            painter.setPen(QPen(QColor(255, 235, 59)));
            QFont f = painter.font();
            f.setBold(true);
            f.setPointSize(11);
            painter.setFont(f);
            painter.drawText(sx - 30, sy - 15, QString::fromStdString(highlight_name_));
            painter.restore();
        }
    }
    
    // Draw Heatmap (High-resolution industrial EDA heatmap with Turbo/Jet colormap)
    if (heatmap_mode_ > 0 && !heatmap_data_.empty()) {
        int gw = (heatmap_grid_w_ > 0) ? heatmap_grid_w_ : 160;
        int gh = (heatmap_grid_h_ > 0) ? heatmap_grid_h_ : 160;
        size_t expected_size = (size_t)gw * gh;
        QRectF h_bounds = (heatmap_rect_.width() > 0 && heatmap_rect_.height() > 0) ? heatmap_rect_ : core_rect_;
        if (heatmap_data_.size() >= expected_size && h_bounds.width() > 0 && h_bounds.height() > 0) {
            float cell_w = h_bounds.width() / (float)gw;
            float cell_h = h_bounds.height() / (float)gh;
            painter.setPen(Qt::NoPen);

            for (int y = 0; y < gh; ++y) {
                float cell_y = h_bounds.y() + y * cell_h;
                // Fast viewport culling for rows
                if (cell_y + cell_h < viewport.top() || cell_y > viewport.bottom()) continue;

                for (int x = 0; x < gw; ++x) {
                    float cell_x = h_bounds.x() + x * cell_w;
                    if (cell_x + cell_w < viewport.left() || cell_x > viewport.right()) continue;

                    float raw_val = heatmap_data_[y * gw + x];
                    if (std::isnan(raw_val) || std::isinf(raw_val)) continue;
                    float val = std::min(1.0f, std::max(0.0f, raw_val));
                    if (val > 0.01f) {
                        // Professional EDA Multi-stop colormap:
                        // 0.0 -> Blue, 0.25 -> Cyan, 0.5 -> Green, 0.75 -> Yellow, 1.0 -> Red
                        int r = 0, g = 0, b = 0;
                        if (val < 0.25f) {
                            float f = val / 0.25f;
                            r = 0;
                            g = (int)(255 * f);
                            b = 255;
                        } else if (val < 0.5f) {
                            float f = (val - 0.25f) / 0.25f;
                            r = 0;
                            g = 255;
                            b = (int)(255 * (1.0f - f));
                        } else if (val < 0.75f) {
                            float f = (val - 0.5f) / 0.25f;
                            r = (int)(255 * f);
                            g = 255;
                            b = 0;
                        } else {
                            float f = (val - 0.75f) / 0.25f;
                            r = 255;
                            g = (int)(255 * (1.0f - f));
                            b = 0;
                        }
                        int alpha = std::min(185, (int)(70 + val * 115));
                        painter.fillRect(QRectF(cell_x, cell_y, cell_w, cell_h), QColor(r, g, b, alpha));
                    }
                }
            }
        }
    }

    // Draw Ruler (interactive distance measurement)
    if (ruler_has_start_) {
        QPen ruler_pen(QColor(255, 235, 59), 2.0f / zoom_factor_);
        ruler_pen.setCosmetic(true);
        ruler_pen.setStyle(Qt::DashLine);
        painter.setPen(ruler_pen);
        painter.drawLine(ruler_start_, ruler_current_);

        // Draw start/end ticks
        float tick = 5.0f / zoom_factor_;
        painter.drawLine(QPointF(ruler_start_.x() - tick, ruler_start_.y() - tick), QPointF(ruler_start_.x() + tick, ruler_start_.y() + tick));
        painter.drawLine(QPointF(ruler_start_.x() - tick, ruler_start_.y() + tick), QPointF(ruler_start_.x() + tick, ruler_start_.y() - tick));
        painter.drawLine(QPointF(ruler_current_.x() - tick, ruler_current_.y() - tick), QPointF(ruler_current_.x() + tick, ruler_current_.y() + tick));
        painter.drawLine(QPointF(ruler_current_.x() - tick, ruler_current_.y() + tick), QPointF(ruler_current_.x() + tick, ruler_current_.y() - tick));

        // Distance in microns exact conversion using DBU
        double current_dbu = (dbu_ > 0.0f) ? (double)dbu_ : 1000.0;
        double dx = ruler_current_.x() - ruler_start_.x();
        double dy = ruler_current_.y() - ruler_start_.y();
        double dist = std::sqrt(dx * dx + dy * dy);
        double dist_um = dist / current_dbu;
        double dx_um = std::abs(dx) / current_dbu;
        double dy_um = std::abs(dy) / current_dbu;

        painter.save();
        painter.scale(1.0 / zoom_factor_, -1.0 / zoom_factor_);
        QPointF mid = (ruler_start_ + ruler_current_) / 2.0;
        double sx = mid.x() * zoom_factor_;
        double sy = mid.y() * -zoom_factor_;

        QString lbl = QString("L: %1 um (dx: %2, dy: %3)").arg(dist_um, 0, 'f', 2).arg(dx_um, 0, 'f', 2).arg(dy_um, 0, 'f', 2);
        QFont f = painter.font();
        f.setBold(true);
        f.setPointSize(10);
        painter.setFont(f);
        QFontMetrics fm(f);
        int tw = fm.horizontalAdvance(lbl);
        painter.fillRect(QRectF(sx - tw/2 - 4, sy - 18, tw + 8, 18), QColor(0, 0, 0, 200));
        painter.setPen(QColor(255, 235, 59));
        painter.drawText(sx - tw/2, sy - 4, lbl);
        painter.restore();
    }

    // Draw Heatmap Hover HUD Card (Subtle, non-intrusive bottom-right of cursor)
    if (heatmap_mode_ > 0 && hover_active_ && hover_val_ > 0.001f) {
        painter.save();
        // Reset transform to draw in screen pixel coordinates
        painter.resetTransform();

        // 16px offset to bottom-right of cursor
        float hud_x = hover_mouse_pos_.x() + 16.0f;
        float hud_y = hover_mouse_pos_.y() + 16.0f;
        float card_w = 200.0f;
        float card_h = 60.0f;

        // Flip inward if near screen borders
        if (hud_x + card_w > width() - 8.0f) {
            hud_x = hover_mouse_pos_.x() - card_w - 12.0f;
        }
        if (hud_y + card_h > height() - 8.0f) {
            hud_y = hover_mouse_pos_.y() - card_h - 12.0f;
        }

        // Draw Card Background (semi-transparent dark slate)
        QRectF card_rect(hud_x, hud_y, card_w, card_h);
        painter.setPen(QColor(48, 54, 61, 255)); // #30363d subtle border
        painter.setBrush(QColor(22, 27, 34, 235)); // rgba(22, 27, 34, 0.92)
        painter.drawRoundedRect(card_rect, 4.0, 4.0);

        // Heatmap metric title
        const char* mode_title = "Heatmap";
        if (heatmap_mode_ == 1) mode_title = "RUDY Congestion";
        else if (heatmap_mode_ == 2) mode_title = "Route Density";
        else if (heatmap_mode_ == 3) mode_title = "Placement Density";
        else if (heatmap_mode_ == 4) mode_title = "Pin Density";
        else if (heatmap_mode_ == 5) mode_title = "Static IR Drop";
        else if (heatmap_mode_ == 6) mode_title = "Power Density";

        QFont f_mono("Monospace", 8);
        f_mono.setStyleHint(QFont::Monospace);
        painter.setFont(f_mono);

        // Header line: Metric & Percentage
        painter.setPen(QColor(88, 166, 255)); // Blue highlight
        QString line1 = QString("%1: %2%").arg(mode_title).arg(hover_val_ * 100.0f, 0, 'f', 1);
        painter.drawText(QRectF(hud_x + 8, hud_y + 6, card_w - 16, 16), Qt::AlignLeft | Qt::AlignVCenter, line1);

        // Line 2: Tile bin indices
        painter.setPen(QColor(201, 209, 217)); // #c9d1d9
        QString line2 = QString("Tile: [%1, %2] (%3x%4)").arg(hover_gx_).arg(hover_gy_).arg(heatmap_grid_w_).arg(heatmap_grid_h_);
        painter.drawText(QRectF(hud_x + 8, hud_y + 22, card_w - 16, 16), Qt::AlignLeft | Qt::AlignVCenter, line2);

        // Line 3: Micrometer database coordinates
        double current_dbu = (dbu_ > 0.0f) ? (double)dbu_ : 1000.0;
        double db_x_um = hover_db_pos_.x() / current_dbu;
        double db_y_um = hover_db_pos_.y() / current_dbu;
        painter.setPen(QColor(139, 148, 158)); // muted gray
        QString line3 = QString("Coord: (%1, %2) um").arg(db_x_um, 0, 'f', 1).arg(db_y_um, 0, 'f', 1);
        painter.drawText(QRectF(hud_x + 8, hud_y + 38, card_w - 16, 16), Qt::AlignLeft | Qt::AlignVCenter, line3);

        painter.restore();
    }
}

void FastLayoutViewer::set_dbu(float dbu) {
    if (dbu > 0.0f) {
        dbu_ = dbu;
        update();
    }
}

float FastLayoutViewer::get_dbu() const {
    return dbu_;
}

void FastLayoutViewer::set_ruler_active(bool active) {
    ruler_active_ = active;
    if (!active) {
        ruler_has_start_ = false;
        setCursor(Qt::ArrowCursor);
    } else {
        setCursor(Qt::CrossCursor);
    }
    update();
}

bool FastLayoutViewer::is_ruler_active() const {
    return ruler_active_;
}

void FastLayoutViewer::clear_ruler() {
    ruler_has_start_ = false;
    update();
}

void FastLayoutViewer::pan_to(float x, float y, float target_zoom) {
    if (target_zoom > 0.0f) {
        zoom_factor_ = target_zoom;
    }
    pan_offset_ = core_rect_.center() - QPointF(x, y);
    update();
}

void FastLayoutViewer::highlight_box(float x, float y, float w, float h, const std::string& name) {
    highlight_rect_ = QRectF(x, y, w, h);
    highlight_name_ = name;
    update();
}

void FastLayoutViewer::clear_highlight() {
    highlight_rect_ = QRectF();
    highlight_name_.clear();
    update();
}

void FastLayoutViewer::wheelEvent(QWheelEvent* event) {
    double angle = event->angleDelta().y();
    if (angle == 0) return;
    double factor = (angle > 0) ? 1.2 : (1.0 / 1.2);
    double old_zoom = zoom_factor_;
    zoom_factor_ *= factor;
    // Bound zoom between 1e-4 and 1e4 to avoid numerical degeneracy
    zoom_factor_ = std::max(1e-4, std::min(1e4, zoom_factor_));
    double actual_factor = zoom_factor_ / old_zoom;

    // Anchor zoom around cursor position on screen
    QPointF cursor_pos = event->position();
    double center_x = width() / 2.0;
    double center_y = height() / 2.0;
    pan_offset_.rx() += (cursor_pos.x() - center_x) * (1.0 / zoom_factor_ - 1.0 / old_zoom);
    pan_offset_.ry() -= (cursor_pos.y() - center_y) * (1.0 / zoom_factor_ - 1.0 / old_zoom);

    update();
}

void FastLayoutViewer::mousePressEvent(QMouseEvent* event) {
    if (ruler_active_ && event->button() == Qt::LeftButton) {
        // Map screen point to world coordinates
        // World coordinates: center = (width/2, height/2), pan_offset, scale (zoom_factor, -zoom_factor)
        double center_x = width() / 2.0;
        double center_y = height() / 2.0;
        double wx = (event->position().x() - center_x) / zoom_factor_ - pan_offset_.x() + core_rect_.center().x();
        double wy = -(event->position().y() - center_y) / zoom_factor_ - pan_offset_.y() + core_rect_.center().y();
        QPointF pt(wx, wy);

        if (!ruler_has_start_) {
            ruler_start_ = pt;
            ruler_current_ = pt;
            ruler_has_start_ = true;
        } else {
            ruler_current_ = pt;
        }
        update();
        return;
    }

    if (event->button() == Qt::RightButton || event->button() == Qt::MiddleButton || (!ruler_active_ && event->button() == Qt::LeftButton)) {
        is_panning_ = true;
        last_mouse_pos_ = event->position();
        setCursor(Qt::ClosedHandCursor);
    }
}

void FastLayoutViewer::mouseMoveEvent(QMouseEvent* event) {
    if (ruler_active_ && ruler_has_start_) {
        double center_x = width() / 2.0;
        double center_y = height() / 2.0;
        double wx = (event->position().x() - center_x) / zoom_factor_ - pan_offset_.x() + core_rect_.center().x();
        double wy = -(event->position().y() - center_y) / zoom_factor_ - pan_offset_.y() + core_rect_.center().y();
        ruler_current_ = QPointF(wx, wy);
        update();
        return;
    }

    if (is_panning_) {
        QPointF delta = event->position() - last_mouse_pos_;
        pan_offset_.rx() += delta.x() / zoom_factor_;
        pan_offset_.ry() -= delta.y() / zoom_factor_;
        last_mouse_pos_ = event->position();
        hover_active_ = false;
        update();
        return;
    }

    // Interactive Heatmap Hover Inspection
    if (heatmap_mode_ > 0 && !heatmap_data_.empty()) {
        double center_x = width() / 2.0;
        double center_y = height() / 2.0;
        double wx = (event->position().x() - center_x) / zoom_factor_ - pan_offset_.x() + core_rect_.center().x();
        double wy = -(event->position().y() - center_y) / zoom_factor_ - pan_offset_.y() + core_rect_.center().y();

        QRectF h_bounds = (heatmap_rect_.width() > 0 && heatmap_rect_.height() > 0) ? heatmap_rect_ : core_rect_;
        if (h_bounds.contains(QPointF(wx, wy)) && h_bounds.width() > 0 && h_bounds.height() > 0) {
            int gw = (heatmap_grid_w_ > 0) ? heatmap_grid_w_ : 160;
            int gh = (heatmap_grid_h_ > 0) ? heatmap_grid_h_ : 160;

            int gx = (int)(gw * (wx - h_bounds.x()) / h_bounds.width());
            int gy = (int)(gh * (wy - h_bounds.y()) / h_bounds.height());
            gx = std::max(0, std::min(gw - 1, gx));
            gy = std::max(0, std::min(gh - 1, gy));

            size_t idx = (size_t)gy * gw + gx;
            if (idx < heatmap_data_.size()) {
                hover_active_ = true;
                hover_mouse_pos_ = event->position();
                hover_db_pos_ = QPointF(wx, wy);
                hover_gx_ = gx;
                hover_gy_ = gy;
                hover_val_ = heatmap_data_[idx];
                update();
                return;
            }
        }
    }

    if (hover_active_) {
        hover_active_ = false;
        update();
    }
}

void FastLayoutViewer::mouseReleaseEvent(QMouseEvent* event) {
    if (ruler_active_ && event->button() == Qt::LeftButton) {
        return;
    }

    if (event->button() == Qt::RightButton || event->button() == Qt::MiddleButton || event->button() == Qt::LeftButton) {
        is_panning_ = false;
        setCursor(ruler_active_ ? Qt::CrossCursor : Qt::ArrowCursor);
    }
}
