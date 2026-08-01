#include "TerminalWidget.h"
#include <QPainter>
#include <QKeyEvent>
#include <QWheelEvent>
#include <QTimer>
#include <QSocketNotifier>
#include <QFontMetrics>
#include <QFontDatabase>
#include <QInputMethodEvent>
#include <QApplication>

#include <pty.h>       // forkpty
#include <unistd.h>    // write, close
#include <sys/ioctl.h> // TIOCSWINSZ
#include <signal.h>    // kill, SIGHUP
#include <fcntl.h>

#include "../schematicviewer/json.hpp"
using json = nlohmann::json;

// ── ANSI 16 colour palette ───────────────────────────────────────────────────
const QColor TerminalWidget::ANSI16[16] = {
    {0x00,0x00,0x00},{0xaa,0x00,0x00},{0x00,0xaa,0x00},{0xaa,0x55,0x00},
    {0x00,0x00,0xaa},{0xaa,0x00,0xaa},{0x00,0xaa,0xaa},{0xaa,0xaa,0xaa},
    {0x55,0x55,0x55},{0xff,0x55,0x55},{0x55,0xff,0x55},{0xff,0xff,0x55},
    {0x55,0x55,0xff},{0xff,0x55,0xff},{0x55,0xff,0xff},{0xff,0xff,0xff},
};

QColor TerminalWidget::xterm256(int n) {
    if (n < 16)  return ANSI16[n];
    if (n < 232) {
        int m = n - 16;
        int b = m % 6; m /= 6;
        int g = m % 6; m /= 6;
        int r = m;
        return QColor(r ? r*40+55 : 0, g ? g*40+55 : 0, b ? b*40+55 : 0);
    }
    int v = (n - 232) * 10 + 8;
    return QColor(v, v, v);
}

// ── Constructor ──────────────────────────────────────────────────────────────
TerminalWidget::TerminalWidget(QWidget* parent) : QWidget(parent) {
    setAttribute(Qt::WA_InputMethodEnabled);
    setFocusPolicy(Qt::StrongFocus);
    setAutoFillBackground(false);

    def_fg_ = cur_fg_ = QColor(0xcd,0xd6,0xf4);
    def_bg_ = cur_bg_ = QColor(0x1e,0x1e,0x2e);

    // Default font
    QFont f = QFontDatabase::systemFont(QFontDatabase::FixedFont);
    f.setPointSize(12);
    set_font(f.family().toStdString(), f.pointSize());

    // Allocate screen buffers
    screen_.assign(rows_, Row(cols_));
    alt_screen_.assign(rows_, Row(cols_));
    scroll_top_ = 0; scroll_bot_ = rows_ - 1;

    // Blinking cursor
    blink_timer_ = new QTimer(this);
    connect(blink_timer_, &QTimer::timeout, this, &TerminalWidget::blinkTick);
    blink_timer_->start(500);
}

TerminalWidget::~TerminalWidget() {
    if (child_pid_ > 0) { kill(child_pid_, SIGHUP); }
    if (pty_fd_ >= 0)   { ::close(pty_fd_); }
}

// ── Font ─────────────────────────────────────────────────────────────────────
void TerminalWidget::set_font(const std::string& family, int size_pt) {
    font_ = QFont(QString::fromStdString(family), size_pt);
    font_.setFixedPitch(true);
    bold_font_ = font_;
    bold_font_.setBold(true);
    updateFontMetrics();
    full_dirty_ = true;
    update();
}

void TerminalWidget::updateFontMetrics() {
    QFontMetrics fm(font_);
    cell_w_ = fm.horizontalAdvance(' ');
    cell_h_ = fm.height();
    if (cell_w_ < 1) cell_w_ = 8;
    if (cell_h_ < 1) cell_h_ = 16;
}

// ── Theme ─────────────────────────────────────────────────────────────────────
void TerminalWidget::apply_theme(const std::string& colors_json) {
    try {
        auto c = json::parse(colors_json);
        auto parse_color = [&](const std::string& key, const QColor& fallback) -> QColor {
            if (c.contains(key)) {
                std::string hex = c[key].get<std::string>();
                return QColor(QString::fromStdString(hex));
            }
            return fallback;
        };
        def_fg_ = cur_fg_ = parse_color("fg",  def_fg_);
        def_bg_ = cur_bg_ = parse_color("bg",  def_bg_);

        // Repaint everything
        for (auto& row : screen_)    for (auto& cell : row) { cell.fg=def_fg_; cell.bg=def_bg_; }
        for (auto& row : alt_screen_) for (auto& cell : row) { cell.fg=def_fg_; cell.bg=def_bg_; }
    } catch (...) {}
    full_dirty_ = true;
    update();
}

// ── Shell ─────────────────────────────────────────────────────────────────────
void TerminalWidget::start_shell(const std::string& shell, const std::string& working_dir) {
    QString sh = shell.empty()
        ? qEnvironmentVariable("SHELL", "/bin/bash")
        : QString::fromStdString(shell);

    struct winsize ws{};
    ws.ws_row = rows_; ws.ws_col = cols_;

    child_pid_ = forkpty(&pty_fd_, nullptr, nullptr, &ws);
    if (child_pid_ < 0) return;

    if (child_pid_ == 0) {
        // child
        if (!working_dir.empty()) chdir(working_dir.c_str());
        setenv("TERM", "xterm-256color", 1);
        setenv("COLORTERM", "truecolor", 1);
        execlp(sh.toLocal8Bit().constData(), sh.toLocal8Bit().constData(), nullptr);
        _exit(1);
    }

    // parent — make pty non-blocking
    fcntl(pty_fd_, F_SETFL, O_NONBLOCK);

    notifier_ = new QSocketNotifier(pty_fd_, QSocketNotifier::Read, this);
    connect(notifier_, &QSocketNotifier::activated, this, &TerminalWidget::onPtyData);
}

void TerminalWidget::set_working_directory(const std::string& dir) {
    send_text("cd " + dir + "\n");
}

void TerminalWidget::send_text(const std::string& text) {
    writePty(QByteArray::fromStdString(text));
}

void TerminalWidget::writePty(const QByteArray& data) {
    if (pty_fd_ < 0) return;
    ::write(pty_fd_, data.constData(), data.size());
}

void TerminalWidget::resizePty() {
    if (pty_fd_ < 0) return;
    struct winsize ws{};
    ws.ws_row = rows_; ws.ws_col = cols_;
    ioctl(pty_fd_, TIOCSWINSZ, &ws);
}

// ── PTY data ready ────────────────────────────────────────────────────────────
void TerminalWidget::onPtyData() {
    char buf[4096];
    ssize_t n;
    QByteArray data;
    while ((n = ::read(pty_fd_, buf, sizeof(buf))) > 0)
        data.append(buf, n);
    if (n == 0 || (n < 0 && errno != EAGAIN)) {
        notifier_->setEnabled(false);
        emit shellFinished();
        return;
    }
    if (!data.isEmpty()) {
        processData(data);
        full_dirty_ = true;
        update();
    }
}

// ── Blink ─────────────────────────────────────────────────────────────────────
void TerminalWidget::blinkTick() {
    cursor_blink_on_ = !cursor_blink_on_;
    // Only repaint cursor region
    int x = cur_col_ * cell_w_;
    int y = cur_row_ * cell_h_;
    update(x, y, cell_w_, cell_h_);
}

// ── Paint ─────────────────────────────────────────────────────────────────────
void TerminalWidget::paintEvent(QPaintEvent*) {
    QPainter p(this);
    p.setFont(font_);

    int vis_rows = height() / cell_h_;
    int vis_cols = width()  / cell_w_;

    // Build a view: scrollback + screen
    // If scrolled back, show scrollback rows first
    for (int r = 0; r < vis_rows; r++) {
        int screen_row = r - scroll_offset_;    // <0 means scrollback
        const Row* rowPtr = nullptr;
        Row empty_row(vis_cols);

        if (screen_row < 0) {
            // from scrollback
            int sb_idx = (int)scrollback_.size() + screen_row;
            if (sb_idx >= 0 && sb_idx < (int)scrollback_.size())
                rowPtr = &scrollback_[sb_idx];
            else
                rowPtr = &empty_row;
        } else if (screen_row < rows_) {
            rowPtr = &(use_alt_ ? alt_screen_[screen_row] : screen_[screen_row]);
        } else {
            rowPtr = &empty_row;
        }

        int c = 0;
        while (c < vis_cols) {
            const TermCell& cell = (c < (int)rowPtr->size()) ? (*rowPtr)[c] : empty_row[0];

            QColor fg = cell.reverse ? cell.bg : cell.fg;
            QColor bg = cell.reverse ? cell.fg : cell.bg;

            // Span consecutive cells with same bg for efficiency
            int span = 1;
            while (c + span < vis_cols && span < (int)rowPtr->size() - c) {
                const TermCell& nc = (*rowPtr)[c + span];
                QColor nbg = nc.reverse ? nc.fg : nc.bg;
                if (nbg != bg) break;
                span++;
            }

            QRect bg_rect(c * cell_w_, r * cell_h_, span * cell_w_, cell_h_);
            p.fillRect(bg_rect, bg);

            // Draw each character
            for (int i = 0; i < span; i++) {
                const TermCell& tc = (c+i < (int)rowPtr->size()) ? (*rowPtr)[c+i] : empty_row[0];
                if (tc.ch == ' ' || tc.ch == 0) { continue; }
                QFont& f = tc.bold ? bold_font_ : font_;
                if (tc.italic) { QFont fi = f; fi.setItalic(true); p.setFont(fi); }
                else p.setFont(f);
                p.setPen(tc.reverse ? tc.bg : tc.fg);
                QRect cr((c+i)*cell_w_, r*cell_h_, cell_w_, cell_h_);
                p.drawText(cr, Qt::AlignLeft | Qt::AlignVCenter, QString(QChar(tc.ch)));
                if (tc.underline) {
                    QFontMetrics fm(f);
                    int uy = r*cell_h_ + fm.ascent() + 1;
                    p.drawLine((c+i)*cell_w_, uy, (c+i+1)*cell_w_, uy);
                }
            }
            c += span;
        }
    }

    // Draw cursor (only when not scrolled back)
    if (cursor_visible_ && cursor_blink_on_ && scroll_offset_ == 0 &&
        cur_row_ < vis_rows && cur_col_ < vis_cols) {
        int cx = cur_col_ * cell_w_;
        int cy = cur_row_ * cell_h_;
        p.setPen(def_fg_);
        p.drawRect(cx, cy, cell_w_-1, cell_h_-1);
        // filled block when focused
        if (hasFocus()) {
            p.fillRect(cx, cy, cell_w_, cell_h_, def_fg_);
            const Row& row = use_alt_ ? alt_screen_[cur_row_] : screen_[cur_row_];
            if (cur_col_ < (int)row.size() && row[cur_col_].ch != ' ' && row[cur_col_].ch != 0) {
                p.setPen(def_bg_);
                p.setFont(font_);
                p.drawText(QRect(cx, cy, cell_w_, cell_h_),
                           Qt::AlignLeft | Qt::AlignVCenter,
                           QString(QChar(row[cur_col_].ch)));
            }
        }
    }
}

// ── Resize ────────────────────────────────────────────────────────────────────
void TerminalWidget::resizeEvent(QResizeEvent*) {
    int new_cols = width()  / cell_w_;
    int new_rows = height() / cell_h_;
    if (new_cols < 1) new_cols = 1;
    if (new_rows < 1) new_rows = 1;
    if (new_cols == cols_ && new_rows == rows_) return;

    cols_ = new_cols; rows_ = new_rows;
    scroll_top_ = 0; scroll_bot_ = rows_ - 1;
    cur_row_ = std::min(cur_row_, rows_-1);
    cur_col_ = std::min(cur_col_, cols_-1);

    // Resize both screens
    auto resize_screen = [&](std::vector<Row>& scr) {
        scr.resize(rows_);
        for (auto& row : scr) {
            row.resize(cols_);
            for (auto& c : row) if (c.ch == 0) { c.fg=def_fg_; c.bg=def_bg_; }
        }
    };
    resize_screen(screen_);
    resize_screen(alt_screen_);
    resizePty();
    full_dirty_ = true;
}

// ── Keyboard ──────────────────────────────────────────────────────────────────
void TerminalWidget::keyPressEvent(QKeyEvent* e) {
    // Scroll back to bottom on any keypress
    if (scroll_offset_ > 0) { scroll_offset_ = 0; full_dirty_ = true; update(); }

    QByteArray data;
    bool ctrl  = e->modifiers() & Qt::ControlModifier;
    bool shift = e->modifiers() & Qt::ShiftModifier;
    bool alt   = e->modifiers() & Qt::AltModifier;

    int key = e->key();

    if (ctrl && !shift && !alt) {
        // Ctrl + letter → send control code
        if (key >= Qt::Key_At && key <= Qt::Key_Underscore) {
            data.append(char(key - Qt::Key_At));
        } else if (key == Qt::Key_BracketLeft)  data.append('\x1b');
        else if (key == Qt::Key_Backslash)       data.append('\x1c');
        else if (key == Qt::Key_BracketRight)    data.append('\x1d');
        else if (key == Qt::Key_AsciiCircum)     data.append('\x1e');
        else if (key == Qt::Key_Underscore)      data.append('\x1f');
    } else {
        switch (key) {
            case Qt::Key_Return:    data = "\r"; break;
            case Qt::Key_Enter:     data = "\r"; break;
            case Qt::Key_Backspace: data = "\x7f"; break;
            case Qt::Key_Delete:    data = "\x1b[3~"; break;
            case Qt::Key_Escape:    data = "\x1b"; break;
            case Qt::Key_Tab:       data = shift ? "\x1b[Z" : "\t"; break;
            case Qt::Key_Home:      data = app_cursor_keys_ ? "\x1bOH" : "\x1b[H"; break;
            case Qt::Key_End:       data = app_cursor_keys_ ? "\x1bOF" : "\x1b[F"; break;
            case Qt::Key_Insert:    data = "\x1b[2~"; break;
            case Qt::Key_PageUp:    data = shift ? QByteArray() : QByteArray("\x1b[5~"); break;
            case Qt::Key_PageDown:  data = shift ? QByteArray() : QByteArray("\x1b[6~"); break;
            case Qt::Key_Up:    data = app_cursor_keys_ ? "\x1bOA" : "\x1b[A"; break;
            case Qt::Key_Down:  data = app_cursor_keys_ ? "\x1bOB" : "\x1b[B"; break;
            case Qt::Key_Right: data = app_cursor_keys_ ? "\x1bOC" : "\x1b[C"; break;
            case Qt::Key_Left:  data = app_cursor_keys_ ? "\x1bOD" : "\x1b[D"; break;
            case Qt::Key_F1:  data = "\x1bOP"; break;
            case Qt::Key_F2:  data = "\x1bOQ"; break;
            case Qt::Key_F3:  data = "\x1bOR"; break;
            case Qt::Key_F4:  data = "\x1bOS"; break;
            case Qt::Key_F5:  data = "\x1b[15~"; break;
            case Qt::Key_F6:  data = "\x1b[17~"; break;
            case Qt::Key_F7:  data = "\x1b[18~"; break;
            case Qt::Key_F8:  data = "\x1b[19~"; break;
            case Qt::Key_F9:  data = "\x1b[20~"; break;
            case Qt::Key_F10: data = "\x1b[21~"; break;
            case Qt::Key_F11: data = "\x1b[23~"; break;
            case Qt::Key_F12: data = "\x1b[24~"; break;
            default: {
                if (!e->text().isEmpty()) {
                    data = e->text().toUtf8();
                    if (alt && data.size() == 1) data.prepend('\x1b');
                }
            }
        }
    }
    if (!data.isEmpty()) writePty(data);
}

void TerminalWidget::wheelEvent(QWheelEvent* e) {
    int delta = e->angleDelta().y();
    if (delta > 0) scroll_offset_ = std::min(scroll_offset_+3, (int)scrollback_.size());
    else           scroll_offset_ = std::max(scroll_offset_-3, 0);
    full_dirty_ = true;
    update();
}

void TerminalWidget::focusInEvent(QFocusEvent*)  { update(); }
void TerminalWidget::focusOutEvent(QFocusEvent*) { update(); }
bool TerminalWidget::focusNextPrevChild(bool) { return false; }

void TerminalWidget::inputMethodEvent(QInputMethodEvent* e) {
    if (!e->commitString().isEmpty())
        writePty(e->commitString().toUtf8());
}

QVariant TerminalWidget::inputMethodQuery(Qt::InputMethodQuery q) const {
    if (q == Qt::ImEnabled) return true;
    return QWidget::inputMethodQuery(q);
}

void TerminalWidget::closeEvent(QCloseEvent*) {
    if (child_pid_ > 0) kill(child_pid_, SIGHUP);
}

// ── VT parser ─────────────────────────────────────────────────────────────────
void TerminalWidget::processData(const QByteArray& data) {
    for (unsigned char byte : data) {
        uint32_t ch = byte;
        switch (vt_state_) {
        case VTState::Normal:
            if (ch == 0x1b) { vt_state_ = VTState::Esc; }
            else if (ch == '\r')   { carriageReturn(); }
            else if (ch == '\n' || ch == '\x0b' || ch == '\x0c') { newline(); }
            else if (ch == '\b')   { cur_col_ = std::max(0, cur_col_-1); }
            else if (ch == '\t')   { cur_col_ = std::min(cols_-1, (cur_col_/8+1)*8); }
            else if (ch == '\x07') { /* bell – ignore */ }
            else if (ch == '\x0e' || ch == '\x0f') { /* charset shift – ignore */ }
            else if (ch >= 0x20 || ch == 0) { applyChar(ch); }
            break;

        case VTState::Esc:
            switch (ch) {
            case '[': vt_state_=VTState::CSI; csi_params_.clear(); csi_private_=false; osc_buf_.clear(); break;
            case ']': vt_state_=VTState::OSC; osc_buf_.clear(); break;
            case 'P': vt_state_=VTState::DCS; osc_buf_.clear(); break;
            case '7': saveCursor();    vt_state_=VTState::Normal; break;
            case '8': restoreCursor(); vt_state_=VTState::Normal; break;
            case 'M': // reverse index
                if (cur_row_ == scroll_top_) scrollDown(1);
                else cur_row_ = std::max(0, cur_row_-1);
                vt_state_=VTState::Normal; break;
            case 'D': // index (like newline)
                newline(); vt_state_=VTState::Normal; break;
            case 'E': // next line
                carriageReturn(); newline(); vt_state_=VTState::Normal; break;
            case '=': case '>': // keypad mode – ignore
                vt_state_=VTState::Normal; break;
            case 'c': // full reset
                cur_row_=0; cur_col_=0; cur_fg_=def_fg_; cur_bg_=def_bg_;
                cur_bold_=false; cur_italic_=false; cur_underline_=false;
                screen_.assign(rows_, Row(cols_));
                vt_state_=VTState::Normal; break;
            default:  vt_state_=VTState::Normal; break;
            }
            break;

        case VTState::CSI:
            if (ch == '?') { csi_private_=true; }
            else if (ch >= '0' && ch <= '9') {
                if (csi_params_.empty()) csi_params_.push_back(0);
                csi_params_.back() = csi_params_.back()*10 + (ch-'0');
            } else if (ch == ';') {
                csi_params_.push_back(0);
            } else if (ch >= 0x40 && ch <= 0x7e) {
                dispatchCSI(char(ch));
                vt_state_=VTState::Normal;
                csi_private_=false;
            }
            break;

        case VTState::OSC:
            if (ch == '\x07' || (ch == '\\' && !osc_buf_.isEmpty() && osc_buf_.back()=='\x1b')) {
                if (ch == '\\') osc_buf_.chop(1);
                dispatchOSC();
                vt_state_=VTState::Normal;
            } else {
                osc_buf_.append(QChar(ch));
            }
            break;

        case VTState::DCS:
            // DCS sequences – consume until ST
            if (ch == '\x07' || (ch == '\\' && !osc_buf_.isEmpty() && osc_buf_.back()=='\x1b'))
                vt_state_=VTState::Normal;
            else osc_buf_.append(QChar(ch));
            break;
        }
    }
}

void TerminalWidget::applyChar(uint32_t ch) {
    if (cur_col_ >= cols_) { carriageReturn(); newline(); }
    auto& cell = curScreen(cur_row_)[cur_col_];
    cell.ch        = ch;
    cell.fg        = cur_fg_;
    cell.bg        = cur_bg_;
    cell.bold      = cur_bold_;
    cell.italic    = cur_italic_;
    cell.underline = cur_underline_;
    cell.reverse   = cur_reverse_;
    cur_col_++;
}

void TerminalWidget::newline() {
    if (cur_row_ == scroll_bot_) scrollUp(1);
    else cur_row_ = std::min(rows_-1, cur_row_+1);
}

void TerminalWidget::carriageReturn() { cur_col_ = 0; }

void TerminalWidget::scrollUp(int n) {
    auto& scr = use_alt_ ? alt_screen_ : screen_;
    for (int i = 0; i < n; i++) {
        if (!use_alt_) {
            scrollback_.push_back(scr[scroll_top_]);
            if ((int)scrollback_.size() > SCROLLBACK_MAX) scrollback_.pop_front();
        }
        scr.erase(scr.begin() + scroll_top_);
        Row blank(cols_);
        for (auto& c : blank) { c.fg=cur_fg_; c.bg=cur_bg_; }
        scr.insert(scr.begin() + scroll_bot_, blank);
    }
}

void TerminalWidget::scrollDown(int n) {
    auto& scr = use_alt_ ? alt_screen_ : screen_;
    for (int i = 0; i < n; i++) {
        scr.erase(scr.begin() + scroll_bot_);
        Row blank(cols_);
        for (auto& c : blank) { c.fg=cur_fg_; c.bg=cur_bg_; }
        scr.insert(scr.begin() + scroll_top_, blank);
    }
}

void TerminalWidget::insertLines(int n) {
    auto& scr = use_alt_ ? alt_screen_ : screen_;
    for (int i = 0; i < n && cur_row_ <= scroll_bot_; i++) {
        scr.erase(scr.begin() + scroll_bot_);
        Row blank(cols_);
        for (auto& c : blank) { c.fg=cur_fg_; c.bg=cur_bg_; }
        scr.insert(scr.begin() + cur_row_, blank);
    }
}

void TerminalWidget::deleteLines(int n) {
    auto& scr = use_alt_ ? alt_screen_ : screen_;
    for (int i = 0; i < n && cur_row_ <= scroll_bot_; i++) {
        scr.erase(scr.begin() + cur_row_);
        Row blank(cols_);
        for (auto& c : blank) { c.fg=cur_fg_; c.bg=cur_bg_; }
        scr.insert(scr.begin() + scroll_bot_, blank);
    }
}

void TerminalWidget::eraseDisplay(int mode) {
    auto& scr = use_alt_ ? alt_screen_ : screen_;
    auto blank_row = [&]() { Row r(cols_); for(auto&c:r){c.fg=cur_fg_;c.bg=cur_bg_;} return r; };
    if (mode == 0) { // below
        for (int c = cur_col_; c < cols_; c++) clearCell(curScreen(cur_row_)[c]);
        for (int r = cur_row_+1; r < rows_; r++) scr[r] = blank_row();
    } else if (mode == 1) { // above
        for (int r = 0; r < cur_row_; r++) scr[r] = blank_row();
        for (int c = 0; c <= cur_col_; c++) clearCell(curScreen(cur_row_)[c]);
    } else if (mode == 2 || mode == 3) { // all
        for (int r = 0; r < rows_; r++) scr[r] = blank_row();
        if (mode == 3) { scrollback_.clear(); scroll_offset_=0; }
    }
}

void TerminalWidget::eraseLine(int mode) {
    if (mode == 0) for (int c=cur_col_; c<cols_; c++) clearCell(curScreen(cur_row_)[c]);
    else if (mode == 1) for (int c=0; c<=cur_col_; c++) clearCell(curScreen(cur_row_)[c]);
    else if (mode == 2) for (int c=0; c<cols_;    c++) clearCell(curScreen(cur_row_)[c]);
}

void TerminalWidget::saveCursor() {
    auto& s = use_alt_ ? saved_cursor_alt_ : saved_cursor_;
    s = {cur_row_, cur_col_, cur_fg_, cur_bg_, cur_bold_, cur_italic_, cur_underline_, cur_reverse_};
}

void TerminalWidget::restoreCursor() {
    auto& s = use_alt_ ? saved_cursor_alt_ : saved_cursor_;
    cur_row_=s.row; cur_col_=s.col; cur_fg_=s.fg; cur_bg_=s.bg;
    cur_bold_=s.bold; cur_italic_=s.italic; cur_underline_=s.underline; cur_reverse_=s.reverse;
}

// ── CSI dispatch ──────────────────────────────────────────────────────────────
void TerminalWidget::dispatchCSI(char f) {
    auto P = [&](int i, int def=0) -> int {
        return (i < (int)csi_params_.size() && csi_params_[i] != 0)
               ? csi_params_[i] : def;
    };
    auto P0 = [&](int i) -> int {
        return (i < (int)csi_params_.size()) ? csi_params_[i] : 0;
    };

    switch (f) {
    case 'A': cur_row_ = std::max(scroll_top_, cur_row_ - P(0,1)); break;
    case 'B': cur_row_ = std::min(scroll_bot_, cur_row_ + P(0,1)); break;
    case 'C': cur_col_ = std::min(cols_-1,     cur_col_ + P(0,1)); break;
    case 'D': cur_col_ = std::max(0,            cur_col_ - P(0,1)); break;
    case 'E': cur_col_=0; cur_row_=std::min(rows_-1, cur_row_+P(0,1)); break;
    case 'F': cur_col_=0; cur_row_=std::max(0,        cur_row_-P(0,1)); break;
    case 'G': cur_col_ = std::min(cols_-1, std::max(0, P(0,1)-1)); break;
    case 'H': case 'f':
        cur_row_ = std::min(rows_-1, std::max(0, P(0,1)-1));
        cur_col_ = std::min(cols_-1, std::max(0, P(1,1)-1));
        break;
    case 'J': eraseDisplay(P0(0)); break;
    case 'K': eraseLine(P0(0)); break;
    case 'L': insertLines(P(0,1)); break;
    case 'M': deleteLines(P(0,1)); break;
    case 'P': { // delete chars
        auto& row = curScreen(cur_row_);
        int n = std::min(P(0,1), cols_-cur_col_);
        row.erase(row.begin()+cur_col_, row.begin()+cur_col_+n);
        TermCell blank; blank.fg=cur_fg_; blank.bg=cur_bg_;
        row.insert(row.end(), n, blank);
    } break;
    case '@': { // insert chars
        auto& row = curScreen(cur_row_);
        int n = std::min(P(0,1), cols_-cur_col_);
        TermCell blank; blank.fg=cur_fg_; blank.bg=cur_bg_;
        row.insert(row.begin()+cur_col_, n, blank);
        row.resize(cols_, blank);
    } break;
    case 'S': scrollUp(P(0,1)); break;
    case 'T': scrollDown(P(0,1)); break;
    case 'd': cur_row_ = std::min(rows_-1, std::max(0, P(0,1)-1)); break;
    case 'r': // set scroll region
        scroll_top_ = std::max(0,      P(0,1)-1);
        scroll_bot_ = std::min(rows_-1, P(1,rows_)-1);
        cur_row_=0; cur_col_=0;
        break;
    case 's': saveCursor();    break;
    case 'u': restoreCursor(); break;
    case 'm': applySGR(csi_params_); break;
    case 'h':
        if (csi_private_) {
            for (int p : (csi_params_.empty()?std::vector<int>{0}:csi_params_)) {
                if (p==1)    app_cursor_keys_=true;
                if (p==25)   cursor_visible_=true;
                if (p==2004) bracketed_paste_=true;
                if (p==1049) {
                    saveCursor();
                    use_alt_=true;
                    for (auto& r:alt_screen_) for(auto& c:r){c.ch=' ';c.fg=def_fg_;c.bg=def_bg_;}
                }
            }
        }
        break;
    case 'l':
        if (csi_private_) {
            for (int p : (csi_params_.empty()?std::vector<int>{0}:csi_params_)) {
                if (p==1)    app_cursor_keys_=false;
                if (p==25)   cursor_visible_=false;
                if (p==2004) bracketed_paste_=false;
                if (p==1049) { use_alt_=false; restoreCursor(); }
            }
        }
        break;
    case 'n': // DSR
        if (P0(0)==6) {
            QByteArray r = QString("\x1b[%1;%2R").arg(cur_row_+1).arg(cur_col_+1).toUtf8();
            writePty(r);
        }
        break;
    default: break;
    }
}

// ── SGR ───────────────────────────────────────────────────────────────────────
void TerminalWidget::applySGR(const std::vector<int>& p) {
    if (p.empty()) { // reset
        cur_fg_=def_fg_; cur_bg_=def_bg_;
        cur_bold_=false; cur_italic_=false; cur_underline_=false; cur_reverse_=false;
        return;
    }
    for (int i=0; i<(int)p.size(); i++) {
        int v = p[i];
        switch(v) {
        case 0:  cur_fg_=def_fg_; cur_bg_=def_bg_;
                 cur_bold_=false; cur_italic_=false; cur_underline_=false; cur_reverse_=false; break;
        case 1:  cur_bold_=true;      break;
        case 3:  cur_italic_=true;    break;
        case 4:  cur_underline_=true; break;
        case 7:  cur_reverse_=true;   break;
        case 22: cur_bold_=false;      break;
        case 23: cur_italic_=false;    break;
        case 24: cur_underline_=false; break;
        case 27: cur_reverse_=false;   break;
        case 39: cur_fg_=def_fg_; break;
        case 49: cur_bg_=def_bg_; break;
        default:
            if (v>=30 && v<=37) { cur_fg_=ANSI16[v-30]; }
            else if (v>=90 && v<=97) { cur_fg_=ANSI16[v-90+8]; }
            else if (v>=40 && v<=47) { cur_bg_=ANSI16[v-40]; }
            else if (v>=100 && v<=107) { cur_bg_=ANSI16[v-100+8]; }
            else if (v==38 && i+2<(int)p.size() && p[i+1]==5) {
                cur_fg_=xterm256(p[i+2]); i+=2;
            } else if (v==38 && i+4<(int)p.size() && p[i+1]==2) {
                cur_fg_=QColor(p[i+2],p[i+3],p[i+4]); i+=4;
            } else if (v==48 && i+2<(int)p.size() && p[i+1]==5) {
                cur_bg_=xterm256(p[i+2]); i+=2;
            } else if (v==48 && i+4<(int)p.size() && p[i+1]==2) {
                cur_bg_=QColor(p[i+2],p[i+3],p[i+4]); i+=4;
            }
        }
    }
}

// ── OSC dispatch ──────────────────────────────────────────────────────────────
void TerminalWidget::dispatchOSC() {
    // OSC 0 or 2: set window title
    if (osc_buf_.startsWith("0;") || osc_buf_.startsWith("2;"))
        emit titleChanged(osc_buf_.section(';', 1));
}
