#pragma once

#include <QThread>
#include <QImage>
#include <QRect>
#include <QMutex>
#include <QWaitCondition>
#include <atomic>

class LayoutViewer;

// Mirrors OpenROAD's RenderThread
class RenderThread : public QThread {
    Q_OBJECT

public:
    explicit RenderThread(LayoutViewer* viewer, QObject* parent = nullptr);
    ~RenderThread();

    void render(const QRect& draw_rect);
    void exitThread();

signals:
    void done(const QImage& image, const QRect& bounds);

protected:
    void run() override;

private:
    LayoutViewer* m_viewer;
    QMutex m_mutex;
    QWaitCondition m_condition;
    
    QRect m_drawRect;
    std::atomic<bool> m_abort{false};
    bool m_restart;
};
