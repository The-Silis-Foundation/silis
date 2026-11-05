#pragma once

#include <QThread>
#include <QString>
#include <QStringList>
#include <QProcess>
#include <string>
#include <vector>

class YosysStructuralWorker : public QThread {
    Q_OBJECT
public:
    YosysStructuralWorker(const std::string& root, const std::vector<std::string>& src, const std::string& module_name, const std::string& mode, const std::string& pdk_lib);

signals:
    void log(const QString& msg, const QString& type = "INFO");
    void finished(const QString& out_path, const QString& module_name, const QString& mode);

protected:
    void run() override;

private:
    std::string root_;
    std::vector<std::string> src_;
    std::string module_name_;
    std::string mode_;
    std::string pdk_lib_;
};
