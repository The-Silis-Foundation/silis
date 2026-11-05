// ==============================================================================
// Silis Native Layer Viewer Canvas
//
// Heartfelt compliments, tribute, and attribution to the incredible OpenROAD
// Project community and contributors (The OpenROAD Authors / Precision Innovations).
// Based on and inspired by the battle-tested architecture and visual precision
// of OpenROAD's LayoutViewer (layoutViewer.cpp / displayControls.cpp).
// ==============================================================================

#pragma once
#include <QWidget>
#include <vector>
#include <string>
#include <map>
#include <QRectF>
#include <QPointF>
#include <QColor>
#include <QRect>
#include <QPoint>

struct LayerShape {
    float x;
    float y;
    float w;
    float h;
};

struct Flightline {
    float x1;
    float y1;
    float x2;
    float y2;
};

class SilisNativeLayerViewer : public QWidget {
    Q_OBJECT
public:
    explicit SilisNativeLayerViewer(QWidget* parent = nullptr);

    void clear();
    void set_core(float x, float y, float w, float h);
    void set_dbu(float dbu);

    // Layer loading
    void load_layer_shapes(const std::string& layer_name, const std::vector<float>& x,
                          const std::vector<float>& y, const std::vector<float>& w,
                          const std::vector<float>& h);
    void set_layer_visible(const std::string& layer_name, bool visible);
    void set_all_layers_visible(bool visible);

    // Instances
    void load_instances(const std::vector<float>& x, const std::vector<float>& y,
                       const std::vector<float>& w, const std::vector<float>& h,
                       const std::vector<std::string>& names,
                       const std::vector<std::string>& masters,
                       const std::vector<bool>& is_macro);

    // Selection & Highlighting
    void select_instance(const std::string& name);
    void clear_selection();

    // Flightlines
    void set_flightlines(const std::vector<float>& x1, const std::vector<float>& y1,
                         const std::vector<float>& x2, const std::vector<float>& y2);
    void clear_flightlines();

    // Navigation & Viewport
    void fit_in_view();
    void pan_to(float x, float y, float target_zoom = -1.0f);
    void zoom_to_box(const QRectF& dbu_box);

    // Ruler
    void set_ruler_active(bool active);
    bool is_ruler_active() const { return ruler_active_; }
    void clear_ruler();

    // Raw pointer for sip.wrapinstance
    uintptr_t get_ptr() { return reinterpret_cast<uintptr_t>(this); }

signals:
    void instance_clicked(const QString& name, const QString& master, float x, float y, float w, float h);
    void area_selected(float x1, float y1, float x2, float y2);
    void canvas_clicked(float x, float y);

protected:
    void paintEvent(QPaintEvent* event) override;
    void wheelEvent(QWheelEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;

private:
    QRectF core_rect_;
    float dbu_ = 1000.0f;
    double zoom_factor_ = 1.0;
    QPointF pan_offset_;
    bool is_panning_ = false;
    QPointF last_mouse_pos_;

    // Exact OpenROAD Marquee Rubberband Selection
    QRect rubber_band_;
    bool rubber_band_showing_ = false;
    QPoint mouse_press_pos_;

    // Layer shapes: "li1", "met1", "met2", "met3", "met4", "met5", "vias"
    std::map<std::string, std::vector<LayerShape>> layers_;
    std::map<std::string, bool> layer_visible_;
    std::map<std::string, QColor> layer_colors_;

    // Placed instances
    struct PlacedInst {
        QRectF rect;
        std::string name;
        std::string master;
        bool is_macro;
    };
    std::vector<PlacedInst> instances_;
    std::map<std::string, size_t> inst_name_index_;

    // Selection
    std::string selected_inst_name_;
    QRectF selected_rect_;

    // Flightlines
    std::vector<Flightline> flightlines_;

    // Ruler
    bool ruler_active_ = false;
    bool ruler_has_start_ = false;
    QPointF ruler_start_;
    QPointF ruler_current_;

    QPointF screen_to_world(const QPointF& screen_pt) const;
    QPointF world_to_screen(const QPointF& world_pt) const;
};
