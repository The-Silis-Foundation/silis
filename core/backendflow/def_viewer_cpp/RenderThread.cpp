#include "RenderThread.h"
#include "LayoutViewer.h"
#include <QPainter>
#include <QDebug>

RenderThread::RenderThread(LayoutViewer* viewer, QObject* parent)
    : QThread(parent), m_viewer(viewer), m_abort(false), m_restart(false) {}

RenderThread::~RenderThread() {
    exitThread();
}

void RenderThread::exitThread() {
    m_mutex.lock();
    m_abort = true;
    m_condition.wakeOne();
    m_mutex.unlock();
    wait();
}

void RenderThread::render(const QRect& draw_rect) {
    if (m_abort) return;

    QMutexLocker locker(&m_mutex);
    m_drawRect = draw_rect;

    if (!isRunning()) {
        start(LowPriority);
    } else {
        m_restart = true;
        m_condition.wakeOne();
    }
}

void RenderThread::run() {
    forever {
        m_mutex.lock();
        QRect draw_bounds = m_drawRect;
        m_mutex.unlock();

        // 1. Setup Image Buffer
        QImage image(draw_bounds.size(), QImage::Format_ARGB32_Premultiplied);
        image.fill(Qt::black);

        // 2. Offscreen painting using Cosmetic Pens (OpenROAD logic)
        try {
            QPainter painter(&image);
            painter.setRenderHint(QPainter::Antialiasing);

            // Shift coordinate system so top-left of draw_bounds is at (0,0) in the image buffer
            painter.translate(-draw_bounds.topLeft());

            // --- DRAWING LOGIC ---
            // A mock wire mimicking OpenROAD cosmetic tracks
            QPen metalPen(QColor(100, 200, 255));
            metalPen.setCosmetic(true); // <--- CRITICAL OpenROAD feature for EDA
            painter.setPen(metalPen);
            
            // Draw a grid of boxes to simulate a massive layout
            int step = 100;
            for (int x = draw_bounds.left(); x < draw_bounds.right(); x += step) {
                for (int y = draw_bounds.top(); y < draw_bounds.bottom(); y += step) {
                    painter.drawRect(x, y, step - 10, step - 10);
                }
            }
            // ---------------------

            painter.end();
        } catch (...) {
            qWarning() << "Rendering exception!";
        }

        if (!m_restart) {
            emit done(image, draw_bounds);
        }

        if (m_abort) return;

        m_mutex.lock();
        if (!m_restart) {
            m_condition.wait(&m_mutex);
        }
        m_restart = false;
        m_mutex.unlock();
    }
}
