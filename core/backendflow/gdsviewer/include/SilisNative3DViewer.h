#pragma once

#include <QOpenGLWidget>
#include <QOpenGLFunctions_3_3_Core>
#include <QOpenGLShaderProgram>
#include <QOpenGLBuffer>
#include <QOpenGLVertexArrayObject>
#include <QMatrix4x4>
#include <QVector3D>
#include <QVector4D>
#include <QPoint>
#include <QMouseEvent>
#include <QWheelEvent>
#include <QKeyEvent>
#include <QTimer>
#include <QEvent>
#include <QFocusEvent>

#include <string>
#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <cstdint>

struct Layer3DBatch {
    std::string name;
    float z_min = 0.0f;
    float z_max = 1.0f;
    QVector4D color = QVector4D(0.4f, 0.7f, 1.0f, 1.0f);
    bool visible = true;
    std::vector<float> instances; // packed [x, y, w, h] * N
    GLuint instance_vbo = 0;
    size_t instance_count = 0;
    bool dirty = false;
};

class SilisNative3DViewer : public QOpenGLWidget, protected QOpenGLFunctions_3_3_Core {
    Q_OBJECT
public:
    explicit SilisNative3DViewer(QWidget* parent = nullptr);
    ~SilisNative3DViewer() override;

    void clear();
    void setBounds(float min_x, float min_y, float max_x, float max_y);
    void setLayerData(
        const std::string& name,
        const std::vector<float>& x,
        const std::vector<float>& y,
        const std::vector<float>& w,
        const std::vector<float>& h,
        float z_min,
        float z_max,
        float r, float g, float b, float a
    );
    void setLayerVisible(const std::string& name, bool visible);
    void setZScale(float scale);
    void setClipZ(float max_z);
    void setCameraPreset(const std::string& preset);
    void fitInView();
    uintptr_t getPtr() const;

protected:
    void initializeGL() override;
    void resizeGL(int w, int h) override;
    void paintGL() override;

    bool event(QEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void wheelEvent(QWheelEvent* event) override;
    void keyPressEvent(QKeyEvent* event) override;
    void keyReleaseEvent(QKeyEvent* event) override;
    void focusOutEvent(QFocusEvent* event) override;

private:
    void tickCamera();
    void uploadDirtyBatches();
    void buildCubeGeometry();

    QOpenGLShaderProgram* m_program = nullptr;
    QOpenGLVertexArrayObject m_vao;
    QOpenGLBuffer m_cube_vbo{QOpenGLBuffer::VertexBuffer};
    QOpenGLBuffer m_cube_ebo{QOpenGLBuffer::IndexBuffer};
    bool m_gl_ready = false;

    std::vector<Layer3DBatch> m_batches;
    std::unordered_map<std::string, size_t> m_batch_map;

    float m_min_x = 0.0f, m_min_y = 0.0f, m_max_x = 100.0f, m_max_y = 100.0f;
    float m_max_z_stack = 15.0f;
    float m_z_scale = 1.0f;
    float m_clip_z = 1000.0f;

    // Orbit camera
    QVector3D m_target = QVector3D(50.0f, 50.0f, 0.0f);
    float m_distance = 160.0f;
    float m_yaw = 45.0f;
    float m_pitch = 35.0f;

    QPoint m_last_mouse;
    Qt::MouseButton m_drag_btn = Qt::NoButton;
    bool m_mouse_look = false;
    std::unordered_set<int> m_keys;
    QTimer* m_fly_timer = nullptr;
};
