#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "SilisNative3DViewer.h"

namespace py = pybind11;

PYBIND11_MODULE(silis_gds3d_viewer, m) {
    m.doc() = "Native Qt6 OpenGL 3.3 Core Instanced 3D IC Layout Viewer";

    py::class_<SilisNative3DViewer>(m, "SilisNative3DViewer")
        .def(py::init<>())
        .def("clear", &SilisNative3DViewer::clear)
        .def("set_bounds", &SilisNative3DViewer::setBounds)
        .def("set_layer_data", &SilisNative3DViewer::setLayerData)
        .def("set_layer_visible", &SilisNative3DViewer::setLayerVisible)
        .def("set_z_scale", &SilisNative3DViewer::setZScale)
        .def("set_clip_z", &SilisNative3DViewer::setClipZ)
        .def("set_camera_preset", &SilisNative3DViewer::setCameraPreset)
        .def("fit_in_view", &SilisNative3DViewer::fitInView)
        .def("get_ptr", &SilisNative3DViewer::getPtr);
}
