#include "YosysWorker.h"
#include <QDir>
#include <QFileInfo>
#include <QTextStream>
#include <QTemporaryFile>

YosysStructuralWorker::YosysStructuralWorker(const std::string& root, const std::vector<std::string>& src, const std::string& module_name, const std::string& mode, const std::string& pdk_lib)
    : root_(root), src_(src), module_name_(module_name), mode_(mode), pdk_lib_(pdk_lib) {
}

void YosysStructuralWorker::run() {
    QString qmodule_name = QString::fromStdString(module_name_);
    QString qroot = QString::fromStdString(root_);
    
    emit log("Extracting structural JSON for " + qmodule_name + "...");

    QString out_path = QDir(qroot).filePath("build/structural_" + qmodule_name + ".json");
    QDir().mkpath(QDir(qroot).filePath("build"));

    QTemporaryFile scriptFile;
    if (!scriptFile.open()) {
        emit log("Failed to create temporary yosys script.", "ERR");
        return;
    }

    QTextStream out(&scriptFile);
    for (const std::string& std_s : src_) {
        QString s = QString::fromStdString(std_s);
        if (s.endsWith(".sv")) {
            out << "read_verilog -sv " << s << "\n";
        } else {
            out << "read_verilog " << s << "\n";
        }
    }

    out << "hierarchy -top " << qmodule_name << "\n";

    if (mode_ == "gate" && !pdk_lib_.empty()) {
        out << "synth -top " << qmodule_name << "\n";
        out << "dfflibmap -liberty " << QString::fromStdString(pdk_lib_) << "\n";
        out << "abc -liberty " << QString::fromStdString(pdk_lib_) << "\n";
    } else {
        out << "prep -top " << qmodule_name << "\n";
    }

    out << "write_json " << out_path << "\n";
    scriptFile.flush();

    QProcess yosys;
    yosys.setProcessChannelMode(QProcess::MergedChannels);
    yosys.start("yosys", QStringList() << "-q" << scriptFile.fileName());
    yosys.waitForFinished(-1);

    if (yosys.exitCode() == 0 && QFileInfo::exists(out_path)) {
        emit log("Block Diagram Ready (" + qmodule_name + ").");
        emit finished(out_path, qmodule_name, QString::fromStdString(mode_));
    } else {
        emit log("Yosys synthesis failed.", "ERR");
    }
}
