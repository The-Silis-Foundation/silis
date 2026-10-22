#pragma once

#include <QWidget>
#include <QPixmap>
#include <QRect>
#include <QPoint>
#include <QEvent>
#include <QWheelEvent>
#include <QMouseEvent>
#include <QPaintEvent>

class RenderThread;

// Mirrors OpenROAD's LayoutViewer
class LayoutViewer : public QWidget {
    Q_OBJECT

public:
    explicit LayoutViewer(QWidget* parent = nullptr);
    ~LayoutViewer();

protected:
    void paintEvent(QPaintEvent* event) override;
    void resizeEvent(QResizeEvent* event) override;
    
    // Zoom/Pan handling
    void wheelEvent(QWheelEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;

private slots:
    void onRenderDone(const QImage& image, const QRect& bounds);

private:
    void requestRender();

    RenderThread* m_renderThread;
    
    QPixmap m_buffer;
    QRect m_bufferRect;
    
    // Viewport transform state
    double m_zoomFactor;
    QPoint m_panOffset;
    
    // Mouse state
    QPoint m_lastMousePos;
    bool m_isPanning;
};
