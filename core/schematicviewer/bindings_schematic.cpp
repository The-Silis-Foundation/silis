#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "SchematicViewer.h"
#include "YosysWorker.h"

namespace py = pybind11;

PYBIND11_MODULE(schematic_engine, m) {
    m.doc() = "Fast schematic routing engine for Silis via WebEngine";

    py::class_<YosysStructuralWorker>(m, "YosysStructuralWorkerCore")
        .def(py::init<const std::string&, const std::vector<std::string>&, const std::string&, const std::string&, const std::string&>())
        .def("get_ptr", [](YosysStructuralWorker& self) {
            return (uintptr_t)&self;
        });

    py::class_<SchematicViewer, std::unique_ptr<SchematicViewer, py::nodelete>>(m, "SchematicViewerCore")
        .def(py::init<>())
        .def("init_url", &SchematicViewer::init_url)
        .def("fit_in_view", &SchematicViewer::fit_in_view)
        .def("clear", &SchematicViewer::clear)
        .def("load_json", &SchematicViewer::load_json)
        .def("set_theme", &SchematicViewer::set_theme)
        .def("get_ptr", [](SchematicViewer& self) {
            return reinterpret_cast<uintptr_t>(&self);
        });
}
