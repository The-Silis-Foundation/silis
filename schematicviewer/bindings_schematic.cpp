#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "SchematicViewer.h"

namespace py = pybind11;

#include "YosysWorker.h"

PYBIND11_MODULE(schematic_engine, m) {
    m.doc() = "Fast schematic routing engine for Silis";

    py::class_<YosysStructuralWorker>(m, "YosysStructuralWorkerCore")
        .def(py::init<const std::string&, const std::vector<std::string>&, const std::string&, const std::string&, const std::string&>())
        .def("get_ptr", [](YosysStructuralWorker& self) {
            return (uintptr_t)&self;
        });

    py::class_<SchematicViewer, std::unique_ptr<SchematicViewer, py::nodelete>>(m, "SchematicViewerCore")
        .def(py::init<>())
        .def("clear", &SchematicViewer::clear)
        .def("load_blocks", &SchematicViewer::load_blocks)
        .def("load_ports", &SchematicViewer::load_ports)
        .def("load_wires", &SchematicViewer::load_wires)
        .def("load_junctions", &SchematicViewer::load_junctions)
        .def("load_dots", &SchematicViewer::load_dots)
        .def("load_json", &SchematicViewer::load_json)
        .def("hit_test", &SchematicViewer::hit_test)
        .def("fit_in_view", &SchematicViewer::fit_in_view)
        .def("get_ptr", [](SchematicViewer& self) {
            return reinterpret_cast<uintptr_t>(&self);
        });
}
