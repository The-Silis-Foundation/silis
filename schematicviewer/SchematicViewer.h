#include <QWebEngineView>
#include <QWebEnginePage>
#include <string>

class SchematicViewer : public QWebEngineView {
    Q_OBJECT
public:
    SchematicViewer(QWidget* parent = nullptr);
    void init_url(const std::string& url);
    void load_json(const std::string& path, const std::string& module, const std::string& mode);
    void set_theme(const std::string& colors_json);
    void fit_in_view();
    void clear();
    
private:
    bool is_loaded = false;
    QString pending_json_b64;
    QString pending_theme;
    
private slots:
    void on_load_finished(bool ok);
};
