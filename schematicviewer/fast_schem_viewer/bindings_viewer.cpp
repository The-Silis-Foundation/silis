#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "FastSchematicViewer.h"

namespace py = pybind11;

PYBIND11_MODULE(fast_schem_viewer, m) {
    py::class_<FastSchematicViewer, std::unique_ptr<FastSchematicViewer, py::nodelete>>(m, "FastSchematicViewerCore")
        .def(py::init<>())
        .def("clear", &FastSchematicViewer::clear)
        .def("load_blocks", &FastSchematicViewer::load_blocks)
        .def("load_ports", &FastSchematicViewer::load_ports)
        .def("load_wires", &FastSchematicViewer::load_wires)
        .def("load_junctions", &FastSchematicViewer::load_junctions)
        .def("load_dots", &FastSchematicViewer::load_dots)
        .def("hit_test", &FastSchematicViewer::hit_test)
        .def("fit_in_view", &FastSchematicViewer::fit_in_view)
        .def("get_ptr", [](FastSchematicViewer& self) {
            return reinterpret_cast<uintptr_t>(&self);
        });
}
