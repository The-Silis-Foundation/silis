#pragma once
#include <string>
#include <vector>

class SynthOrchestrator {
public:
    SynthOrchestrator();
    ~SynthOrchestrator();

    std::string generate_yosys_script(const std::vector<std::string>& verilog_files, const std::string& top_module, const std::string& liberty_file);
    bool run_synthesis(const std::string& script_content, const std::string& output_json_path, const std::string& output_verilog_path);
};
