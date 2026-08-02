#include "SynthOrchestrator.h"
#include <fstream>
#include <sstream>
#include <cstdlib>
#include <iostream>

SynthOrchestrator::SynthOrchestrator() {}
SynthOrchestrator::~SynthOrchestrator() {}

std::string SynthOrchestrator::generate_yosys_script(const std::vector<std::string>& verilog_files, const std::string& top_module, const std::string& liberty_file) {
    std::stringstream ss;
    
    // Read modules
    for(const auto& v : verilog_files) {
        ss << "read_verilog " << v << "\n";
    }
    
    // Elaboration
    ss << "hierarchy -check -top " << top_module << "\n";
    
    // High-level synthesis
    ss << "proc; opt; fsm; opt; memory; opt\n";
    
    // Tech mapping
    ss << "techmap; opt\n";
    
    // ABC mapping to Liberty
    ss << "dfflibmap -liberty " << liberty_file << "\n";
    ss << "abc -liberty " << liberty_file << "\n";
    ss << "flatten\n";
    ss << "opt_clean -purge\n";
    
    return ss.str();
}

bool SynthOrchestrator::run_synthesis(const std::string& script_content, const std::string& output_json_path, const std::string& output_verilog_path) {
    // Write script to temp file
    std::string script_path = "/tmp/silis_synth.ys";
    std::ofstream script_file(script_path);
    script_file << script_content;
    script_file << "write_json " << output_json_path << "\n";
    script_file << "write_verilog -noattr -noexpr " << output_verilog_path << "\n";
    script_file.close();
    
    // Execute yosys
    std::string cmd = "yosys -s " + script_path;
    int ret = std::system(cmd.c_str());
    
    return (ret == 0);
}
