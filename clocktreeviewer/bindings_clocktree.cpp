#include <pybind11/pybind11.h>
#include "ClockTreeViewer.h"
#include <QApplication>
#include <QTimer>

namespace py = pybind11;

// Wrapper class that handles Qt thread initialization seamlessly
class ClockTreeViewerCore {
public:
    ClockTreeViewerCore() {
        if (!QApplication::instance()) {
            int argc = 0;
            char** argv = nullptr;
            app = new QApplication(argc, argv);
            owns_app = true;
        }
        viewer = new ClockTreeViewer();
    }
    
    ~ClockTreeViewerCore() {
        delete viewer;
        if (owns_app && app) {
            delete app;
            app = nullptr;
        }
    }
    
    void load_tree_data(const std::string& json_str) {
        viewer->load_tree_data(json_str);
    }
    
    void clear() {
        viewer->clear();
    }
    
    void show() {
        viewer->show();
    }
    
    // Returns pointer as uintptr_t for PyQt6 sip wrapping
    uintptr_t get_ptr() {
        return reinterpret_cast<uintptr_t>(viewer);
    }
    
    // Qt Event loop processing from Python
    void process_events() {
        if (QApplication::instance()) {
            QApplication::instance()->processEvents();
        }
    }

private:
    ClockTreeViewer* viewer;
    QApplication* app = nullptr;
    bool owns_app = false;
};

PYBIND11_MODULE(clocktree_engine, m) {
    py::class_<ClockTreeViewerCore>(m, "ClockTreeViewerCore")
        .def(py::init<>())
        .def("load_tree_data", &ClockTreeViewerCore::load_tree_data)
        .def("clear", &ClockTreeViewerCore::clear)
        .def("show", &ClockTreeViewerCore::show)
        .def("get_ptr", &ClockTreeViewerCore::get_ptr)
        .def("process_events", &ClockTreeViewerCore::process_events);
}
