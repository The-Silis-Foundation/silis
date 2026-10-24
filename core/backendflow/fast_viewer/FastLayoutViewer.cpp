#include "FastLayoutViewer.h"
#include <QPainter>
#include <QWheelEvent>
#include <QMouseEvent>
#include <QPen>

FastLayoutViewer::FastLayoutViewer(QWidget* parent) 
    : QWidget(parent), zoom_factor_(1.0), is_panning_(false) {
    lod_std_cells_ = 0.03f;
    lod_nets_ = 0.05f;
    setMouseTracking(true);
    setAttribute(Qt::WA_OpaquePaintEvent); // Skip default background drawing for raw speed
}

void FastLayoutViewer::clear() {
    std_cells_.clear();
    macros_.clear();
    macro_names_.clear();
    pins_.clear();
    pin_names_.clear();
    power_.clear();
    signals_.clear();
    regions_.clear();
    region_names_.clear();
    blockages_.clear();
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

void FastLayoutViewer::load_blockages(const std::vector<float>& x, const std::vector<float>& y, 
                                      const std::vector<float>& w, const std::vector<float>& h) {
    size_t count = x.size();
    blockages_.reserve(blockages_.size() + count);
    for (size_t i = 0; i < count; ++i) {
        blockages_.emplace_back(x[i], y[i], w[i], h[i]);
    }
    update();
}

void FastLayoutViewer::set_heatmap(int mode, const std::vector<float>& data) {
    heatmap_mode_ = mode;
    heatmap_data_ = data;
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
            if (viewport.contains(l.p1()) || viewport.contains(l.p2()) || viewport.intersects(QRectF(l.p1(), l.p2()).normalized())) {
                visible_sigs.push_back(l);
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

    // Draw Tap Cells (Greayer)
    if (zoom_factor_ > lod_std_cells_) {
        painter.setPen(Qt::NoPen);
        painter.setBrush(QColor(128, 128, 128, 255));
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

    // Draw Macros (Bright Orange/Red, solid)
    macro_pen.setColor(QColor(0, 0, 0, 255));
    macro_pen.setCosmetic(true);
    painter.setPen(macro_pen);
    painter.setBrush(QColor(76, 175, 80, 255));
    painter.drawRects(macros_.data(), macros_.size());
    
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
    
    // Draw Heatmap
    if (heatmap_mode_ > 0 && heatmap_data_.size() == 400) {
        float cell_w = core_rect_.width() / 20.0f;
        float cell_h = core_rect_.height() / 20.0f;
        painter.setPen(Qt::NoPen);
        for (int y = 0; y < 20; ++y) {
            for (int x = 0; x < 20; ++x) {
                float intensity = heatmap_data_[y * 20 + x];
                if (intensity > 0) {
                    int r = std::min(255, (int)(intensity * 255));
                    int b = std::min(255, (int)((1.0f - intensity) * 255));
                    painter.fillRect(QRectF(core_rect_.x() + x * cell_w, core_rect_.y() + y * cell_h, cell_w, cell_h), QColor(r, 0, b, 150));
                }
            }
        }
    }
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
    if (angle > 0) zoom_factor_ *= 1.2;
    else zoom_factor_ /= 1.2;
    update();
}

void FastLayoutViewer::mousePressEvent(QMouseEvent* event) {
    if (event->button() == Qt::RightButton || event->button() == Qt::MiddleButton || event->button() == Qt::LeftButton) {
        is_panning_ = true;
        last_mouse_pos_ = event->position();
        setCursor(Qt::ClosedHandCursor);
    }
}

void FastLayoutViewer::mouseMoveEvent(QMouseEvent* event) {
    if (is_panning_) {
        QPointF delta = event->position() - last_mouse_pos_;
        pan_offset_.rx() += delta.x() / zoom_factor_;
        pan_offset_.ry() -= delta.y() / zoom_factor_;
        last_mouse_pos_ = event->position();
        update();
    }
}

void FastLayoutViewer::mouseReleaseEvent(QMouseEvent* event) {
    if (event->button() == Qt::RightButton || event->button() == Qt::MiddleButton || event->button() == Qt::LeftButton) {
        is_panning_ = false;
        setCursor(Qt::ArrowCursor);
    }
}
