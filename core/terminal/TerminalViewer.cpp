#include "TerminalViewer.h"
#include <qtermwidget5/qtermwidget.h>
#include <QVBoxLayout>
#include <QFont>
#include <QColor>
#include <QDir>
#include <QFile>
#include <QTextStream>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

// Path to write our generated colorscheme so QTermWidget can load it by name
static const QString SILIS_SCHEME_PATH =
    QDir::tempPath() + "/silis_terminal.colorscheme";

static const QString SILIS_SCHEME_NAME = "silis_terminal";

TerminalViewer::TerminalViewer(QWidget* parent) : QWidget(parent) {
    m_layout = new QVBoxLayout(this);
    m_layout->setContentsMargins(0, 0, 0, 0);
    m_layout->setSpacing(0);

    // startnow=0 so we call start_shell() explicitly later
    m_term = new QTermWidget(0, this);
    m_term->setScrollBarPosition(QTermWidget::ScrollBarRight);
    m_term->setHistorySize(10000);
    m_term->setFlowControlEnabled(false);
    m_term->setBlinkingCursor(true);
    m_term->setKeyboardCursorShape(QTermWidget::BlockCursor);

    // Register temp dir so our custom scheme is found
    QTermWidget::addCustomColorSchemeDir(QDir::tempPath());

    connect(m_term, &QTermWidget::finished, this, &TerminalViewer::finished);
    connect(m_term, &QTermWidget::titleChanged, this, &TerminalViewer::title_changed);

    m_layout->addWidget(m_term);
}

void TerminalViewer::start_shell(const std::string& shell, const std::string& working_dir) {
    QString sh = shell.empty()
        ? qEnvironmentVariable("SHELL", "/bin/bash")
        : QString::fromStdString(shell);

    m_term->setShellProgram(sh);

    if (!working_dir.empty())
        m_term->setWorkingDirectory(QString::fromStdString(working_dir));

    m_term->startShellProgram();
}

void TerminalViewer::send_text(const std::string& text) {
    m_term->sendText(QString::fromStdString(text));
}

void TerminalViewer::set_font(const std::string& family, int size_pt) {
    QFont f(QString::fromStdString(family), size_pt);
    f.setFixedPitch(true);
    m_term->setTerminalFont(f);
}

void TerminalViewer::set_color_scheme(const std::string& scheme_name) {
    m_term->setColorScheme(QString::fromStdString(scheme_name));
}

void TerminalViewer::set_working_directory(const std::string& dir) {
    m_term->changeDir(QString::fromStdString(dir));
}

void TerminalViewer::apply_theme(const std::string& colors_json) {
    // Parse our colorconfig.json color dict and write a .colorscheme file
    // that QTermWidget can load by name from the temp dir.
    try {
        auto c = json::parse(colors_json);

        auto hex = [](const std::string& s) -> QString {
            // strip '#', return just 6-char hex
            return QString::fromStdString(s.size() > 1 ? s.substr(1) : s);
        };

        // QTermWidget .colorscheme format
        QString scheme;
        QTextStream ts(&scheme);

        // Background / foreground
        ts << "[Background]\n"
           << "Color=" << hex(c.value("bg", "#1e1e2e")) << "\n\n"
           << "[BackgroundIntense]\n"
           << "Color=" << hex(c.value("margin_bg", "#181825")) << "\n\n"
           << "[Foreground]\n"
           << "Color=" << hex(c.value("fg", "#cdd6f4")) << "\n\n"
           << "[ForegroundIntense]\n"
           << "Color=" << hex(c.value("fg", "#cdd6f4")) << "\n\n";

        // ANSI colors — map our theme slots to meaningful ANSI indices
        // 0=black 1=red 2=green 3=yellow 4=blue 5=magenta 6=cyan 7=white
        // We use: margin_bg=black, kw2=red, str=green, num=yellow,
        //         ident=blue, kw=magenta, comment=cyan, fg=white
        const std::vector<std::pair<std::string,std::string>> ansi = {
            {"Color0",  c.value("margin_bg","#181825")},
            {"Color1",  c.value("kw2","#f38ba8")},
            {"Color2",  c.value("str","#a6e3a1")},
            {"Color3",  c.value("num","#fab387")},
            {"Color4",  c.value("ident","#89b4fa")},
            {"Color5",  c.value("kw","#cba6f7")},
            {"Color6",  c.value("comment","#94e2d5")},
            {"Color7",  c.value("fg","#cdd6f4")},
        };

        for (auto& [name, color] : ansi) {
            ts << "[" << name << "]\nColor=" << hex(color) << "\n\n";
            ts << "[" << name << "Intense]\nColor=" << hex(color) << "\n\n";
        }

        // Write to temp file
        QFile f(SILIS_SCHEME_PATH);
        if (f.open(QIODevice::WriteOnly | QIODevice::Text)) {
            QTextStream out(&f);
            out << scheme;
            f.close();
            m_term->setColorScheme(SILIS_SCHEME_NAME);
        }
    } catch (...) {
        // Fallback to built-in dark scheme
        m_term->setColorScheme("Linux");
    }
}

uintptr_t TerminalViewer::get_ptr() {
    return reinterpret_cast<uintptr_t>(this);
}
