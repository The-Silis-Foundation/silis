#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "MonacoViewer.h"

namespace py = pybind11;

PYBIND11_MODULE(editor_engine, m) {
    m.doc() = "Monaco Editor engine via WebEngine for Silis";

    py::class_<MonacoViewer, std::unique_ptr<MonacoViewer, py::nodelete>>(m, "MonacoViewerCore")
        .def(py::init<>())
        .def("init_url", &MonacoViewer::init_url)
        .def("load_html", &MonacoViewer::load_html)
        .def("set_text", &MonacoViewer::set_text)
        .def("get_text", &MonacoViewer::get_text)
        .def("set_language", &MonacoViewer::set_language)
        .def("set_theme", &MonacoViewer::set_theme)
        .def("get_ptr", [](MonacoViewer& self) {
            return reinterpret_cast<uintptr_t>(&self);
        });
}
