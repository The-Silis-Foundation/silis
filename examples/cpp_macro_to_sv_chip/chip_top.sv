// chip_top.sv
// Top-level ASIC chip instantiating hardened simple_alu macro
// Technology: SkyWater 130nm (sky130_fd_sc_hd)

module chip_top (
    input  logic clk_pad,
    input  logic rst_n_pad,
    input  logic a_pad,
    input  logic b_pad,
    input  logic op_pad,
    output logic res_pad,
    output logic zero_pad,
    output logic [3:0] status_leds
);

    logic reg_a, reg_b, reg_op;
    logic alu_res, alu_zero;
    logic [3:0] counter;

    always_ff @(posedge clk_pad or negedge rst_n_pad) begin
        if (!rst_n_pad) begin
            reg_a       <= 1'b0;
            reg_b       <= 1'b0;
            reg_op      <= 1'b0;
            res_pad     <= 1'b0;
            zero_pad    <= 1'b0;
            counter     <= '0;
            status_leds <= '0;
        end else begin
            reg_a       <= a_pad;
            reg_b       <= b_pad;
            reg_op      <= op_pad;
            res_pad     <= alu_res;
            zero_pad    <= alu_zero;
            counter     <= counter + 1'b1;
            status_leds <= counter;
        end
    end

    // Instantiation of hardened simple_alu Macro
    simple_alu u_alu_core (
        .clk       (clk_pad),
        .rst_n     (rst_n_pad),
        .a_in      (reg_a),
        .b_in      (reg_b),
        .op_sel    (reg_op),
        .res_out   (alu_res),
        .flag_zero (alu_zero)
    );

endmodule
