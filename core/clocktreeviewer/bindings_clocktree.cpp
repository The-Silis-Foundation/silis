#include <pybind11/pybind11.h>
#include "ClockTreeViewer.h"
#include <QApplication>
#include <QPointer>
#include <QTimer>
#include <stdexcept>

namespace py = pybind11;

// Wrapper class that handles Qt thread initialization seamlessly
class ClockTreeViewerCore {
public:
    ClockTreeViewerCore() {
        if (!QApplication::instance()) {
            throw std::runtime_error(
                "ClockTreeViewerCore requires an active QApplication instance. "
                "Initialize QApplication or run within a Qt application before instantiating ClockTreeViewerCore."
            );
        }
        viewer = new ClockTreeViewer();
    }
    
    ~ClockTreeViewerCore() {
        if (viewer && !viewer->parent()) {
            delete viewer.data();
        }
    }
    
    void load_tree_data(const std::string& json_str) {
        if (!viewer) return;
        viewer->load_tree_data(json_str);
    }
    
    void clear() {
        if (!viewer) return;
        viewer->clear();
    }
    
    void show() {
        if (!viewer) return;
        viewer->show();
    }
    
    void zoom_in() {
        if (!viewer) return;
        viewer->zoom_in();
    }

    void zoom_out() {
        if (!viewer) return;
        viewer->zoom_out();
    }

    void fit_view() {
        if (!viewer) return;
        viewer->fit_view();
    }

    // Returns pointer as uintptr_t for PyQt6 sip wrapping
    uintptr_t get_ptr() {
        return reinterpret_cast<uintptr_t>(viewer.data());
    }
    
    // Qt Event loop processing from Python
    void process_events() {
        if (QApplication::instance()) {
            QApplication::instance()->processEvents();
        }
    }

private:
    QPointer<ClockTreeViewer> viewer;
};

PYBIND11_MODULE(clocktree_engine, m) {
    py::class_<ClockTreeViewerCore>(m, "ClockTreeViewerCore")
        .def(py::init<>())
        .def("load_tree_data", &ClockTreeViewerCore::load_tree_data)
        .def("clear", &ClockTreeViewerCore::clear)
        .def("show", &ClockTreeViewerCore::show)
        .def("zoom_in", &ClockTreeViewerCore::zoom_in)
        .def("zoom_out", &ClockTreeViewerCore::zoom_out)
        .def("fit_view", &ClockTreeViewerCore::fit_view)
        .def("get_ptr", &ClockTreeViewerCore::get_ptr)
        .def("process_events", &ClockTreeViewerCore::process_events);
}
