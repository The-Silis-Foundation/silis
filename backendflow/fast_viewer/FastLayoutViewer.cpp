#include "FastLayoutViewer.h"
#include <QPainter>
#include <QWheelEvent>
#include <QMouseEvent>
#include <QPen>

FastLayoutViewer::FastLayoutViewer(QWidget* parent) 
    : QWidget(parent), zoom_factor_(1.0), is_panning_(false) {
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
    update();
}

void FastLayoutViewer::set_core(float x, float y, float w, float h) {
    core_rect_ = QRectF(x, y, w, h);
    update();
}

void FastLayoutViewer::load_std_cells(const std::vector<float>& x, const std::vector<float>& y, 
                                     const std::vector<float>& w, const std::vector<float>& h) {
    size_t count = x.size();
    std_cells_.reserve(std_cells_.size() + count);
    for (size_t i = 0; i < count; ++i) {
        std_cells_.emplace_back(x[i], y[i], w[i], h[i]);
    }
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
    // Use the color config from the simplified viewer
    // Background #2D323A
    painter.fillRect(rect(), QColor(45, 50, 58));
    painter.setRenderHint(QPainter::Antialiasing, false); 
    
    painter.translate(rect().center());
    painter.scale(zoom_factor_, -zoom_factor_); // Y is flipped in CAD vs Screen
    painter.translate(-core_rect_.center());
    painter.translate(pan_offset_);

    // Draw Core Box #4A5568
    QPen core_pen(QColor(74, 85, 104));
    core_pen.setWidth(0);
    core_pen.setCosmetic(true);
    painter.setPen(core_pen);
    painter.setBrush(Qt::NoBrush);
    painter.drawRect(core_rect_);
    
    // Draw Power Rails #ffaa00
    QPen pwr_pen(Qt::NoPen);
    painter.setPen(pwr_pen);
    painter.setBrush(QColor(255, 170, 0, 150));
    painter.drawRects(power_.data(), power_.size());
    
    // Draw Signal Routes #4169E1
    if (!signals_.empty()) {
        QPen sig_pen(QColor(65, 105, 225, 200));
        sig_pen.setCosmetic(true);
        painter.setPen(sig_pen);
        painter.drawLines(signals_.data(), signals_.size());
    }

    // Draw Standard Cells #4cc9f0, outline #00509d
    QPen std_pen(QColor(0, 80, 157, 100));
    std_pen.setCosmetic(true);
    painter.setPen(std_pen);
    painter.setBrush(QColor(76, 201, 240, 255));
    painter.drawRects(std_cells_.data(), std_cells_.size());

    // Draw Blockages
    QPen blk_pen(QColor(150, 150, 150, 255));
    blk_pen.setCosmetic(true);
    painter.setPen(blk_pen);
    painter.setBrush(QColor(100, 100, 100, 100)); // transparent grey
    painter.drawRects(blockages_.data(), blockages_.size());

    // Draw Regions
    QPen reg_pen(QColor(255, 255, 0, 200)); // Yellow outline
    reg_pen.setCosmetic(true);
    painter.setPen(reg_pen);
    painter.setBrush(QColor(255, 255, 0, 30)); // very transparent yellow
    painter.drawRects(regions_.data(), regions_.size());

    // Draw Macros #4CAF50, outline black
    QPen macro_pen(QColor(0, 0, 0, 255));
    macro_pen.setCosmetic(true);
    painter.setPen(macro_pen);
    painter.setBrush(QColor(76, 175, 80, 255));
    painter.drawRects(macros_.data(), macros_.size());
    
    // Draw Pins #ff0000, outline black
    QPen pin_pen(QColor(0, 0, 0, 255));
    pin_pen.setCosmetic(true);
    painter.setPen(pin_pen);
    painter.setBrush(QColor(255, 0, 0, 255));
    painter.drawRects(pins_.data(), pins_.size());

    // We must draw text uninverted.
    painter.save();
    // Un-invert the Y-axis for text rendering
    painter.scale(1.0 / zoom_factor_, -1.0 / zoom_factor_);
    painter.setPen(QPen(Qt::black));
    
    for (size_t i = 0; i < macros_.size(); i++) {
        if (!macro_names_[i].empty()) {
            QPointF p = macros_[i].center();
            // Transform point to screen space
            double sx = p.x() * zoom_factor_;
            double sy = p.y() * -zoom_factor_;
            painter.drawText(sx - 20, sy, QString::fromStdString(macro_names_[i]));
        }
    }
    
    for (size_t i = 0; i < pins_.size(); i++) {
        if (!pin_names_[i].empty()) {
            QPointF p = pins_[i].center();
            double sx = p.x() * zoom_factor_;
            double sy = p.y() * -zoom_factor_;
            painter.drawText(sx - 10, sy, QString::fromStdString(pin_names_[i]));
        }
    }

    for (size_t i = 0; i < regions_.size(); i++) {
        if (!region_names_[i].empty()) {
            QPointF p = regions_[i].center();
            double sx = p.x() * zoom_factor_;
            double sy = p.y() * -zoom_factor_;
            painter.setPen(QPen(Qt::yellow));
            painter.drawText(sx - 20, sy, QString::fromStdString(region_names_[i]));
        }
    }
    painter.restore();
    
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

void FastLayoutViewer::wheelEvent(QWheelEvent* event) {
    double angle = event->angleDelta().y();
    if (angle > 0) zoom_factor_ *= 1.2;
    else zoom_factor_ /= 1.2;
    update();
}

void FastLayoutViewer::mousePressEvent(QMouseEvent* event) {
    if (event->button() == Qt::MiddleButton || event->button() == Qt::LeftButton) {
        is_panning_ = true;
        last_mouse_pos_ = event->position();
        setCursor(Qt::ClosedHandCursor);
    }
}

void FastLayoutViewer::mouseMoveEvent(QMouseEvent* event) {
    if (is_panning_) {
        QPointF delta = event->position() - last_mouse_pos_;
        pan_offset_ += delta / zoom_factor_;
        last_mouse_pos_ = event->position();
        update();
    }
}

void FastLayoutViewer::mouseReleaseEvent(QMouseEvent* event) {
    if (event->button() == Qt::MiddleButton || event->button() == Qt::LeftButton) {
        is_panning_ = false;
        setCursor(Qt::ArrowCursor);
    }
}
