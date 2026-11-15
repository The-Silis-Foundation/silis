// Sky130 transparent latch techmap for Yosys to prevent unmapped behavioral latches
// Maps $_DLATCH_P_ to sky130_fd_sc_hd__dlxtp_1 and $_DLATCH_N_ to sky130_fd_sc_hd__dlxtn_1
module \$_DLATCH_P_ (input E, input D, output Q);
    sky130_fd_sc_hd__dlxtp_1 _TECHMAP_REPLACE_ (.GATE(E), .D(D), .Q(Q));
endmodule

module \$_DLATCH_N_ (input E, input D, output Q);
    sky130_fd_sc_hd__dlxtn_1 _TECHMAP_REPLACE_ (.GATE_N(E), .D(D), .Q(Q));
endmodule
