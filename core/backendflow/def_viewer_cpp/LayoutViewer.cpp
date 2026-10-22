#include "LayoutViewer.h"
#include "RenderThread.h"
#include <QPainter>

LayoutViewer::LayoutViewer(QWidget* parent)
    : QWidget(parent),
      m_zoomFactor(1.0),
      m_panOffset(0, 0),
      m_isPanning(false)
{
    setMouseTracking(true);
    setFocusPolicy(Qt::StrongFocus);
    setAttribute(Qt::WA_OpaquePaintEvent); // Optimize drawing

    m_renderThread = new RenderThread(this, this);
    connect(m_renderThread, &RenderThread::done, this, &LayoutViewer::onRenderDone);
}

LayoutViewer::~LayoutViewer() {
    m_renderThread->exitThread();
}

void LayoutViewer::paintEvent(QPaintEvent* event) {
    QPainter painter(this);
    
    // Background
    painter.fillRect(event->rect(), Qt::black);

    // Draw the off-screen buffer
    if (!m_buffer.isNull()) {
        painter.drawPixmap(m_bufferRect.topLeft(), m_buffer);
    }
}

void LayoutViewer::resizeEvent(QResizeEvent* event) {
    QWidget::resizeEvent(event);
    requestRender();
}

void LayoutViewer::requestRender() {
    // The "viewport" we want to render based on current pan and zoom
    QRect targetRect = rect().translated(-m_panOffset);
    // In a full implementation, you would apply m_zoomFactor transform bounds here
    
    m_renderThread->render(targetRect);
}

void LayoutViewer::onRenderDone(const QImage& image, const QRect& bounds) {
    m_buffer = QPixmap::fromImage(image);
    // Map bounds back to screen coordinates
    m_bufferRect = bounds.translated(m_panOffset);
    update();
}

void LayoutViewer::wheelEvent(QWheelEvent* event) {
    // Zoom in/out logic
    if (event->angleDelta().y() > 0) m_zoomFactor *= 1.2;
    else m_zoomFactor /= 1.2;
    requestRender();
}

void LayoutViewer::mousePressEvent(QMouseEvent* event) {
    if (event->button() == Qt::LeftButton) {
        m_isPanning = true;
        m_lastMousePos = event->pos();
        setCursor(Qt::ClosedHandCursor);
    }
}

void LayoutViewer::mouseMoveEvent(QMouseEvent* event) {
    if (m_isPanning) {
        QPoint delta = event->pos() - m_lastMousePos;
        m_panOffset += delta;
        m_bufferRect.translate(delta);
        m_lastMousePos = event->pos();
        update(); // Fast update (pan existing buffer)
    }
}

void LayoutViewer::mouseReleaseEvent(QMouseEvent* event) {
    if (event->button() == Qt::LeftButton && m_isPanning) {
        m_isPanning = false;
        setCursor(Qt::ArrowCursor);
        requestRender(); // Request new high-res buffer now that panning stopped
    }
}
