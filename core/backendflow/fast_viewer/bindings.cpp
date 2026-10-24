#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include "FastLayoutViewer.h"

namespace py = pybind11;

PYBIND11_MODULE(fast_layout_viewer, m) {
    py::class_<FastLayoutViewer, std::unique_ptr<FastLayoutViewer, py::nodelete>>(m, "FastLayoutViewerCore")
        .def(py::init<>())
        .def("clear", &FastLayoutViewer::clear)
        .def("set_lod", &FastLayoutViewer::set_lod)
        .def("set_core", &FastLayoutViewer::set_core)
        .def("load_std_cells", &FastLayoutViewer::load_std_cells)
        .def("load_cells_flat", [](FastLayoutViewer& self, py::buffer b) {
            py::buffer_info info = b.request();
            if (info.format != py::format_descriptor<float>::format()) {
                throw std::runtime_error("load_cells_flat requires a float32 1D buffer");
            }
            if (info.ndim != 1 || (info.size % 4) != 0) {
                throw std::runtime_error("load_cells_flat requires a 1D float buffer whose length is a multiple of 4 (x,y,w,h)");
            }
            size_t cell_count = info.size / 4;
            const float* ptr = static_cast<const float*>(info.ptr);
            self.load_cells_flat(ptr, cell_count);
        })
        .def("load_tap_cells", &FastLayoutViewer::load_tap_cells)
        .def("load_macros", &FastLayoutViewer::load_macros)
        .def("load_pins", &FastLayoutViewer::load_pins)
        .def("load_power", &FastLayoutViewer::load_power)
        .def("load_signals", &FastLayoutViewer::load_signals)
        .def("load_regions", &FastLayoutViewer::load_regions)
        .def("load_blockages", &FastLayoutViewer::load_blockages)
        .def("set_heatmap", &FastLayoutViewer::set_heatmap)
        .def("fit_in_view", &FastLayoutViewer::fit_in_view)
        .def("pan_to", &FastLayoutViewer::pan_to, py::arg("x"), py::arg("y"), py::arg("target_zoom") = -1.0f)
        .def("highlight_box", &FastLayoutViewer::highlight_box, py::arg("x"), py::arg("y"), py::arg("w"), py::arg("h"), py::arg("name"))
        .def("clear_highlight", &FastLayoutViewer::clear_highlight)
        .def("get_ptr", [](FastLayoutViewer& self) {
            return reinterpret_cast<uintptr_t>(&self);
        });
}
