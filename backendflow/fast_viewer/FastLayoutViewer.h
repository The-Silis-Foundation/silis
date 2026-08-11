#pragma once
#include <QWidget>
#include <vector>
#include <string>
#include <QRectF>
#include <QPointF>

class FastLayoutViewer : public QWidget {
    Q_OBJECT
public:
    explicit FastLayoutViewer(QWidget* parent = nullptr);

    void clear();
    void set_lod(float std_cell_threshold, float nets_threshold);
    void set_core(float x, float y, float w, float h);
    void load_std_cells(const std::vector<float>& x, const std::vector<float>& y, 
                        const std::vector<float>& w, const std::vector<float>& h);
    void load_tap_cells(const std::vector<float>& x, const std::vector<float>& y, 
                        const std::vector<float>& w, const std::vector<float>& h);
    void load_macros(const std::vector<float>& x, const std::vector<float>& y, 
                     const std::vector<float>& w, const std::vector<float>& h,
                     const std::vector<std::string>& names);
    void load_pins(const std::vector<float>& x, const std::vector<float>& y, 
                   const std::vector<float>& w, const std::vector<float>& h,
                   const std::vector<std::string>& names);
    void load_power(const std::vector<float>& x, const std::vector<float>& y, 
                    const std::vector<float>& w, const std::vector<float>& h);
    void load_signals(const std::vector<float>& x1, const std::vector<float>& y1, 
                      const std::vector<float>& x2, const std::vector<float>& y2);
    void load_regions(const std::vector<float>& x, const std::vector<float>& y, 
                      const std::vector<float>& w, const std::vector<float>& h,
                      const std::vector<std::string>& names);
    void load_blockages(const std::vector<float>& x, const std::vector<float>& y, 
                        const std::vector<float>& w, const std::vector<float>& h);
    void set_heatmap(int mode, const std::vector<float>& data);
    void fit_in_view();

protected:
    void paintEvent(QPaintEvent* event) override;
    void wheelEvent(QWheelEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;

private:
    std::vector<QRectF> std_cells_;
    std::vector<QRectF> tap_cells_;
    std::vector<QRectF> macros_;
    std::vector<std::string> macro_names_;
    std::vector<QRectF> pins_;
    std::vector<std::string> pin_names_;
    std::vector<QRectF> power_;
    std::vector<QLineF> signals_;
    std::vector<QRectF> regions_;
    std::vector<std::string> region_names_;
    std::vector<QRectF> blockages_;
    
    QRectF core_rect_;
    double zoom_factor_;
    QPointF pan_offset_;
    bool is_panning_;
    QPointF last_mouse_pos_;
    
    float lod_std_cells_ = 0.03f;
    float lod_nets_ = 0.05f;
    int heatmap_mode_ = 0;
    std::vector<float> heatmap_data_;
};
