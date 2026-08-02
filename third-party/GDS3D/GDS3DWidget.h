#pragma once

#include <QOpenGLWidget>
#include <QOpenGLFunctions>
#include <QMouseEvent>
#include <QKeyEvent>
#include <QTimer>
#include <memory>
#include <string>

#include "gdsoglviewer/windowmanager.h"
#include "gdsoglviewer/renderer.h"
#include <QElapsedTimer>
#include <QPainter>
#include <QPaintEvent>
#include <vector>

struct TextCmd {
    int x, y;
    std::string text;
    VECTOR4D color;
};

// We implement WindowManager to link GDS3D to Qt
class Wm_Qt : public WindowManager {
public:
    QElapsedTimer global_timer;

    Wm_Qt() {
        screenWidth = 800;
        screenHeight = 600;
        active = true;
        global_timer.start();
    }
    virtual ~Wm_Qt() {}

    void gl_finish() override {}
    bool hide_mouse() override { return false; }
    bool show_mouse() override { return false; }
    void change_cursor(int shape) override {}
    void move_mouse(int x, int y) override {}
    
    htime* new_timer() override { 
        return (htime*) new qint64(global_timer.nsecsElapsed()); 
    }
    float timer(htime *t, int reset) override { 
        if (!t) return 0.016f;
        qint64* qt = (qint64*)t;
        qint64 now = global_timer.nsecsElapsed();
        float delta = (now - *qt) / 1e9f;
        if (reset) *qt = now;
        return delta;
    }
    
    std::vector<TextCmd> texts;
    void render_text(int x, int y, const char * text, VECTOR4D color) override {
        texts.push_back({x, y, text ? text : "", color});
    }
    bool query_update(FILE *f) override { return false; }
    
    bool active;
};

class GDS3DWidget : public QOpenGLWidget, protected QOpenGLFunctions {
    Q_OBJECT
public:
    GDS3DWidget(QWidget *parent = nullptr);
    ~GDS3DWidget();

    bool load_gds(const std::string& gds_file, const std::string& tech_file, const std::string& top_cell = "");
    uintptr_t get_ptr();

protected:
    void initializeGL() override;
    void resizeGL(int w, int h) override;
    void paintGL() override;

    void mousePressEvent(QMouseEvent *event) override;
    void mouseReleaseEvent(QMouseEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;
    void keyPressEvent(QKeyEvent *event) override;
    void keyReleaseEvent(QKeyEvent *event) override;
    void wheelEvent(QWheelEvent *event) override;

private:
    std::unique_ptr<Wm_Qt> wm;
    QTimer* render_timer;
    EventKey translate_key(int qt_key);
    int translate_button(Qt::MouseButton button);
};
