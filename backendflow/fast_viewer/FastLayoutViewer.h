#pragma once
#include <QWidget>
#include <vector>
#include <QRectF>
#include <QPointF>

class FastLayoutViewer : public QWidget {
    Q_OBJECT
public:
    FastLayoutViewer(QWidget* parent = nullptr);
    void set_core(float x, float y, float w, float h);
    void load_std_cells(const std::vector<float>& x, const std::vector<float>& y, const std::vector<float>& w, const std::vector<float>& h);
    void load_macros(const std::vector<float>& x, const std::vector<float>& y, const std::vector<float>& w, const std::vector<float>& h);
    void load_pins(const std::vector<float>& x, const std::vector<float>& y, const std::vector<float>& w, const std::vector<float>& h);
    void load_power(const std::vector<float>& x, const std::vector<float>& y, const std::vector<float>& w, const std::vector<float>& h);
    void fit_in_view();
    void clear();
protected:
    void paintEvent(QPaintEvent* event) override;
    void wheelEvent(QWheelEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;
private:
    QRectF core_rect_;
    std::vector<QRectF> std_cells_;
    std::vector<QRectF> macros_;
    std::vector<QRectF> pins_;
    std::vector<QRectF> power_;
    double zoom_factor_;
    QPointF pan_offset_;
    bool is_panning_;
    QPointF last_mouse_pos_;
};
