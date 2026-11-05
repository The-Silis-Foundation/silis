#pragma once

#include <QThread>
#include <QImage>
#include <QRect>
#include <QMutex>
#include <QWaitCondition>

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
    bool m_abort;
    bool m_restart;
};
