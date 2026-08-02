#include "MonacoViewer.h"
#include <QUrl>
#include <QCoreApplication>
#include <QEventLoop>
#include <QVariant>
#include <QFile>

MonacoViewer::MonacoViewer(QWidget* parent) : QWebEngineView(parent) {
    connect(this, &QWebEngineView::loadFinished, this, &MonacoViewer::on_load_finished);
}

void MonacoViewer::on_load_finished(bool ok) {
    if (ok) {
        is_loaded = true;
        if (!pending_theme.isEmpty()) {
            set_theme(pending_theme.toStdString());
            pending_theme.clear();
        }
        if (!pending_lang.isEmpty()) {
            set_language(pending_lang.toStdString());
            pending_lang.clear();
        }
        if (!pending_text.isEmpty()) {
            set_text(pending_text.toStdString());
            pending_text.clear();
        }
    }
}

void MonacoViewer::init_url(const std::string& url) {
    QString qurl = QString::fromStdString(url);
    if (QFile::exists(qurl)) {
        load(QUrl::fromLocalFile(qurl));
    } else {
        load(QUrl(qurl));
    }
}

void MonacoViewer::load_html(const std::string& html, const std::string& base_url) {
    is_loaded = false;
    page()->setHtml(QString::fromStdString(html), QUrl(QString::fromStdString(base_url)));
}

void MonacoViewer::set_text(const std::string& text) {
    QString qtext = QString::fromStdString(text);
    if (is_loaded) {
        QByteArray ba = qtext.toUtf8().toBase64();
        QString js = QString("setText('%1');").arg(QString(ba));
        page()->runJavaScript(js);
    } else {
        pending_text = qtext;
    }
}

std::string MonacoViewer::get_text() {
    if (!is_loaded) {
        return pending_text.toStdString();
    }
    QString result;
    bool done = false;
    page()->runJavaScript("getText();", [&](const QVariant& v) {
        result = v.toString();
        done = true;
    });
    
    // Wait for JS execution
    while (!done) {
        QCoreApplication::processEvents(QEventLoop::ExcludeUserInputEvents);
    }
    return result.toStdString();
}

void MonacoViewer::set_language(const std::string& lang) {
    QString qlang = QString::fromStdString(lang);
    if (is_loaded) {
        QString js = QString("setLanguage('%1');").arg(qlang);
        page()->runJavaScript(js);
    } else {
        pending_lang = qlang;
    }
}

void MonacoViewer::set_theme(const std::string& theme) {
    QString qtheme = QString::fromStdString(theme);
    if (is_loaded) {
        QString js = QString("setTheme('%1');").arg(qtheme);
        page()->runJavaScript(js);
    } else {
        pending_theme = qtheme;
    }
}

void MonacoViewer::run_js(const std::string& script) {
    if (is_loaded) {
        page()->runJavaScript(QString::fromStdString(script));
    }
}
