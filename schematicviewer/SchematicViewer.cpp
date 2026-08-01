#include "SchematicViewer.h"
#include <fstream>
#include <sstream>
#include <QUrl>
#include <QDir>
#include <QByteArray>
#include <QString>

SchematicViewer::SchematicViewer(QWidget* parent) : QWebEngineView(parent) {
    connect(this, &QWebEngineView::loadFinished, this, &SchematicViewer::on_load_finished);
}

void SchematicViewer::on_load_finished(bool ok) {
    if (ok) {
        is_loaded = true;
        if (!pending_json_b64.isEmpty()) {
            QString js = QString("loadSchematic('%1');").arg(pending_json_b64);
            page()->runJavaScript(js);
            pending_json_b64.clear();
        }
    }
}

void SchematicViewer::init_url(const std::string& url) {
    load(QUrl::fromLocalFile(QString::fromStdString(url)));
}

void SchematicViewer::fit_in_view() {
    if (is_loaded) {
        page()->runJavaScript("if(typeof circuit !== 'undefined' && circuit) { circuit.center(); }");
    }
}

void SchematicViewer::clear() {
    if (is_loaded) {
        page()->runJavaScript("if(typeof circuit !== 'undefined' && circuit) { circuit.shutdown(); } $('#paper').empty();");
    }
}

void SchematicViewer::load_json(const std::string& path, const std::string& module, const std::string& mode) {
    std::ifstream file(path);
    if (!file.is_open()) return;
    std::stringstream buffer;
    buffer << file.rdbuf();
    std::string json_str = buffer.str();
    
    QByteArray ba(json_str.c_str(), json_str.length());
    QString b64 = QString::fromLatin1(ba.toBase64());
    
    if (is_loaded) {
        QString js = QString("loadSchematic('%1');").arg(b64);
        page()->runJavaScript(js);
    } else {
        pending_json_b64 = b64;
    }
}
