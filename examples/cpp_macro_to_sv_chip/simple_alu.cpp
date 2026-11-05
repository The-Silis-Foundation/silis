// simple_alu.cpp
// Algorithmic C++ model of an Arithmetic Logic Unit

#include <cstdint>

struct ALUOutput {
    bool res_out;
    bool flag_zero;
};

ALUOutput simple_alu(bool a_in, bool b_in, bool op_sel) {
    ALUOutput out{false, false};
    if (op_sel) {
        out.res_out = (a_in ^ b_in); // XOR
    } else {
        out.res_out = (a_in & b_in); // AND
    }
    out.flag_zero = !out.res_out;
    return out;
}
