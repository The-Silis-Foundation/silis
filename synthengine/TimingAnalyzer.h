#pragma once
#include <string>
#include <vector>

namespace sta {
    class Sta;
}

struct TimingPathNode {
    std::string pin_name;
    double arrival_time;
    double delay;
};

struct TimingPath {
    double slack;
    double start_arrival_time;
    std::string start_pin;
    std::string end_pin;
    std::vector<TimingPathNode> nodes;
};

class TimingAnalyzer {
public:
    TimingAnalyzer();
    ~TimingAnalyzer();

    bool init_and_analyze(const std::string& liberty_file, const std::string& verilog_file, const std::string& top_module);
    std::string get_worst_paths_json(int count);
    std::string get_clock_tree_json(const std::string& clock_name);
    std::string get_input_ports_json();

private:
    sta::Sta* sta_;
};
