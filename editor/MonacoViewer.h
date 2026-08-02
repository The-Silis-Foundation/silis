#pragma once
#include <QWebEngineView>
#include <QWebEnginePage>
#include <string>

class MonacoViewer : public QWebEngineView {
    Q_OBJECT
public:
    MonacoViewer(QWidget* parent = nullptr);
    void init_url(const std::string& url);
    void load_html(const std::string& html, const std::string& base_url);
    void set_text(const std::string& text);
    std::string get_text();
    void set_language(const std::string& lang);
    void set_theme(const std::string& theme);
    void run_js(const std::string& script);

private:
    bool is_loaded = false;
    QString pending_text;
    QString pending_lang;
    QString pending_theme;

private slots:
    void on_load_finished(bool ok);
};
