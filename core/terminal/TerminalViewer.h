#pragma once
#include <QWidget>
#include <QString>
#include <QFont>

// Forward-declare to avoid pulling QTermWidget headers into pybind11 bindings
class QTermWidget;
class QVBoxLayout;

class TerminalViewer : public QWidget {
    Q_OBJECT
public:
    explicit TerminalViewer(QWidget* parent = nullptr);
    ~TerminalViewer() override = default;

    void start_shell(const std::string& shell, const std::string& working_dir);
    void send_text(const std::string& text);
    void set_font(const std::string& family, int size_pt);
    void set_color_scheme(const std::string& scheme_name);
    void set_working_directory(const std::string& dir);
    void apply_theme(const std::string& colors_json); // accepts colorconfig.json color dict
    uintptr_t get_ptr();

signals:
    void finished();
    void title_changed(const QString& title);

private:
    QTermWidget*  m_term   = nullptr;
    QVBoxLayout*  m_layout = nullptr;
};
