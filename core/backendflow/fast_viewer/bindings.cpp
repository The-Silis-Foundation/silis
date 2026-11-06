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
            if (info.strides.empty() || info.strides[0] != static_cast<py::ssize_t>(sizeof(float))) {
                throw std::runtime_error("load_cells_flat requires a contiguous C-style buffer (stride == sizeof(float))");
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
        .def("load_voltage_islands", &FastLayoutViewer::load_voltage_islands)
        .def("load_blockages", &FastLayoutViewer::load_blockages)
        .def("set_heatmap", [](FastLayoutViewer& self, int mode, const std::vector<float>& data, int gw = 0, int gh = 0) {
            self.set_heatmap(mode, data, gw, gh);
        }, py::arg("mode"), py::arg("data"), py::arg("grid_w") = 0, py::arg("grid_h") = 0)
        .def("set_heatmap_bounds", &FastLayoutViewer::set_heatmap_bounds, py::arg("x"), py::arg("y"), py::arg("w"), py::arg("h"))
        .def("fit_in_view", &FastLayoutViewer::fit_in_view)
        .def("pan_to", &FastLayoutViewer::pan_to, py::arg("x"), py::arg("y"), py::arg("target_zoom") = -1.0f)
        .def("highlight_box", &FastLayoutViewer::highlight_box, py::arg("x"), py::arg("y"), py::arg("w"), py::arg("h"), py::arg("name"))
        .def("clear_highlight", &FastLayoutViewer::clear_highlight)
        .def("set_ruler_active", &FastLayoutViewer::set_ruler_active, py::arg("active"))
        .def("is_ruler_active", &FastLayoutViewer::is_ruler_active)
        .def("clear_ruler", &FastLayoutViewer::clear_ruler)
        .def("get_ptr", [](FastLayoutViewer& self) {
            return reinterpret_cast<uintptr_t>(&self);
        });
}
