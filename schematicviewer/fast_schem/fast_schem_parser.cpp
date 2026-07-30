#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <fstream>
#include <iostream>
#include "json.hpp"

namespace py = pybind11;
using json = nlohmann::json;

py::dict parse_target_module(const std::string& filepath, const std::string& target_module) {
    std::ifstream f(filepath);
    if (!f.is_open()) {
        throw std::runtime_error("Could not open JSON file: " + filepath);
    }
    
    json j;
    f >> j;
    
    if (!j.contains("modules") || !j["modules"].contains(target_module)) {
        return py::dict();
    }
    
    // We only want to convert the target module to a Python dictionary, avoiding building Python objects for the rest of the huge file
    const json& mod = j["modules"][target_module];
    
    py::dict result;
    
    // Convert ports
    if (mod.contains("ports")) {
        py::dict ports_dict;
        for (auto it = mod["ports"].begin(); it != mod["ports"].end(); ++it) {
            py::dict port_data;
            if (it.value().contains("direction")) {
                port_data["direction"] = it.value()["direction"].get<std::string>();
            }
            if (it.value().contains("bits")) {
                py::list bits;
                for (const auto& bit : it.value()["bits"]) {
                    if (bit.is_number()) {
                        bits.append(bit.get<int>());
                    } else if (bit.is_string()) {
                        bits.append(bit.get<std::string>());
                    }
                }
                port_data["bits"] = bits;
            }
            ports_dict[it.key().c_str()] = port_data;
        }
        result["ports"] = ports_dict;
    }
    
    // Convert cells
    if (mod.contains("cells")) {
        py::dict cells_dict;
        for (auto it = mod["cells"].begin(); it != mod["cells"].end(); ++it) {
            py::dict cell_data;
            if (it.value().contains("type")) {
                cell_data["type"] = it.value()["type"].get<std::string>();
            }
            if (it.value().contains("port_directions")) {
                py::dict dirs;
                for (auto dir_it = it.value()["port_directions"].begin(); dir_it != it.value()["port_directions"].end(); ++dir_it) {
                    dirs[dir_it.key().c_str()] = dir_it.value().get<std::string>();
                }
                cell_data["port_directions"] = dirs;
            }
            if (it.value().contains("connections")) {
                py::dict conns;
                for (auto conn_it = it.value()["connections"].begin(); conn_it != it.value()["connections"].end(); ++conn_it) {
                    py::list bits;
                    for (const auto& bit : conn_it.value()) {
                        if (bit.is_number()) {
                            bits.append(bit.get<int>());
                        } else if (bit.is_string()) {
                            bits.append(bit.get<std::string>());
                        }
                    }
                    conns[conn_it.key().c_str()] = bits;
                }
                cell_data["connections"] = conns;
            }
            cells_dict[it.key().c_str()] = cell_data;
        }
        result["cells"] = cells_dict;
    }
    
    return result;
}

PYBIND11_MODULE(fast_schem_parser, m) {
    m.doc() = "Fast JSON parser for Yosys schematic extraction";
    m.def("parse_target_module", &parse_target_module, "Parses only the target module from a Yosys JSON file");
}
