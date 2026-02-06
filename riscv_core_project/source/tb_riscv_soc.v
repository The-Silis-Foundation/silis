// tb_riscv_soc.v - RISC-V SoC Comprehensive Testbench
// IEEE Std 1364-2005 Verilog Compliant

module tb_riscv_soc;
    reg clk;
    reg rst;
    
    // UART
    wire uart_tx;
    reg uart_rx;
    
    // SPI
    wire spi_sck;
    wire spi_mosi;
    reg spi_miso;
    wire spi_cs;
    
    // GPIO
    reg [15:0] gpio_in;
    wire [15:0] gpio_out;
    wire [15:0] gpio_oe;
    
    // Interrupt
    wire irq;
    
    // Debug
    wire [31:0] debug_pc;
    wire [31:0] debug_instr;
    
    integer i;
    integer test_num;
    
    // Instantiate SoC
    riscv_soc dut (
        .clk(clk),
        .rst(rst),
        .uart_rx(uart_rx),
        .uart_tx(uart_tx),
        .spi_sck(spi_sck),
        .spi_mosi(spi_mosi),
        .spi_miso(spi_miso),
        .spi_cs(spi_cs),
        .gpio_in(gpio_in),
        .gpio_out(gpio_out),
        .gpio_oe(gpio_oe),
        .irq(irq),
        .debug_pc(debug_pc),
        .debug_instr(debug_instr)
    );
    
    // Clock generation (100MHz)
    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end
    
    // Main test
    initial begin
        $display("=========================================");
        $display("  RISC-V SoC Integration Test");
        $display("=========================================");
        
        // Initialize
        $dumpfile("dump.vcd");
        $dumpvars(0);
        rst = 1;
        uart_rx = 1;
        spi_miso = 0;
        gpio_in = 16'h0;
        test_num = 0;
        
        // Load test program into instruction memory
        $display("[INFO] Loading firmware...");
        
        // Test 1: Basic computation and GPIO
        // ADDI x1, x0, 0xAA -> x1 = 0xAA
        dut.instruction_ram[0] = {12'hAA, 5'd0, 3'b000, 5'd1, 7'b0010011};
        
        // LUI x2, 0x10000 -> x2 = 0x10000000 (peripheral base)
        dut.instruction_ram[1] = {20'h10000, 5'd2, 7'b0110111};
        
        // ADDI x2, x2, 0x20 -> x2 = 0x10000020 (GPIO base)
        dut.instruction_ram[2] = {12'h020, 5'd2, 3'b000, 5'd2, 7'b0010011};
        
        // SW x1, 0(x2) -> Write 0xAA to GPIO output
        dut.instruction_ram[3] = {7'd0, 5'd1, 5'd2, 3'b010, 5'd0, 7'b0100011};
        
        // Test 2: Timer setup
        // LUI x3, 0x10000 -> x3 = 0x10000000
        dut.instruction_ram[4] = {20'h10000, 5'd3, 7'b0110111};
        
        // ADDI x3, x3, 0x30 -> x3 = 0x10000030 (Timer base)
        dut.instruction_ram[5] = {12'h030, 5'd3, 3'b000, 5'd3, 7'b0010011};
        
        // ADDI x4, x0, 100 -> x4 = 100 (timer compare value)
        dut.instruction_ram[6] = {12'd100, 5'd0, 3'b000, 5'd4, 7'b0010011};
        
        // SW x4, 4(x3) -> Set timer compare
        dut.instruction_ram[7] = {7'd0, 5'd4, 5'd3, 3'b010, 5'd1, 7'b0100011};
        
        // ADDI x5, x0, 1 -> x5 = 1 (enable)
        dut.instruction_ram[8] = {12'd1, 5'd0, 3'b000, 5'd5, 7'b0010011};
        
        // SW x5, 8(x3) -> Enable timer
        dut.instruction_ram[9] = {7'd0, 5'd5, 5'd3, 3'b010, 5'd2, 7'b0100011};
        
        // Test 3: Memory operations
        // LUI x6, 0x00010 -> x6 = 0x00010000 (Data RAM base)
        dut.instruction_ram[10] = {20'h00010, 5'd6, 7'b0110111};
        
        // ADDI x7, x0, 0x12 -> x7 = 0x12
        dut.instruction_ram[11] = {12'h012, 5'd0, 3'b000, 5'd7, 7'b0010011};
        
        // ADDI x8, x0, 0x34 -> x8 = 0x34
        dut.instruction_ram[12] = {12'h034, 5'd0, 3'b000, 5'd8, 7'b0010011};
        
        // SW x7, 0(x6) -> Store 0x12 to RAM
        dut.instruction_ram[13] = {7'd0, 5'd7, 5'd6, 3'b010, 5'd0, 7'b0100011};
        
        // SW x8, 4(x6) -> Store 0x34 to RAM
        dut.instruction_ram[14] = {7'd0, 5'd8, 5'd6, 3'b010, 5'd1, 7'b0100011};
        
        // LW x9, 0(x6) -> Load from RAM
        dut.instruction_ram[15] = {12'd0, 5'd6, 3'b010, 5'd9, 7'b0000011};
        
        // LW x10, 4(x6) -> Load from RAM
        dut.instruction_ram[16] = {12'd4, 5'd6, 3'b010, 5'd10, 7'b0000011};
        
        // ADD x11, x9, x10 -> x11 = x9 + x10
        dut.instruction_ram[17] = {7'b0000000, 5'd10, 5'd9, 3'b000, 5'd11, 7'b0110011};
        
        // Test 4: Branches and loops
        // ADDI x12, x0, 0 -> x12 = 0 (loop counter)
        dut.instruction_ram[18] = {12'd0, 5'd0, 3'b000, 5'd12, 7'b0010011};
        
        // ADDI x13, x0, 5 -> x13 = 5 (loop limit)
        dut.instruction_ram[19] = {12'd5, 5'd0, 3'b000, 5'd13, 7'b0010011};
        
        // Loop: ADDI x12, x12, 1 -> Increment counter
        dut.instruction_ram[20] = {12'd1, 5'd12, 3'b000, 5'd12, 7'b0010011};
        
        // BLT x12, x13, -4 -> if x12 < x13, loop back
        dut.instruction_ram[21] = {1'b1, 6'b111111, 5'd13, 5'd12, 3'b100, 4'b1110, 1'b0, 7'b1100011};
        
        // Test 5: Arithmetic stress test
        // ADDI x14, x0, 255 -> x14 = 255
        dut.instruction_ram[22] = {12'd255, 5'd0, 3'b000, 5'd14, 7'b0010011};
        
        // ADDI x15, x0, 17 -> x15 = 17
        dut.instruction_ram[23] = {12'd17, 5'd0, 3'b000, 5'd15, 7'b0010011};
        
        // ADD x16, x14, x15 -> Overflow test
        dut.instruction_ram[24] = {7'b0000000, 5'd15, 5'd14, 3'b000, 5'd16, 7'b0110011};
        
        // SUB x17, x14, x15
        dut.instruction_ram[25] = {7'b0100000, 5'd15, 5'd14, 3'b000, 5'd17, 7'b0110011};
        
        // AND x18, x14, x15
        dut.instruction_ram[26] = {7'b0000000, 5'd15, 5'd14, 3'b111, 5'd18, 7'b0110011};
        
        // OR x19, x14, x15
        dut.instruction_ram[27] = {7'b0000000, 5'd15, 5'd14, 3'b110, 5'd19, 7'b0110011};
        
        // XOR x20, x14, x15
        dut.instruction_ram[28] = {7'b0000000, 5'd15, 5'd14, 3'b100, 5'd20, 7'b0110011};
        
        // SLL x21, x14, x15
        dut.instruction_ram[29] = {7'b0000000, 5'd15, 5'd14, 3'b001, 5'd21, 7'b0110011};
        
        // SRL x22, x14, x15
        dut.instruction_ram[30] = {7'b0000000, 5'd15, 5'd14, 3'b101, 5'd22, 7'b0110011};
        
        // Infinite loop
        dut.instruction_ram[31] = {1'b0, 6'd0, 5'd0, 5'd0, 3'b000, 4'd0, 1'b0, 7'b1100011};
        
        $display("[INFO] Firmware loaded (32 instructions)");
        
        // Release reset
        #20 rst = 0;
        $display("[INFO] System running...");
        $display("");
        
        // Run tests
        test_num = 1;
        
        // Test 1: GPIO
        $display("TEST %0d: GPIO Output", test_num);
        #500;
        if (gpio_out[7:0] == 8'hAA) begin
            $display("  PASS: GPIO output = 0x%h", gpio_out);
        end else begin
            $display("  FAIL: GPIO output = 0x%h (expected 0xAA)", gpio_out);
        end
        test_num = test_num + 1;
        
        // Test 2: Timer
        $display("TEST %0d: Timer", test_num);
        #1000;
        if (irq == 1'b1) begin
            $display("  PASS: Timer interrupt triggered");
        end else begin
            $display("  FAIL: Timer interrupt not triggered");
        end
        test_num = test_num + 1;
        
        // Test 3: Memory
        $display("TEST %0d: Memory Operations", test_num);
        #500;
        if (dut.data_ram[0] == 32'h12 && dut.data_ram[1] == 32'h34) begin
            $display("  PASS: Memory write/read successful");
        end else begin
            $display("  FAIL: Memory corruption");
        end
        test_num = test_num + 1;
        
        // Test 4: GPIO Input
        $display("TEST %0d: GPIO Input", test_num);
        gpio_in = 16'h5A5A;
        #100;
        $display("  INFO: GPIO input set to 0x%h", gpio_in);
        test_num = test_num + 1;
        
        // Run for more cycles
        $display("");
        $display("[INFO] Running extended test...");
        repeat(500) @(posedge clk);
        
        // Display register file
        $display("");
        $display("=========================================");
        $display("  Register File Snapshot");
        $display("=========================================");
        for (i = 0; i < 32; i = i + 1) begin
            if (dut.cpu.registers[i] != 32'h0) begin
                $display("  x%02d = 0x%08h (%0d)", i, dut.cpu.registers[i], dut.cpu.registers[i]);
            end
        end
        
        // Display memory snapshot
        $display("");
        $display("=========================================");
        $display("  Data Memory Snapshot");
        $display("=========================================");
        for (i = 0; i < 16; i = i + 1) begin
            if (dut.data_ram[i] != 32'h0) begin
                $display("  [0x%05h] = 0x%08h", 32'h10000 + (i*4), dut.data_ram[i]);
            end
        end
        
        // Display peripheral status
        $display("");
        $display("=========================================");
        $display("  Peripheral Status");
        $display("=========================================");
        $display("  GPIO Out:    0x%04h", gpio_out);
        $display("  GPIO OE:     0x%04h", gpio_oe);
        $display("  GPIO In:     0x%04h", gpio_in);
        $display("  Timer Count: %0d", dut.timer_counter);
        $display("  IRQ:         %b", irq);
        $display("  UART TX:     %b", uart_tx);
        $display("  SPI CS:      %b", spi_cs);
        
        #1000;
        
        $display("");
        $display("=========================================");
        $display("  Simulation Complete");
        $display("=========================================");
        $finish;
    end
    
    // Monitor PC and instructions
    always @(posedge clk) begin
        if (!rst && dut.cpu.reg_write && dut.cpu.rd_addr != 5'b0) begin
            $display("[%0t] PC=0x%h, x%0d <= 0x%h", $time, debug_pc, 
                     dut.cpu.rd_addr, dut.cpu.rd_data);
        end
    end
    
    // Timeout
    initial begin
        #50000;
        $display("[ERROR] Simulation timeout!");
        $finish;
    end

endmodule