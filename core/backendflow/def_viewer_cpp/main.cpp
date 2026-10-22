#include <iostream>
#include <QApplication>
#include <QMainWindow>
#include <QDockWidget>
#include <QTreeView>
#include <QTextEdit>
#include <QLineEdit>
#include <QVBoxLayout>
#include <QWidget>
#include "LayoutViewer.h"

// Mirrors OpenROAD's MainWindow and Docking logic
class MainWindow : public QMainWindow {
public:
    MainWindow() {
        setWindowTitle("Silis - OpenROAD C++ GUI Port");
        resize(1024, 768);

        // 1. Central Layout Viewer
        LayoutViewer* viewer = new LayoutViewer(this);
        setCentralWidget(viewer);

        // 2. Display Controls Dock (Layers)
        QDockWidget* displayDock = new QDockWidget("Display Control", this);
        QTreeView* layerTree = new QTreeView(displayDock);
        layerTree->setHeaderHidden(true);
        displayDock->setWidget(layerTree);
        addDockWidget(Qt::LeftDockWidgetArea, displayDock);

        // 3. Inspector Dock (Properties)
        QDockWidget* inspectorDock = new QDockWidget("Inspector", this);
        QTextEdit* inspectorView = new QTextEdit(inspectorDock);
        inspectorView->setReadOnly(true);
        inspectorView->setText("Select an object to inspect properties...");
        inspectorDock->setWidget(inspectorView);
        addDockWidget(Qt::RightDockWidgetArea, inspectorDock);

        // 4. Scripting Dock (TCL / Console)
        QDockWidget* scriptDock = new QDockWidget("Scripting", this);
        QWidget* scriptContainer = new QWidget(scriptDock);
        QVBoxLayout* scriptLayout = new QVBoxLayout(scriptContainer);
        scriptLayout->setContentsMargins(0, 0, 0, 0);
        
        QTextEdit* scriptOutput = new QTextEdit(scriptContainer);
        scriptOutput->setReadOnly(true);
        scriptOutput->append("Welcome to Silis C++ GUI (OpenROAD port).");
        
        QLineEdit* scriptInput = new QLineEdit(scriptContainer);
        scriptInput->setPlaceholderText("Enter command...");
        
        scriptLayout->addWidget(scriptOutput);
        scriptLayout->addWidget(scriptInput);
        scriptDock->setWidget(scriptContainer);
        addDockWidget(Qt::BottomDockWidgetArea, scriptDock);
    }
};

int main(int argc, char* argv[]) {
    QApplication app(argc, argv);
    MainWindow window;
    window.show();
    
    // Output Window ID for Python to embed
    std::cout << "WID:" << window.winId() << std::endl;
    
    return app.exec();
}
