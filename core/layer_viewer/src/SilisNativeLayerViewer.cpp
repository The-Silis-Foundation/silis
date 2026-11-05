#include "SilisNativeLayerViewer.h"
#include <QPainter>
#include <QPaintEvent>
#include <QWheelEvent>
#include <QMouseEvent>
#include <QFontDatabase>
#include <algorithm>
#include <cmath>

SilisNativeLayerViewer::SilisNativeLayerViewer(QWidget* parent)
    : QWidget(parent) {
    setAttribute(Qt::WA_OpaquePaintEvent);
    setAttribute(Qt::WA_NoSystemBackground);
    setMouseTracking(true);

    // Standard ASIC layer color palette (Sky130 convention)
    layer_colors_["li1"]  = QColor(140, 100, 220, 190); // Violet
    layer_colors_["met1"] = QColor(65, 135, 245, 190);  // Blue
    layer_colors_["met2"] = QColor(245, 160, 45, 190);  // Orange
    layer_colors_["met3"] = QColor(50, 205, 120, 190);  // Emerald Green
    layer_colors_["met4"] = QColor(230, 75, 150, 190);  // Magenta
    layer_colors_["met5"] = QColor(240, 220, 50, 190);  // Gold / Yellow
    layer_colors_["vias"] = QColor(200, 200, 200, 220); // Silver / White

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
    flightlines_.clear();
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
                                           const std::vector<bool>& is_macro) {
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
        inst_name_index_[names[i]] = instances_.size();
        instances_.push_back(inst);
    }
    update();
}

void SilisNativeLayerViewer::select_instance(const std::string& name) {
    selected_inst_name_ = name;
    auto it = inst_name_index_.find(name);
    if (it != inst_name_index_.end()) {
        selected_rect_ = instances_[it->second].rect;
    } else {
        selected_rect_ = QRectF();
    }
    update();
}

void SilisNativeLayerViewer::clear_selection() {
    selected_inst_name_.clear();
    selected_rect_ = QRectF();
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

    // Dark EDA Canvas Background (#161618)
    p.fillRect(rect(), QColor(22, 22, 24));

    if (core_rect_.isNull()) {
        p.setPen(QColor(120, 120, 120));
        p.drawText(rect(), Qt::AlignCenter, "Silis Native Layer Viewer\nNo DEF / LEF Layout Loaded");
        return;
    }

    // Viewport transform
    p.save();
    p.translate(width() / 2.0, height() / 2.0);
    p.scale(zoom_factor_, -zoom_factor_);
    p.translate(-core_rect_.center().x() + pan_offset_.x(),
                -core_rect_.center().y() + pan_offset_.y());

    // 1. Draw Die / Core Boundary
    p.setPen(QPen(QColor(80, 80, 90), 1.0 / zoom_factor_));
    p.setBrush(QColor(28, 28, 32));
    p.drawRect(core_rect_);

    // 2. Render Placed Macros & Block Outlines
    for (const auto& inst : instances_) {
        if (!inst.is_macro) continue;
        p.setPen(QPen(QColor(200, 140, 40), 1.5 / zoom_factor_));
        p.setBrush(QColor(50, 40, 25, 180));
        p.drawRect(inst.rect);
    }

    // 3. Render Metal & Via Layers
    const std::vector<std::string> render_order = {"li1", "vias", "met1", "met2", "met3", "met4", "met5"};
    for (const auto& lname : render_order) {
        auto it_vis = layer_visible_.find(lname);
        if (it_vis != layer_visible_.end() && !it_vis->second) continue;

        auto it_layer = layers_.find(lname);
        if (it_layer == layers_.end() || it_layer->second.empty()) continue;

        QColor color = layer_colors_[lname];
        p.setPen(Qt::NoPen);
        p.setBrush(color);

        for (const auto& s : it_layer->second) {
            p.drawRect(QRectF(s.x, s.y, s.w, s.h));
        }
    }

    // 4. Render Flightlines (Net connectivity)
    if (!flightlines_.empty()) {
        p.setPen(QPen(QColor(255, 230, 40, 220), 1.8 / zoom_factor_, Qt::DashLine));
        for (const auto& fl : flightlines_) {
            p.drawLine(QPointF(fl.x1, fl.y1), QPointF(fl.x2, fl.y2));
        }
    }

    // 5. Render Selected Highlight Box
    if (!selected_rect_.isNull()) {
        // High-contrast pulsating / bright yellow-white selection box
        p.setPen(QPen(QColor(255, 255, 255), 2.5 / zoom_factor_));
        p.setBrush(QColor(255, 240, 0, 80));
        p.drawRect(selected_rect_);

        // Outer halo
        p.setPen(QPen(QColor(255, 200, 0, 180), 1.0 / zoom_factor_, Qt::DotLine));
        p.setBrush(Qt::NoBrush);
        p.drawRect(selected_rect_.adjusted(-4.0 / zoom_factor_, -4.0 / zoom_factor_, 4.0 / zoom_factor_, 4.0 / zoom_factor_));
    }

    p.restore();

    // 6. Screen-space HUD & Ruler Overlay
    if (ruler_active_ && ruler_has_start_) {
        QPointF s1 = world_to_screen(ruler_start_);
        QPointF s2 = world_to_screen(ruler_current_);

        p.setPen(QPen(QColor(255, 80, 80), 2.0));
        p.drawLine(s1, s2);
        p.setBrush(QColor(255, 80, 80));
        p.drawEllipse(s1, 4, 4);
        p.drawEllipse(s2, 4, 4);

        // Compute physical distance in microns
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
        p.setBrush(QColor(20, 20, 24, 210));
        p.drawRoundedRect(text_rect, 4, 4);

        p.setPen(QColor(255, 255, 255));
        p.drawText(text_rect, Qt::AlignCenter, ruler_str);
    }

    // Top-left design status HUD
    if (!selected_inst_name_.empty()) {
        QFont hud_font = QFontDatabase::systemFont(QFontDatabase::SystemFont::FixedFont);
        hud_font.setPointSize(9);
        p.setFont(hud_font);

        QString hud_text = QString("Selected: %1 | Bounds: (%2, %3) to (%4, %5) µm")
                               .arg(QString::fromStdString(selected_inst_name_))
                               .arg(selected_rect_.left() / dbu_, 0, 'f', 3)
                               .arg(selected_rect_.bottom() / dbu_, 0, 'f', 3)
                               .arg(selected_rect_.right() / dbu_, 0, 'f', 3)
                               .arg(selected_rect_.top() / dbu_, 0, 'f', 3);

        QRect hud_rect = p.fontMetrics().boundingRect(hud_text).adjusted(-8, -4, 8, 4);
        hud_rect.moveTo(10, 10);

        p.setPen(Qt::NoPen);
        p.setBrush(QColor(20, 20, 24, 210));
        p.drawRoundedRect(hud_rect, 4, 4);

        p.setPen(QColor(255, 220, 50));
        p.drawText(hud_rect, Qt::AlignCenter, hud_text);
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

    // Anchor zoom around cursor position
    QPointF mouse_pos = event->position();
    double center_x = width() / 2.0;
    double center_y = height() / 2.0;
    pan_offset_.rx() += (mouse_pos.x() - center_x) * (1.0 / zoom_factor_ - 1.0 / old_zoom);
    pan_offset_.ry() -= (mouse_pos.y() - center_y) * (1.0 / zoom_factor_ - 1.0 / old_zoom);

    update();
}

void SilisNativeLayerViewer::mousePressEvent(QMouseEvent* event) {
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

    if (event->button() == Qt::LeftButton) {
        // Hit test instances (macros first, then std cells)
        int best_hit = -1;
        double best_area = 1e20;

        for (size_t i = 0; i < instances_.size(); ++i) {
            const auto& inst = instances_[i];
            if (inst.rect.contains(wpos)) {
                double area = inst.rect.width() * inst.rect.height();
                // Pick the smallest containing instance for precision (e.g. pin inside macro)
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
            clear_selection();
            emit canvas_clicked(wpos.x(), wpos.y());
        }
    }

    if (event->button() == Qt::RightButton || event->button() == Qt::MiddleButton) {
        is_panning_ = true;
        last_mouse_pos_ = event->position();
        setCursor(Qt::ClosedHandCursor);
    }
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
    }
}

void SilisNativeLayerViewer::mouseReleaseEvent(QMouseEvent* event) {
    if (event->button() == Qt::RightButton || event->button() == Qt::MiddleButton) {
        is_panning_ = false;
        setCursor(ruler_active_ ? Qt::CrossCursor : Qt::ArrowCursor);
    }
}
