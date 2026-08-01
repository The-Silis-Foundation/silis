#pragma once
#include <QWidget>
#include <QColor>
#include <QFont>
#include <QString>
#include <deque>
#include <vector>
#include <cstdint>

class QSocketNotifier;

// ── One terminal cell ────────────────────────────────────────────────────────
struct TermCell {
    uint32_t ch  = ' ';
    QColor   fg  = QColor(0xcd,0xd6,0xf4);   // Catppuccin Mocha fg default
    QColor   bg  = QColor(0x1e,0x1e,0x2e);   // Catppuccin Mocha bg default
    bool bold      = false;
    bool italic    = false;
    bool underline = false;
    bool reverse   = false;
    bool wide      = false;   // double-width glyph occupies two columns
};

using Row = std::vector<TermCell>;

// ── VT parser state machine states ───────────────────────────────────────────
enum class VTState { Normal, Esc, CSI, OSC, DCS };

// ── Saved cursor state ────────────────────────────────────────────────────────
struct CursorState {
    int row = 0, col = 0;
    QColor fg, bg;
    bool bold = false, italic = false, underline = false, reverse = false;
};

class TerminalWidget : public QWidget {
    Q_OBJECT
public:
    explicit TerminalWidget(QWidget* parent = nullptr);
    ~TerminalWidget() override;

    // ── Public API (exposed via pybind11) ──────────────────────────────────
    void    start_shell(const std::string& shell, const std::string& working_dir);
    void    send_text(const std::string& text);
    void    set_font(const std::string& family, int size_pt);
    void    apply_theme(const std::string& colors_json);   // colorconfig.json dict
    void    set_working_directory(const std::string& dir);
    uintptr_t get_ptr() { return reinterpret_cast<uintptr_t>(this); }

signals:
    void shellFinished();
    void titleChanged(const QString& title);

protected:
    void paintEvent(QPaintEvent*) override;
    void resizeEvent(QResizeEvent*) override;
    void keyPressEvent(QKeyEvent*) override;
    void wheelEvent(QWheelEvent*) override;
    void focusInEvent(QFocusEvent*) override;
    void focusOutEvent(QFocusEvent*) override;
    bool focusNextPrevChild(bool next) override;
    void inputMethodEvent(QInputMethodEvent*) override;
    QVariant inputMethodQuery(Qt::InputMethodQuery) const override;
    void closeEvent(QCloseEvent*) override;

private slots:
    void onPtyData();
    void blinkTick();

private:
    // ── Screen ────────────────────────────────────────────────────────────
    int rows_ = 24, cols_ = 80;
    std::vector<Row>       screen_;       // current screen
    std::vector<Row>       alt_screen_;   // alternate screen (vim, htop…)
    bool                   use_alt_ = false;
    std::deque<Row>        scrollback_;
    int                    scroll_offset_ = 0;   // 0 = bottom, >0 = scrolled back
    static constexpr int   SCROLLBACK_MAX = 10000;

    // ── Cursor ────────────────────────────────────────────────────────────
    int  cur_row_ = 0, cur_col_ = 0;
    bool cursor_visible_ = true;
    bool cursor_blink_on_ = true;
    bool app_cursor_keys_ = false;
    CursorState saved_cursor_, saved_cursor_alt_;

    // Scroll region (0-based, inclusive)
    int scroll_top_ = 0, scroll_bot_ = 0;

    // ── Current SGR attributes ────────────────────────────────────────────
    QColor cur_fg_, cur_bg_, def_fg_, def_bg_;
    bool   cur_bold_ = false, cur_italic_ = false;
    bool   cur_underline_ = false, cur_reverse_ = false;

    // ── Font ──────────────────────────────────────────────────────────────
    QFont  font_, bold_font_;
    int    cell_w_ = 8, cell_h_ = 16;
    void   updateFontMetrics();

    // ── PTY ───────────────────────────────────────────────────────────────
    int             pty_fd_    = -1;
    pid_t           child_pid_ = -1;
    QSocketNotifier* notifier_ = nullptr;
    void writePty(const QByteArray& data);
    void resizePty();

    // ── VT parser state machine ───────────────────────────────────────────
    VTState          vt_state_  = VTState::Normal;
    std::vector<int> csi_params_;
    QString          osc_buf_;
    bool             csi_private_ = false;   // '?' prefix
    void processData(const QByteArray& data);
    void processChar(uint32_t ch);
    void dispatchCSI(char finalByte);
    void dispatchOSC();
    void applyChar(uint32_t ch);

    // ── SGR helpers ───────────────────────────────────────────────────────
    void applySGR(const std::vector<int>& params);
    static QColor xterm256(int idx);
    static const QColor ANSI16[16];

    // ── Screen helpers ────────────────────────────────────────────────────
    Row&  curScreen(int r)       { return use_alt_ ? alt_screen_[r] : screen_[r]; }
    void  clearCell(TermCell& c) { c.ch=' '; c.fg=cur_fg_; c.bg=cur_bg_;
                                   c.bold=false; c.italic=false;
                                   c.underline=false; c.reverse=false; }
    void  eraseDisplay(int mode);
    void  eraseLine(int mode);
    void  insertLines(int n);
    void  deleteLines(int n);
    void  scrollUp(int n);
    void  scrollDown(int n);
    void  newline();
    void  carriageReturn();
    void  saveCursor();
    void  restoreCursor();

    // ── Blinking cursor timer ─────────────────────────────────────────────
    QTimer* blink_timer_ = nullptr;

    // ── Bracketed paste ───────────────────────────────────────────────────
    bool bracketed_paste_ = false;

    // ── Dirty tracking (avoid full repaints) ─────────────────────────────
    bool full_dirty_ = true;
};
