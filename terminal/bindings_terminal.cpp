#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "TerminalWidget.h"

namespace py = pybind11;

PYBIND11_MODULE(terminal_engine, m) {
    m.doc() = "Custom C++ VTE terminal engine for Silis";

    py::class_<TerminalWidget, std::unique_ptr<TerminalWidget, py::nodelete>>(m, "TerminalWidgetCore")
        .def(py::init<>())
        .def("start_shell",            &TerminalWidget::start_shell)
        .def("send_text",              &TerminalWidget::send_text)
        .def("set_font",               &TerminalWidget::set_font)
        .def("set_working_directory",  &TerminalWidget::set_working_directory)
        .def("apply_theme",            &TerminalWidget::apply_theme)
        .def("get_ptr",                &TerminalWidget::get_ptr);
}
