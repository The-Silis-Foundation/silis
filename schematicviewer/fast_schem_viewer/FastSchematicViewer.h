#pragma once
#include <QWidget>
#include <vector>
#include <string>
#include <QRectF>
#include <QPointF>
#include <QLineF>

class FastSchematicViewer : public QWidget {
    Q_OBJECT
public:
    FastSchematicViewer(QWidget* parent = nullptr);

    // load_blocks: x, y, w, h, name, type, is_top
    void load_blocks(const std::vector<float>& x, const std::vector<float>& y, 
                     const std::vector<float>& w, const std::vector<float>& h,
                     const std::vector<std::string>& names, const std::vector<std::string>& types,
                     const std::vector<bool>& is_tops);

    // load_ports: x, y, name, direction, is_left
    void load_ports(const std::vector<float>& x, const std::vector<float>& y, 
                    const std::vector<std::string>& names, const std::vector<std::string>& directions,
                    const std::vector<bool>& is_lefts);

    // load_wires: array of lines with metadata
    void load_wires(const std::vector<float>& x1, const std::vector<float>& y1, 
                    const std::vector<float>& x2, const std::vector<float>& y2,
                    const std::vector<bool>& is_bus, const std::vector<bool>& is_gap);

    // load_junctions: array of x,y coordinates
    void load_junctions(const std::vector<float>& x, const std::vector<float>& y);

    // load_dots: array of x,y coordinates and text
    void load_dots(const std::vector<float>& x, const std::vector<float>& y,
                   const std::vector<std::string>& text);

    // hit_test returns the type name of the block at x,y. Returns empty string if none.
    std::string hit_test(float x, float y);

    void fit_in_view();
    void clear();

protected:
    void paintEvent(QPaintEvent* event) override;
    void wheelEvent(QWheelEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;
    void mouseDoubleClickEvent(QMouseEvent* event) override;

private:
    struct Block {
        QRectF rect;
        std::string name;
        std::string type;
        bool is_top;
    };
    
    struct Port {
        QRectF rect;
        std::string name;
        std::string direction;
        bool is_left;
    };

    struct Wire {
        QLineF line;
        bool is_bus;
        bool is_gap;
    };
    
    struct Dot {
        QPointF pos;
        std::string text;
    };

    std::vector<Block> blocks_;
    std::vector<Port> ports_;
    std::vector<Wire> wires_;
    std::vector<QPointF> junctions_;
    std::vector<Dot> dots_;
    
    double zoom_factor_;
    QPointF pan_offset_;
    bool is_panning_;
    QPointF last_mouse_pos_;
    
    QRectF bounding_rect_;
    void update_bounding_rect();
};
