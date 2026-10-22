#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "SynthOrchestrator.h"
#include "TimingAnalyzer.h"

namespace py = pybind11;

PYBIND11_MODULE(synth_engine, m) {
    m.doc() = "Silis C++ Synthesis and Timing Engine";

    py::class_<TimingPathNode>(m, "TimingPathNode")
        .def_readwrite("pin_name", &TimingPathNode::pin_name)
        .def_readwrite("arrival_time", &TimingPathNode::arrival_time)
        .def_readwrite("delay", &TimingPathNode::delay);

    py::class_<TimingPath>(m, "TimingPath")
        .def_readwrite("slack", &TimingPath::slack)
        .def_readwrite("start_arrival_time", &TimingPath::start_arrival_time)
        .def_readwrite("start_pin", &TimingPath::start_pin)
        .def_readwrite("end_pin", &TimingPath::end_pin)
        .def_readwrite("nodes", &TimingPath::nodes);

    py::class_<TimingAnalyzer>(m, "TimingAnalyzer")
        .def(py::init<>())
        .def("init_and_analyze", &TimingAnalyzer::init_and_analyze,
            py::arg("liberty_file"), py::arg("verilog_file"), py::arg("top_module"))
        .def("get_worst_paths_json", &TimingAnalyzer::get_worst_paths_json,
            py::arg("count") = 10)
        .def("get_clock_tree_json", &TimingAnalyzer::get_clock_tree_json,
            py::arg("clock_name") = "clk")
        .def("get_input_ports_json", &TimingAnalyzer::get_input_ports_json);

    py::class_<SynthOrchestrator>(m, "SynthOrchestrator")
        .def(py::init<>())
        .def("generate_yosys_script", &SynthOrchestrator::generate_yosys_script, 
            py::arg("verilog_files"), py::arg("top_module"), py::arg("liberty_file"))
        .def("run_synthesis", &SynthOrchestrator::run_synthesis,
            py::arg("script_content"), py::arg("output_json_path"), py::arg("output_verilog_path"));
}
