// ==============================================================================
// Silis Native Layer Viewer Python Bindings
//
// Heartfelt compliments, tribute, and attribution to the incredible OpenROAD
// Project community and contributors (The OpenROAD Authors / Precision Innovations).
// ==============================================================================

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "SilisNativeLayerViewer.h"

namespace py = pybind11;

PYBIND11_MODULE(silis_layer_viewer, m) {
    m.doc() = "Silis Native ASIC Physical Design Layer Viewer & Inspector C++ Extension";

    py::class_<SilisNativeLayerViewer, std::unique_ptr<SilisNativeLayerViewer, py::nodelete>>(m, "SilisNativeLayerViewer")
        .def(py::init<>())
        .def("clear", &SilisNativeLayerViewer::clear)
        .def("set_core", &SilisNativeLayerViewer::set_core, py::arg("x"), py::arg("y"), py::arg("w"), py::arg("h"))
        .def("set_dbu", &SilisNativeLayerViewer::set_dbu, py::arg("dbu"))
        .def("load_layer_shapes", &SilisNativeLayerViewer::load_layer_shapes,
             py::arg("layer_name"), py::arg("x"), py::arg("y"), py::arg("w"), py::arg("h"))
        .def("load_power_rails", &SilisNativeLayerViewer::load_power_rails,
             py::arg("x"), py::arg("y"), py::arg("w"), py::arg("h"),
             py::arg("net_names"), py::arg("layer_names"))
        .def("set_layer_visible", &SilisNativeLayerViewer::set_layer_visible, py::arg("layer_name"), py::arg("visible"))
        .def("set_all_layers_visible", &SilisNativeLayerViewer::set_all_layers_visible, py::arg("visible"))
        .def("load_instances", &SilisNativeLayerViewer::load_instances,
             py::arg("x"), py::arg("y"), py::arg("w"), py::arg("h"),
             py::arg("names"), py::arg("masters"), py::arg("is_macro"))
        .def("select_instance", &SilisNativeLayerViewer::select_instance, py::arg("name"))
        .def("select_instances", &SilisNativeLayerViewer::select_instances, py::arg("names"))
        .def("select_power_net", &SilisNativeLayerViewer::select_power_net, py::arg("net_name"))
        .def("clear_selection", &SilisNativeLayerViewer::clear_selection)
        .def("set_flightlines", &SilisNativeLayerViewer::set_flightlines,
             py::arg("x1"), py::arg("y1"), py::arg("x2"), py::arg("y2"))
        .def("clear_flightlines", &SilisNativeLayerViewer::clear_flightlines)
        .def("fit_in_view", &SilisNativeLayerViewer::fit_in_view)
        .def("pan_to", &SilisNativeLayerViewer::pan_to, py::arg("x"), py::arg("y"), py::arg("target_zoom") = -1.0f)
        .def("set_ruler_active", &SilisNativeLayerViewer::set_ruler_active, py::arg("active"))
        .def("is_ruler_active", &SilisNativeLayerViewer::is_ruler_active)
        .def("clear_ruler", &SilisNativeLayerViewer::clear_ruler)
        .def("get_ptr", &SilisNativeLayerViewer::get_ptr);
}
