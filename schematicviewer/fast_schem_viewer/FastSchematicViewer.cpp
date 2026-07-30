#include "FastSchematicViewer.h"
#include <QPainter>
#include <QWheelEvent>
#include <QMouseEvent>
#include <QPainterPath>
#include <QPen>
#include <QBrush>
#include <QFont>
#include <QFontMetrics>
#include <cmath>
#include <iostream>

FastSchematicViewer::FastSchematicViewer(QWidget* parent) 
    : QWidget(parent), zoom_factor_(1.0), is_panning_(false) {
    setMouseTracking(true);
    setAttribute(Qt::WA_OpaquePaintEvent); // Skip default background drawing for speed
}

void FastSchematicViewer::clear() {
    blocks_.clear();
    ports_.clear();
    wires_.clear();
    junctions_.clear();
    dots_.clear();
    bounding_rect_ = QRectF();
    update();
}

void FastSchematicViewer::update_bounding_rect() {
    if (blocks_.empty() && ports_.empty()) return;
    
    float min_x = 1e9, min_y = 1e9;
    float max_x = -1e9, max_y = -1e9;
    
    for (const auto& b : blocks_) {
        if (b.rect.left() < min_x) min_x = b.rect.left();
        if (b.rect.right() > max_x) max_x = b.rect.right();
        if (b.rect.top() < min_y) min_y = b.rect.top();
        if (b.rect.bottom() > max_y) max_y = b.rect.bottom();
    }
    
    for (const auto& p : ports_) {
        if (p.rect.left() < min_x) min_x = p.rect.left();
        if (p.rect.right() > max_x) max_x = p.rect.right();
        if (p.rect.top() < min_y) min_y = p.rect.top();
        if (p.rect.bottom() > max_y) max_y = p.rect.bottom();
    }
    
    for (const auto& l : wires_) {
        if (l.line.x1() < min_x) min_x = l.line.x1();
        if (l.line.x2() < min_x) min_x = l.line.x2();
        if (l.line.y1() < min_y) min_y = l.line.y1();
        if (l.line.y2() < min_y) min_y = l.line.y2();
        
        if (l.line.x1() > max_x) max_x = l.line.x1();
        if (l.line.x2() > max_x) max_x = l.line.x2();
        if (l.line.y1() > max_y) max_y = l.line.y1();
        if (l.line.y2() > max_y) max_y = l.line.y2();
    }
    
    bounding_rect_ = QRectF(QPointF(min_x, min_y), QPointF(max_x, max_y));
}

void FastSchematicViewer::load_blocks(const std::vector<float>& x, const std::vector<float>& y, 
                                     const std::vector<float>& w, const std::vector<float>& h,
                                     const std::vector<std::string>& names, const std::vector<std::string>& types,
                                     const std::vector<bool>& is_tops) {
    size_t count = x.size();
    blocks_.reserve(blocks_.size() + count);
    for (size_t i = 0; i < count; ++i) {
        blocks_.push_back({QRectF(x[i], y[i], w[i], h[i]), names[i], types[i], is_tops[i]});
    }
    update_bounding_rect();
    update();
}

void FastSchematicViewer::load_ports(const std::vector<float>& x, const std::vector<float>& y, 
                                     const std::vector<std::string>& names, const std::vector<std::string>& directions,
                                     const std::vector<bool>& is_lefts) {
    size_t count = x.size();
    ports_.reserve(ports_.size() + count);
    for (size_t i = 0; i < count; ++i) {
        ports_.push_back({QRectF(x[i], y[i], 10, 10), names[i], directions[i], is_lefts[i]});
    }
    update_bounding_rect();
    update();
}

void FastSchematicViewer::load_wires(const std::vector<float>& x1, const std::vector<float>& y1, 
                                     const std::vector<float>& x2, const std::vector<float>& y2,
                                     const std::vector<bool>& is_bus, const std::vector<bool>& is_gap) {
    size_t count = x1.size();
    wires_.reserve(wires_.size() + count);
    for (size_t i = 0; i < count; ++i) {
        wires_.push_back({QLineF(x1[i], y1[i], x2[i], y2[i]), is_bus[i], is_gap[i]});
    }
    update_bounding_rect();
    update();
}

void FastSchematicViewer::load_junctions(const std::vector<float>& x, const std::vector<float>& y) {
    size_t count = x.size();
    junctions_.reserve(junctions_.size() + count);
    for (size_t i = 0; i < count; ++i) {
        junctions_.emplace_back(x[i], y[i]);
    }
    update();
}

void FastSchematicViewer::load_dots(const std::vector<float>& x, const std::vector<float>& y,
                                    const std::vector<std::string>& text) {
    size_t count = x.size();
    dots_.reserve(dots_.size() + count);
    for (size_t i = 0; i < count; ++i) {
        dots_.push_back({QPointF(x[i], y[i]), text[i]});
    }
    update();
}

std::string FastSchematicViewer::hit_test(float x, float y) {
    // x and y are viewport coordinates. Convert to scene coordinates.
    // wait, Python's hit_test usually gives the viewport coordinates.
    // We should map x, y to scene coordinates.
    float scene_x = (x - rect().center().x() - pan_offset_.x()) / zoom_factor_ + bounding_rect_.center().x();
    float scene_y = (y - rect().center().y() - pan_offset_.y()) / zoom_factor_ + bounding_rect_.center().y();
    
    QPointF pt(scene_x, scene_y);
    // Iterate backwards to hit the topmost items first
    for (auto it = blocks_.rbegin(); it != blocks_.rend(); ++it) {
        if (it->rect.contains(pt) && it->type != "BOUNDARY") {
            return it->type;
        }
    }
    return "";
}

void FastSchematicViewer::fit_in_view() {
    if (bounding_rect_.isNull() || bounding_rect_.width() == 0 || bounding_rect_.height() == 0) return;
    double w = width();
    double h = height();
    if (w <= 0 || h <= 0) {
        w = 800;
        h = 600;
    }
    double scale_x = w / (bounding_rect_.width() * 1.1);
    double scale_y = h / (bounding_rect_.height() * 1.1);
    zoom_factor_ = std::min(scale_x, scale_y);
    if (zoom_factor_ <= 0) zoom_factor_ = 1.0;
    pan_offset_ = QPointF(0, 0); // Center
    update();
}

void FastSchematicViewer::paintEvent(QPaintEvent* event) {
    QPainter painter(this);
    // Dark schematic background
    painter.fillRect(rect(), QColor(25, 27, 33));
    painter.setRenderHint(QPainter::Antialiasing, true);
    
    painter.translate(rect().center());
    painter.scale(zoom_factor_, zoom_factor_); // Note: not flipped like layout
    painter.translate(-bounding_rect_.center());
    painter.translate(pan_offset_);

    QFont font("Consolas", 8);
    painter.setFont(font);

    // Draw Wires
    for (const auto& w : wires_) {
        float thickness = w.is_bus ? 3.5f : 2.0f;
        QColor color = w.is_gap ? QColor(224, 108, 117) : (w.is_bus ? QColor(229, 192, 123) : QColor(209, 154, 102));
        if (w.is_gap) thickness += 0.5f;
        
        QPen wire_pen(color, thickness);
        wire_pen.setCosmetic(true);
        painter.setPen(wire_pen);
        painter.drawLine(w.line);
    }
    
    // Draw Junctions
    painter.setBrush(QColor(198, 120, 221)); // Purple
    painter.setPen(Qt::NoPen);
    for (const auto& j : junctions_) {
        painter.drawRect(QRectF(j.x() - 3, j.y() - 3, 6, 6));
    }
    
    // Draw Dots
    painter.setBrush(QColor(152, 195, 121)); // Green
    for (const auto& d : dots_) {
        painter.drawEllipse(d.pos, 3.0, 3.0);
        if (!d.text.empty()) {
            painter.setPen(QColor(171, 178, 191));
            QFont dot_font("Consolas", 7);
            painter.setFont(dot_font);
            painter.drawText(QPointF(d.pos.x() + 5, d.pos.y() - 15), QString::fromStdString(d.text));
            painter.setPen(Qt::NoPen);
            painter.setBrush(QColor(152, 195, 121));
        }
    }

    // Draw Blocks
    for (const auto& b : blocks_) {
        // Block background
        painter.setBrush(QColor(40, 44, 52, 255)); 
        QPen block_pen(b.is_top ? QColor(97, 175, 239) : QColor(152, 195, 121), 2);
        block_pen.setCosmetic(true);
        painter.setPen(block_pen);
        painter.drawRect(b.rect);

        // Block Title
        painter.setPen(QColor(229, 192, 123)); // Yellowish text
        QFont title_font("Consolas", 9, QFont::Bold);
        painter.setFont(title_font);
        
        QString title_text = QString::fromStdString(b.name);
        if (b.name != b.type && !b.is_top) {
            title_text = QString("ID: %1\nType: %2").arg(QString::fromStdString(b.name), QString::fromStdString(b.type));
        }

        QRectF text_rect = painter.boundingRect(b.rect, Qt::AlignTop | Qt::AlignHCenter, title_text);
        text_rect.translate(0, 5); // 5px padding from top
        painter.drawText(text_rect, Qt::AlignTop | Qt::AlignHCenter, title_text);
    }

    // Draw Ports
    painter.setFont(font); // Reset font
    for (const auto& p : ports_) {
        // Port Box
        painter.setBrush(p.direction == "input" ? QColor(97, 175, 239) : QColor(224, 108, 117));
        painter.setPen(Qt::NoPen);
        painter.drawRect(p.rect);

        // Port Label
        painter.setPen(QColor(171, 178, 191)); // Greyish text
        QFontMetrics fm(font);
        QString text = QString::fromStdString(p.name);
        int tw = fm.horizontalAdvance(text);
        
        float tx = p.is_left ? (p.rect.x() + 15) : (p.rect.x() - tw - 5);
        float ty = p.rect.y() + 8; // approx center
        painter.drawText(QPointF(tx, ty), text);
    }
}

void FastSchematicViewer::wheelEvent(QWheelEvent* event) {
    double angle = event->angleDelta().y();
    if (angle > 0) zoom_factor_ *= 1.15;
    else zoom_factor_ /= 1.15;
    update();
}

void FastSchematicViewer::mousePressEvent(QMouseEvent* event) {
    if (event->button() == Qt::MiddleButton || event->button() == Qt::LeftButton) {
        is_panning_ = true;
        last_mouse_pos_ = event->position();
        setCursor(Qt::ClosedHandCursor);
    }
}

void FastSchematicViewer::mouseMoveEvent(QMouseEvent* event) {
    if (is_panning_) {
        QPointF delta = event->position() - last_mouse_pos_;
        pan_offset_ += delta / zoom_factor_;
        last_mouse_pos_ = event->position();
        update();
    }
}

void FastSchematicViewer::mouseReleaseEvent(QMouseEvent* event) {
    if (event->button() == Qt::MiddleButton || event->button() == Qt::LeftButton) {
        is_panning_ = false;
        setCursor(Qt::ArrowCursor);
    }
}

void FastSchematicViewer::mouseDoubleClickEvent(QMouseEvent* event) {
    // We could emit signals here if a block is double-clicked for hierarchy navigation!
    // But currently we'll handle this in Python. 
    // Wait, QMouseEvent in C++ doesn't easily emit to Python unless we pass a callback.
    // For now, let's keep it simple.
    QWidget::mouseDoubleClickEvent(event);
}
