#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "FastLayoutViewer.h"

namespace py = pybind11;

PYBIND11_MODULE(fast_layout_viewer, m) {
    // py::nodelete prevents Python's garbage collector from destroying the C++ Qt Object
    py::class_<FastLayoutViewer, std::unique_ptr<FastLayoutViewer, py::nodelete>>(m, "FastLayoutViewerCore")
        .def(py::init<>())
        .def("clear", &FastLayoutViewer::clear)
        .def("set_core", &FastLayoutViewer::set_core)
        .def("load_std_cells", &FastLayoutViewer::load_std_cells)
        .def("load_macros", &FastLayoutViewer::load_macros)
        .def("load_pins", &FastLayoutViewer::load_pins)
        .def("load_power", &FastLayoutViewer::load_power)
        .def("load_signals", &FastLayoutViewer::load_signals)
        .def("fit_in_view", &FastLayoutViewer::fit_in_view)
        .def("get_ptr", [](FastLayoutViewer& self) {
            return reinterpret_cast<uintptr_t>(&self);
        });
}
