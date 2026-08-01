#include "FastLayoutViewer.h"
#include <QPainter>
#include <QWheelEvent>
#include <QMouseEvent>

FastLayoutViewer::FastLayoutViewer(QWidget* parent) 
    : QWidget(parent), zoom_factor_(1.0), is_panning_(false) {
    setMouseTracking(true);
    setAttribute(Qt::WA_OpaquePaintEvent); // Skip default background drawing for raw speed
}

void FastLayoutViewer::clear() {
    std_cells_.clear();
    macros_.clear();
    pins_.clear();
    power_.clear();
    signals_.clear();
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
                                   const std::vector<float>& w, const std::vector<float>& h) {
    size_t count = x.size();
    macros_.reserve(macros_.size() + count);
    for (size_t i = 0; i < count; ++i) {
        macros_.emplace_back(x[i], y[i], w[i], h[i]);
    }
    update();
}

void FastLayoutViewer::load_pins(const std::vector<float>& x, const std::vector<float>& y, 
                                 const std::vector<float>& w, const std::vector<float>& h) {
    size_t count = x.size();
    pins_.reserve(pins_.size() + count);
    for (size_t i = 0; i < count; ++i) {
        pins_.emplace_back(x[i], y[i], w[i], h[i]);
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
    // OpenROAD aesthetic: Very dark blue/grey background
    painter.fillRect(rect(), QColor(25, 27, 33));
    painter.setRenderHint(QPainter::Antialiasing, false); 
    
    painter.translate(rect().center());
    painter.scale(zoom_factor_, -zoom_factor_); // Y is flipped in CAD vs Screen
    painter.translate(-core_rect_.center());
    painter.translate(pan_offset_);

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
    painter.drawRects(power_.data(), power_.size());
    
    // Draw Signal Routes
    if (!signals_.empty()) {
        QPen sig_pen(QColor(65, 105, 225, 200)); // Royal Blue
        sig_pen.setCosmetic(true);
        painter.setPen(sig_pen);
        painter.drawLines(signals_.data(), signals_.size());
    }

    // Draw Standard Cells (Solid cyan-ish with dark border)
    QPen std_pen(QColor(0, 50, 100, 100));
    std_pen.setCosmetic(true);
    painter.setPen(std_pen);
    painter.setBrush(QColor(76, 201, 240, 255));
    painter.drawRects(std_cells_.data(), std_cells_.size());

    // Draw Macros (Bright Orange/Red, solid)
    QPen macro_pen(QColor(255, 100, 50));
    macro_pen.setCosmetic(true);
    painter.setPen(macro_pen);
    painter.setBrush(QColor(255, 120, 70, 255));
    painter.drawRects(macros_.data(), macros_.size());
    
    // Draw Pins
    QPen pin_pen(Qt::NoPen);
    painter.setPen(pin_pen);
    painter.setBrush(QColor(255, 0, 0, 255));
    painter.drawRects(pins_.data(), pins_.size());
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
