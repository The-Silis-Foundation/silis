#include "TimingAnalyzer.h"
#include "sta/Sta.hh"
#include <tcl.h>
#include <iostream>

using namespace sta;

extern "C" {
    extern int Sta_Init(Tcl_Interp *interp);
}

namespace sta {
    extern const char *tcl_inits[];
    extern void evalTclInit(Tcl_Interp *interp, const char *inits[]);
}

TimingAnalyzer::TimingAnalyzer() {
    sta::initSta();
    sta_ = new Sta();
    Sta::setSta(sta_);
    sta_->makeComponents();
    
    Tcl_Interp *interp = Tcl_CreateInterp();
    Tcl_Init(interp);
    sta_->setTclInterp(interp);
    Sta_Init(interp);
    
    // Evaluate base tcl inits to register read_liberty, link_design, etc.
    sta::evalTclInit(interp, sta::tcl_inits);
    Tcl_Eval(interp, "init_sta_cmds");
}

TimingAnalyzer::~TimingAnalyzer() {
    delete sta_;
}

bool TimingAnalyzer::init_and_analyze(const std::string& liberty_file, const std::string& verilog_file, const std::string& top_module) {
    Tcl_Interp* interp = sta_->tclInterp();
    
    std::cout << "Loading Liberty: " << liberty_file << std::endl;
    std::string cmd1 = "read_liberty " + liberty_file;
    if (Tcl_Eval(interp, cmd1.c_str()) != TCL_OK) {
        std::cerr << "TCL Error (read_liberty): " << Tcl_GetStringResult(interp) << std::endl;
        return false;
    }
    
    std::cout << "Loading Verilog: " << verilog_file << std::endl;
    std::string cmd2 = "read_verilog " + verilog_file;
    if (Tcl_Eval(interp, cmd2.c_str()) != TCL_OK) {
        std::cerr << "TCL Error (read_verilog): " << Tcl_GetStringResult(interp) << std::endl;
        return false;
    }
    
    std::cout << "Linking Design: " << top_module << std::endl;
    std::string cmd3 = "link_design " + top_module;
    if (Tcl_Eval(interp, cmd3.c_str()) != TCL_OK) {
        std::cerr << "TCL Error (link_design): " << Tcl_GetStringResult(interp) << std::endl;
        return false;
    }
    
    // Update timing
    sta_->updateTiming(false);
    return true;
}

std::string TimingAnalyzer::get_worst_paths_json(int count) {
    Tcl_Interp* interp = sta_->tclInterp();
    
    // Debug: Let's see what OpenSTA's default report_checks says
    std::cout << "--- OPENSTA REPORT CHECKS ---" << std::endl;
    Tcl_Eval(interp, "report_checks -unconstrained -digits 4");
    std::cout << Tcl_GetStringResult(interp) << std::endl;
    std::cout << "-----------------------------" << std::endl;
    
    std::cout << "--- RAW TCL FIND_TIMING_PATHS ---" << std::endl;
    if (Tcl_Eval(interp, "find_timing_paths -unconstrained -group_path_count 1") == TCL_OK) {
        std::cout << Tcl_GetStringResult(interp) << std::endl;
    } else {
        std::cout << "ERROR: " << Tcl_GetStringResult(interp) << std::endl;
    }
    std::cout << "---------------------------------" << std::endl;
    
    std::string tcl_script = 
        "set result \"\\[\\n\"\n"
        "set first 1\n"
        "foreach path [find_timing_paths -unconstrained -group_path_count " + std::to_string(count) + "] {\n"
        "    if {!$first} { append result \",\\n\" }\n"
        "    set first 0\n"
        "    set slack [get_property $path slack]\n"
        "    set start_pin [get_property [get_property $path startpoint] full_name]\n"
        "    set end_pin [get_property [get_property $path endpoint] full_name]\n"
        "    append result \"  {\\\"slack\\\": \\\"$slack\\\", \\\"start_pin\\\": \\\"$start_pin\\\", \\\"end_pin\\\": \\\"$end_pin\\\", \\\"nodes\\\": \\[\"\n"
        "    set nfirst 1\n"
        "    foreach point [get_property $path points] {\n"
        "        if {!$nfirst} { append result \",\\n\" }\n"
        "        set nfirst 0\n"
        "        set pin [get_property [get_property $point pin] full_name]\n"
        "        set arrival [get_property $point arrival]\n"
        "        append result \"    {\\\"pin_name\\\": \\\"$pin\\\", \\\"arrival_time\\\": $arrival}\"\n"
        "    }\n"
        "    append result \"\\n  \\]}\"\n"
        "}\n"
        "append result \"\\n\\]\"\n"
        "set result\n";
        
    if (Tcl_Eval(interp, tcl_script.c_str()) == TCL_OK) {
        return Tcl_GetStringResult(interp);
    } else {
        std::cerr << "TCL ERROR (JSON): " << Tcl_GetStringResult(interp) << std::endl;
    }
    return "[]";
}

std::string TimingAnalyzer::get_clock_tree_json(const std::string& clock_name) {
    Tcl_Interp* interp = sta_->tclInterp();
    
    std::string tcl_script = 
        "proc trace_net {net depth} {\n"
        "    if {$depth > 10} { return \"\" }\n"
        "    set result \"\"\n"
        "    set first 1\n"
        "    set fanouts [get_pins -quiet -of_objects $net -filter {direction == input}]\n"
        "    foreach pin $fanouts {\n"
        "        if {!$first} { append result \",\" }\n"
        "        set first 0\n"
        "        set p_name [get_property $pin full_name]\n"
        "        set arr 0.0\n"
        "        catch {set arr [get_property $pin arrival]}\n"
        "        set cell [get_cells -of_objects $pin]\n"
        "        set is_seq 0\n"
        "        catch {\n"
        "            set lib_cell [get_property $cell lib_cell]\n"
        "            set is_seq [get_property $lib_cell is_sequential]\n"
        "        }\n"
        "        if {$is_seq} {\n"
        "            append result \"{\\\"name\\\": \\\"$p_name\\\", \\\"type\\\": \\\"sink\\\", \\\"arrival\\\": $arr, \\\"skew\\\": 0.0}\"\n"
        "        } else {\n"
        "            set out_pins [get_pins -quiet -of_objects $cell -filter {direction == output}]\n"
        "            set children_str \"\"\n"
        "            if {[llength $out_pins] > 0} {\n"
        "                set out_pin [lindex $out_pins 0]\n"
        "                set next_nets [get_nets -quiet -of_objects $out_pin]\n"
        "                if {[llength $next_nets] > 0} {\n"
        "                    set next_net [lindex $next_nets 0]\n"
        "                    set children_str [trace_net $next_net [expr $depth + 1]]\n"
        "                }\n"
        "            }\n"
        "            append result \"{\\\"name\\\": \\\"$p_name\\\", \\\"type\\\": \\\"buffer\\\", \\\"arrival\\\": $arr, \\\"children\\\": \\[$children_str\\]}\"\n"
        "        }\n"
        "    }\n"
        "    return $result\n"
        "}\n"
        "set clks [get_ports -quiet " + clock_name + "]\n"
        "if {[llength $clks] == 0} { return \"{}\" }\n"
        "set clk_port [lindex $clks 0]\n"
        "set root_nets [get_nets -quiet " + clock_name + "]\n"
        "if {[llength $root_nets] == 0} { return \\\"{}\\\" }\n"
        "set root_net [lindex $root_nets 0]\n"
        "set children [trace_net $root_net 0]\n"
        "set final \"{\\\"name\\\": \\\"" + clock_name + "\\\", \\\"type\\\": \\\"port\\\", \\\"arrival\\\": 0.0, \\\"children\\\": \\[$children\\]}\"\n"
        "set final\n";
        
    if (Tcl_Eval(interp, tcl_script.c_str()) == TCL_OK) {
        return Tcl_GetStringResult(interp);
    } else {
        std::cerr << "TCL ERROR (ClockTree JSON): " << Tcl_GetStringResult(interp) << std::endl;
    }
    return "{}";
}

std::string TimingAnalyzer::get_input_ports_json() {
    Tcl_Interp* interp = sta_->tclInterp();
    std::string tcl_script = 
        "set result \"\\[\"\n"
        "set first 1\n"
        "foreach port [get_ports -quiet -filter {direction == input}] {\n"
        "    if {!$first} { append result \",\" }\n"
        "    set first 0\n"
        "    append result \"\\\"[get_property $port name]\\\"\"\n"
        "}\n"
        "append result \"\\]\"\n"
        "set result\n";
        
    if (Tcl_Eval(interp, tcl_script.c_str()) == TCL_OK) {
        return Tcl_GetStringResult(interp);
    } else {
        std::cerr << "TCL ERROR (Ports JSON): " << Tcl_GetStringResult(interp) << std::endl;
    }
    return "[]";
}
