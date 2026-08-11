import os

h_content = """#pragma once
#include <QOpenGLWidget>
#include <QOpenGLFunctions>
#include <QOpenGLShaderProgram>
#include <QOpenGLBuffer>
#include <QOpenGLVertexArrayObject>
#include <vector>
#include <string>
#include <QRectF>
#include <QPointF>
#include <QLineF>
#include <QPainter>

struct InstanceData {
    float x, y, w, h;
};

struct TextLabel {
    float x, y, w, h;
    std::string text;
    float angle;
};

struct GridBucket {
    int std_cells_start = 0, std_cells_count = 0;
    int macros_start = 0, macros_count = 0;
    int pins_start = 0, pins_count = 0;
    int power_start = 0, power_count = 0;
    int signals_start = 0, signals_count = 0; // for lines
    int regions_start = 0, regions_count = 0;
    int blockages_start = 0, blockages_count = 0;
    int tap_cells_start = 0, tap_cells_count = 0;
};

class FastLayoutViewer : public QOpenGLWidget, protected QOpenGLFunctions {
    Q_OBJECT
public:
    explicit FastLayoutViewer(QWidget* parent = nullptr);
    ~FastLayoutViewer();

    void clear();
    void set_core(float x, float y, float w, float h);
    void load_std_cells(const std::vector<float>& x, const std::vector<float>& y, 
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

    void load_def(const std::string& def_path, const std::vector<std::string>& lef_paths, double default_dbu);
    void set_visibility(bool insts, bool macros, bool pins, bool power, bool nets, bool tapcells);

protected:
    void initializeGL() override;
    void resizeGL(int w, int h) override;
    void paintGL() override;

    void wheelEvent(QWheelEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;

private:
    void buildGridAndUpload();
    void drawInstanced(QOpenGLBuffer& vbo, const QColor& color, int count, int start = 0);
    void drawLines(QOpenGLBuffer& vbo, const QColor& color, int count, int start = 0);

    // Raw Data arrays
    std::vector<InstanceData> std_cells_;
    std::vector<InstanceData> macros_;
    std::vector<InstanceData> pins_;
    std::vector<InstanceData> power_;
    std::vector<float> signals_; // x1, y1, x2, y2
    std::vector<InstanceData> regions_;
    std::vector<InstanceData> blockages_;
    std::vector<InstanceData> tap_cells_;
    
    // Texts
    std::vector<TextLabel> macro_labels_;
    std::vector<TextLabel> pin_labels_;
    std::vector<TextLabel> region_labels_;
    
    // Grid Partitioning (20x20)
    static const int GRID_SIZE = 20;
    std::vector<GridBucket> grid_;
    bool data_dirty_ = false;

    // Ordered data for VBOs
    std::vector<InstanceData> std_cells_ordered_;
    std::vector<InstanceData> macros_ordered_;
    std::vector<InstanceData> pins_ordered_;
    std::vector<InstanceData> power_ordered_;
    std::vector<float> signals_ordered_;
    std::vector<InstanceData> regions_ordered_;
    std::vector<InstanceData> blockages_ordered_;
    std::vector<InstanceData> tap_cells_ordered_;

    // OpenGL objects
    QOpenGLShaderProgram* shader_instanced_ = nullptr;
    QOpenGLShaderProgram* shader_lines_ = nullptr;
    QOpenGLVertexArrayObject vao_instanced_;
    QOpenGLVertexArrayObject vao_lines_;
    QOpenGLBuffer quad_vbo_{QOpenGLBuffer::VertexBuffer};
    
    QOpenGLBuffer std_cells_vbo_{QOpenGLBuffer::VertexBuffer};
    QOpenGLBuffer macros_vbo_{QOpenGLBuffer::VertexBuffer};
    QOpenGLBuffer pins_vbo_{QOpenGLBuffer::VertexBuffer};
    QOpenGLBuffer power_vbo_{QOpenGLBuffer::VertexBuffer};
    QOpenGLBuffer signals_vbo_{QOpenGLBuffer::VertexBuffer};
    QOpenGLBuffer regions_vbo_{QOpenGLBuffer::VertexBuffer};
    QOpenGLBuffer blockages_vbo_{QOpenGLBuffer::VertexBuffer};
    QOpenGLBuffer tap_cells_vbo_{QOpenGLBuffer::VertexBuffer};

    // State
    bool show_insts_ = true;
    bool show_macros_ = true;
    bool show_pins_ = true;
    bool show_power_ = true;
    bool show_nets_ = true;
    bool show_tapcells_ = true;
    
    QRectF core_rect_;
    double zoom_factor_ = 1.0;
    QPointF pan_offset_;
    bool is_panning_ = false;
    QPointF last_mouse_pos_;
    
    int heatmap_mode_ = 0;
    std::vector<float> heatmap_data_;
};
"""

with open("/home/jerome/silis/backendflow/fast_viewer/FastLayoutViewer.h", "w") as f:
    f.write(h_content)
