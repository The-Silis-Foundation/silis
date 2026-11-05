#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "GDS3DWidget.h"

namespace py = pybind11;

PYBIND11_MODULE(gds3d_engine, m) {
    m.doc() = "GDS3D Viewer Engine via QOpenGLWidget for Silis";

    py::class_<GDS3DWidget, std::unique_ptr<GDS3DWidget, py::nodelete>>(m, "GDS3DViewerCore")
        .def(py::init<>())
        .def("load_gds", &GDS3DWidget::load_gds)
        .def("get_ptr", &GDS3DWidget::get_ptr);
}
