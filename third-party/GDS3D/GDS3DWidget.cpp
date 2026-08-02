#include "GDS3DWidget.h"
#include <iostream>

GDS3DWidget::GDS3DWidget(QWidget *parent) : QOpenGLWidget(parent) {
    setFocusPolicy(Qt::StrongFocus);
    wm = std::make_unique<Wm_Qt>();
    ::wm = wm.get();
    
    render_timer = new QTimer(this);
    connect(render_timer, &QTimer::timeout, this, [this]() {
        update();
    });
    render_timer->start(16); // Target ~60 FPS
}

GDS3DWidget::~GDS3DWidget() {
    render_timer->stop();
    if (::wm == wm.get()) {
        ::wm = nullptr;
    }
}

bool GDS3DWidget::load_gds(const std::string& gds_file, const std::string& tech_file, const std::string& top_cell) {
    makeCurrent();
    char* gds = const_cast<char*>(gds_file.c_str());
    char* tech = const_cast<char*>(tech_file.c_str());
    char* top = top_cell.empty() ? nullptr : const_cast<char*>(top_cell.c_str());
    bool res = wm->GDSInit(tech, gds, top);
    if (res) {
        wm->init();
    }
    return res;
}

uintptr_t GDS3DWidget::get_ptr() {
    return reinterpret_cast<uintptr_t>(static_cast<QWidget*>(this));
}

void GDS3DWidget::initializeGL() {
    initializeOpenGLFunctions();
}

void GDS3DWidget::resizeGL(int w, int h) {
    wm->screenWidth = w;
    wm->screenHeight = h;
    wm->resize(w, h);
}

void GDS3DWidget::paintGL() {
    static_cast<Wm_Qt*>(wm.get())->texts.clear();
    
    // Safely draw 2D text overlay using QPainter directly onto the active FBO context!
    // We MUST wrap raw OpenGL calls in beginNativePainting/endNativePainting to prevent flickering!
    QPainter painter(this);
    painter.beginNativePainting();
    
    if (wm->getWorld()) {
        // This will issue raw OpenGL commands and also populate the texts buffer
        wm->draw();
    }
    
    painter.endNativePainting();
    QFont font = painter.font();
    font.setPixelSize(14);
    painter.setFont(font);
    
    for (const auto& cmd : static_cast<Wm_Qt*>(wm.get())->texts) {
        painter.setPen(QColor(cmd.color.GetX() * 255, cmd.color.GetY() * 255, cmd.color.GetZ() * 255, cmd.color.GetW() * 255));
        painter.drawText(cmd.x, cmd.y + 12, QString::fromStdString(cmd.text));
    }
    painter.end();
}

int GDS3DWidget::translate_button(Qt::MouseButton button) {
    if (button == Qt::LeftButton) return 1;
    if (button == Qt::MiddleButton) return 2;
    if (button == Qt::RightButton) return 3;
    return 1;
}

EventKey GDS3DWidget::translate_key(int qt_key) {
    if (qt_key >= Qt::Key_A && qt_key <= Qt::Key_Z) {
        return static_cast<EventKey>(KEY_A + (qt_key - Qt::Key_A));
    }
    if (qt_key >= Qt::Key_0 && qt_key <= Qt::Key_9) {
        return static_cast<EventKey>(KEY_0 + (qt_key - Qt::Key_0));
    }
    switch (qt_key) {
        case Qt::Key_Minus: return KEY_MINUS;
        case Qt::Key_Plus: return KEY_PLUS;
        case Qt::Key_Comma: return KEY_COMMA;
        case Qt::Key_Period: return KEY_PERIOD;
        case Qt::Key_Colon: return KEY_COLON;
        case Qt::Key_Slash: return KEY_SLASH;
        case Qt::Key_QuoteLeft: return KEY_TILDE;
        case Qt::Key_BracketLeft: return KEY_BRACKET_O;
        case Qt::Key_Backslash: return KEY_BACKSLASH;
        case Qt::Key_BracketRight: return KEY_BRACKET_C;
        case Qt::Key_QuoteDbl: return KEY_QUOTE;
        case Qt::Key_Shift: return KEY_LSHIFT;
        case Qt::Key_Control: return KEY_LCTRL;
        case Qt::Key_Alt: return KEY_LALT;
        case Qt::Key_Left: return KEY_LEFT;
        case Qt::Key_Right: return KEY_RIGHT;
        case Qt::Key_Up: return KEY_UP;
        case Qt::Key_Down: return KEY_DOWN;
        case Qt::Key_F1: return KEY_F1;
        case Qt::Key_F2: return KEY_F2;
        case Qt::Key_F3: return KEY_F3;
        case Qt::Key_F4: return KEY_F4;
        case Qt::Key_Return: return KEY_ENTER;
        case Qt::Key_Space: return KEY_SPACE;
        case Qt::Key_Tab: return KEY_TAB;
        case Qt::Key_Backspace: return KEY_BACKSPACE;
        case Qt::Key_Escape: return KEY_ESC;
        case Qt::Key_Delete: return KEY_DEL;
        default: return KEY_NONE;
    }
}

void GDS3DWidget::mousePressEvent(QMouseEvent *event) {
    wm->event(EVENT_BUTTON_DOWN, translate_button(event->button()), event->x(), event->y(),
              event->modifiers() & Qt::ShiftModifier,
              event->modifiers() & Qt::ControlModifier,
              event->modifiers() & Qt::AltModifier);
    update();
}

void GDS3DWidget::mouseReleaseEvent(QMouseEvent *event) {
    wm->event(EVENT_BUTTON_UP, translate_button(event->button()), event->x(), event->y(),
              event->modifiers() & Qt::ShiftModifier,
              event->modifiers() & Qt::ControlModifier,
              event->modifiers() & Qt::AltModifier);
    update();
}

void GDS3DWidget::mouseMoveEvent(QMouseEvent *event) {
    wm->event(EVENT_MOUSE_MOVE, 0, event->x(), event->y(),
              event->modifiers() & Qt::ShiftModifier,
              event->modifiers() & Qt::ControlModifier,
              event->modifiers() & Qt::AltModifier);
    update();
}

void GDS3DWidget::wheelEvent(QWheelEvent *event) {
    int btn = (event->angleDelta().y() > 0) ? 4 : 5;
    wm->event(EVENT_BUTTON_DOWN, btn, event->position().x(), event->position().y(),
              event->modifiers() & Qt::ShiftModifier,
              event->modifiers() & Qt::ControlModifier,
              event->modifiers() & Qt::AltModifier);
    wm->event(EVENT_BUTTON_UP, btn, event->position().x(), event->position().y(),
              event->modifiers() & Qt::ShiftModifier,
              event->modifiers() & Qt::ControlModifier,
              event->modifiers() & Qt::AltModifier);
    update();
}

void GDS3DWidget::keyPressEvent(QKeyEvent *event) {
    wm->event(EVENT_KEY_DOWN, translate_key(event->key()), 0, 0,
              event->modifiers() & Qt::ShiftModifier,
              event->modifiers() & Qt::ControlModifier,
              event->modifiers() & Qt::AltModifier);
    update();
}

void GDS3DWidget::keyReleaseEvent(QKeyEvent *event) {
    wm->event(EVENT_KEY_UP, translate_key(event->key()), 0, 0,
              event->modifiers() & Qt::ShiftModifier,
              event->modifiers() & Qt::ControlModifier,
              event->modifiers() & Qt::AltModifier);
    update();
}
