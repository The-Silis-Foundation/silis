// riscv_soc.v - Complete RISC-V System-on-Chip
// IEEE Std 1364-2005 Verilog Compliant
// Includes: CPU + Cache + UART + SPI + GPIO + Timer + Interrupt Controller

module riscv_soc(
    input clk,
    input rst,

// --- POWER PORTS ---
    inout wire vdd,      // Core Voltage (1.2V)
    inout wire vcc,      // IO Voltage (3.3V)
    inout wire vss,      // Ground
    
    // UART Interface
    input uart_rx,
    output uart_tx,
    
    // SPI Interface
    output spi_sck,
    output spi_mosi,
    input spi_miso,
    output spi_cs,
    
    // GPIO
    input [15:0] gpio_in,
    output [15:0] gpio_out,
    output [15:0] gpio_oe,
    
    // Interrupt
    output irq,
    
    // Debug
    output [31:0] debug_pc,
    output [31:0] debug_instr
);
    wire power_good;
    assign power_good = (vdd === 1'b1 && vcc === 1'b1 && vss === 1'b0);

    // System Reset
    wire sys_rst;
    assign sys_rst = rst || !power_good;
    // ========== Memory Map ==========
    // 0x00000000 - 0x00001FFF : Instruction RAM (8KB)
    // 0x00010000 - 0x00011FFF : Data RAM (8KB)
    // 0x10000000 - 0x1000000F : UART
    // 0x10000010 - 0x1000001F : SPI
    // 0x10000020 - 0x1000002F : GPIO
    // 0x10000030 - 0x1000003F : Timer
    // 0x10000040 - 0x1000004F : Interrupt Controller

    // ========== Internal Buses ==========
    wire [31:0] cpu_imem_addr;
    wire [31:0] cpu_imem_rdata;
    wire cpu_imem_valid;
    
    wire [31:0] cpu_dmem_addr;
    wire [31:0] cpu_dmem_wdata;
    wire [31:0] cpu_dmem_rdata;
    wire [3:0] cpu_dmem_we;
    wire cpu_dmem_valid;
    
    wire [31:0] cpu_pc;
    wire [4:0] cpu_rd_addr;
    wire [31:0] cpu_rd_data;
    wire cpu_reg_write;
    
    // ========== Memory Signals ==========
    reg [31:0] imem_rdata;
    reg [31:0] dmem_rdata;
    reg [31:0] peripheral_rdata;
    
    // Chip Select signals
    wire cs_imem, cs_dmem, cs_uart, cs_spi, cs_gpio, cs_timer, cs_intc;
    
    assign cs_imem = (cpu_imem_addr[31:13] == 19'b0);
    assign cs_dmem = (cpu_dmem_addr[31:13] == 19'b0000000000000000001);
    assign cs_uart = (cpu_dmem_addr[31:4] == 28'h1000000);
    assign cs_spi  = (cpu_dmem_addr[31:4] == 28'h1000001);
    assign cs_gpio = (cpu_dmem_addr[31:4] == 28'h1000002);
    assign cs_timer = (cpu_dmem_addr[31:4] == 28'h1000003);
    assign cs_intc = (cpu_dmem_addr[31:4] == 28'h1000004);
    
    // ========== Instruction Memory (8KB) ==========
    reg [31:0] instruction_ram [0:2047];
    integer i;
    
    initial begin
        for (i = 0; i < 2048; i = i + 1) begin
            instruction_ram[i] = 32'h00000013; // NOP
        end
    end
    
    always @(posedge clk) begin
        if (cs_imem) begin
            imem_rdata <= instruction_ram[cpu_imem_addr[12:2]];
        end
    end
    
    assign cpu_imem_rdata = imem_rdata;
    
    // ========== Data Memory (8KB) ==========
    reg [31:0] data_ram [0:2047];
    
    initial begin
        for (i = 0; i < 2048; i = i + 1) begin
            data_ram[i] = 32'h00000000;
        end
    end
    
    always @(posedge clk) begin
        if (cs_dmem) begin
            if (cpu_dmem_we[0]) data_ram[cpu_dmem_addr[12:2]][7:0] <= cpu_dmem_wdata[7:0];
            if (cpu_dmem_we[1]) data_ram[cpu_dmem_addr[12:2]][15:8] <= cpu_dmem_wdata[15:8];
            if (cpu_dmem_we[2]) data_ram[cpu_dmem_addr[12:2]][23:16] <= cpu_dmem_wdata[23:16];
            if (cpu_dmem_we[3]) data_ram[cpu_dmem_addr[12:2]][31:24] <= cpu_dmem_wdata[31:24];
            dmem_rdata <= data_ram[cpu_dmem_addr[12:2]];
        end
    end
    
    // ========== UART Module ==========
    wire [31:0] uart_rdata;
    wire uart_tx_ready, uart_rx_valid;
    reg [7:0] uart_tx_data;
    reg uart_tx_start;
    wire [7:0] uart_rx_data;
    
    uart_controller uart_inst (
        .clk(clk),
        .rst(rst),
        .tx(uart_tx),
        .rx(uart_rx),
        .tx_data(uart_tx_data),
        .tx_start(uart_tx_start),
        .tx_ready(uart_tx_ready),
        .rx_data(uart_rx_data),
        .rx_valid(uart_rx_valid)
    );
    
    assign uart_rdata = {22'b0, uart_rx_valid, uart_tx_ready, uart_rx_data};
    
    always @(posedge clk) begin
        uart_tx_start <= 1'b0;
        if (cs_uart && cpu_dmem_we != 4'b0) begin
            uart_tx_data <= cpu_dmem_wdata[7:0];
            uart_tx_start <= 1'b1;
        end
    end
    
    // ========== SPI Module ==========
    wire [31:0] spi_rdata;
    reg [7:0] spi_tx_data;
    reg spi_start;
    wire [7:0] spi_rx_data;
    wire spi_busy;
    
    spi_master spi_inst (
        .clk(clk),
        .rst(rst),
        .sck(spi_sck),
        .mosi(spi_mosi),
        .miso(spi_miso),
        .cs(spi_cs),
        .tx_data(spi_tx_data),
        .start(spi_start),
        .rx_data(spi_rx_data),
        .busy(spi_busy)
    );
    
    assign spi_rdata = {23'b0, spi_busy, spi_rx_data};
    
    always @(posedge clk) begin
        spi_start <= 1'b0;
        if (cs_spi && cpu_dmem_we != 4'b0) begin
            spi_tx_data <= cpu_dmem_wdata[7:0];
            spi_start <= 1'b1;
        end
    end
    
    // ========== GPIO Module ==========
    reg [15:0] gpio_output;
    reg [15:0] gpio_output_enable;
    wire [31:0] gpio_rdata;
    
    assign gpio_out = gpio_output;
    assign gpio_oe = gpio_output_enable;
    assign gpio_rdata = {gpio_in, gpio_output};
    
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            gpio_output <= 16'h0;
            gpio_output_enable <= 16'h0;
        end else if (cs_gpio && cpu_dmem_we != 4'b0) begin
            case (cpu_dmem_addr[3:2])
                2'b00: gpio_output <= cpu_dmem_wdata[15:0];
                2'b01: gpio_output_enable <= cpu_dmem_wdata[15:0];
            endcase
        end
    end
    
    // ========== Timer Module ==========
    reg [31:0] timer_counter;
    reg [31:0] timer_compare;
    reg timer_enable;
    wire timer_irq;
    wire [31:0] timer_rdata;
    
    assign timer_irq = (timer_counter >= timer_compare) && timer_enable;
    assign timer_rdata = timer_counter;
    
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            timer_counter <= 32'h0;
            timer_compare <= 32'hFFFFFFFF;
            timer_enable <= 1'b0;
        end else begin
            if (timer_enable) begin
                timer_counter <= timer_counter + 1;
            end
            
            if (cs_timer && cpu_dmem_we != 4'b0) begin
                case (cpu_dmem_addr[3:2])
                    2'b00: timer_counter <= cpu_dmem_wdata;
                    2'b01: timer_compare <= cpu_dmem_wdata;
                    2'b10: timer_enable <= cpu_dmem_wdata[0];
                endcase
            end
        end
    end
    
    // ========== Interrupt Controller ==========
    reg [7:0] interrupt_enable;
    reg [7:0] interrupt_pending;
    wire [7:0] interrupt_sources;
    wire [31:0] intc_rdata;
    
    assign interrupt_sources = {4'b0, timer_irq, 1'b0, uart_rx_valid, 1'b0};
    assign irq = |(interrupt_pending & interrupt_enable);
    assign intc_rdata = {16'b0, interrupt_pending, interrupt_enable};
    
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            interrupt_enable <= 8'h0;
            interrupt_pending <= 8'h0;
        end else begin
            interrupt_pending <= interrupt_pending | interrupt_sources;
            
            if (cs_intc && cpu_dmem_we != 4'b0) begin
                case (cpu_dmem_addr[3:2])
                    2'b00: interrupt_enable <= cpu_dmem_wdata[7:0];
                    2'b01: interrupt_pending <= interrupt_pending & ~cpu_dmem_wdata[7:0];
                endcase
            end
        end
    end
    
    // ========== Data Read Multiplexer ==========
    always @(*) begin
        peripheral_rdata = 32'h0;
        if (cs_uart) peripheral_rdata = uart_rdata;
        else if (cs_spi) peripheral_rdata = spi_rdata;
        else if (cs_gpio) peripheral_rdata = gpio_rdata;
        else if (cs_timer) peripheral_rdata = timer_rdata;
        else if (cs_intc) peripheral_rdata = intc_rdata;
    end
    
    assign cpu_dmem_rdata = cs_dmem ? dmem_rdata : peripheral_rdata;
    
    // ========== CPU Core Instance ==========
    riscv_core cpu (
        .clk(clk),
        .rst(rst),
        .imem_addr(cpu_imem_addr),
        .imem_data(cpu_imem_rdata),
        .imem_valid(cpu_imem_valid),
        .dmem_addr(cpu_dmem_addr),
        .dmem_wdata(cpu_dmem_wdata),
        .dmem_rdata(cpu_dmem_rdata),
        .dmem_we(cpu_dmem_we),
        .dmem_valid(cpu_dmem_valid),
        .pc_out(cpu_pc),
        .rd_addr(cpu_rd_addr),
        .rd_data(cpu_rd_data),
        .reg_write(cpu_reg_write)
    );
    
    // ========== Debug Outputs ==========
    assign debug_pc = cpu_pc;
    assign debug_instr = cpu_imem_rdata;

endmodule

// ========== UART Controller ==========
module uart_controller(
    input clk,
    input rst,
    output reg tx,
    input rx,
    input [7:0] tx_data,
    input tx_start,
    output reg tx_ready,
    output reg [7:0] rx_data,
    output reg rx_valid
);
    parameter CLOCK_FREQ = 100000000;
    parameter BAUD_RATE = 115200;
    parameter CLKS_PER_BIT = CLOCK_FREQ / BAUD_RATE;
    
    // TX State Machine
    reg [2:0] tx_state;
    reg [15:0] tx_clk_count;
    reg [2:0] tx_bit_index;
    reg [7:0] tx_shift_reg;
    
    parameter TX_IDLE = 3'b000;
    parameter TX_START = 3'b001;
    parameter TX_DATA = 3'b010;
    parameter TX_STOP = 3'b011;
    
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            tx <= 1'b1;
            tx_state <= TX_IDLE;
            tx_ready <= 1'b1;
            tx_clk_count <= 16'b0;
            tx_bit_index <= 3'b0;
        end else begin
            case (tx_state)
                TX_IDLE: begin
                    tx <= 1'b1;
                    tx_ready <= 1'b1;
                    if (tx_start) begin
                        tx_shift_reg <= tx_data;
                        tx_state <= TX_START;
                        tx_ready <= 1'b0;
                        tx_clk_count <= 16'b0;
                    end
                end
                
                TX_START: begin
                    tx <= 1'b0;
                    if (tx_clk_count < CLKS_PER_BIT - 1) begin
                        tx_clk_count <= tx_clk_count + 1;
                    end else begin
                        tx_clk_count <= 16'b0;
                        tx_state <= TX_DATA;
                        tx_bit_index <= 3'b0;
                    end
                end
                
                TX_DATA: begin
                    tx <= tx_shift_reg[0];
                    if (tx_clk_count < CLKS_PER_BIT - 1) begin
                        tx_clk_count <= tx_clk_count + 1;
                    end else begin
                        tx_clk_count <= 16'b0;
                        tx_shift_reg <= {1'b0, tx_shift_reg[7:1]};
                        if (tx_bit_index < 7) begin
                            tx_bit_index <= tx_bit_index + 1;
                        end else begin
                            tx_state <= TX_STOP;
                        end
                    end
                end
                
                TX_STOP: begin
                    tx <= 1'b1;
                    if (tx_clk_count < CLKS_PER_BIT - 1) begin
                        tx_clk_count <= tx_clk_count + 1;
                    end else begin
                        tx_state <= TX_IDLE;
                    end
                end
            endcase
        end
    end
    
    // RX State Machine
    reg [2:0] rx_state;
    reg [15:0] rx_clk_count;
    reg [2:0] rx_bit_index;
    reg [7:0] rx_shift_reg;
    reg rx_sync1, rx_sync2;
    
    parameter RX_IDLE = 3'b000;
    parameter RX_START = 3'b001;
    parameter RX_DATA = 3'b010;
    parameter RX_STOP = 3'b011;
    
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            rx_state <= RX_IDLE;
            rx_valid <= 1'b0;
            rx_clk_count <= 16'b0;
            rx_bit_index <= 3'b0;
            rx_sync1 <= 1'b1;
            rx_sync2 <= 1'b1;
        end else begin
            rx_sync1 <= rx;
            rx_sync2 <= rx_sync1;
            
            case (rx_state)
                RX_IDLE: begin
                    rx_valid <= 1'b0;
                    if (rx_sync2 == 1'b0) begin
                        rx_state <= RX_START;
                        rx_clk_count <= 16'b0;
                    end
                end
                
                RX_START: begin
                    if (rx_clk_count < (CLKS_PER_BIT / 2) - 1) begin
                        rx_clk_count <= rx_clk_count + 1;
                    end else begin
                        rx_clk_count <= 16'b0;
                        rx_state <= RX_DATA;
                        rx_bit_index <= 3'b0;
                    end
                end
                
                RX_DATA: begin
                    if (rx_clk_count < CLKS_PER_BIT - 1) begin
                        rx_clk_count <= rx_clk_count + 1;
                    end else begin
                        rx_clk_count <= 16'b0;
                        rx_shift_reg <= {rx_sync2, rx_shift_reg[7:1]};
                        if (rx_bit_index < 7) begin
                            rx_bit_index <= rx_bit_index + 1;
                        end else begin
                            rx_state <= RX_STOP;
                        end
                    end
                end
                
                RX_STOP: begin
                    if (rx_clk_count < CLKS_PER_BIT - 1) begin
                        rx_clk_count <= rx_clk_count + 1;
                    end else begin
                        rx_data <= rx_shift_reg;
                        rx_valid <= 1'b1;
                        rx_state <= RX_IDLE;
                    end
                end
            endcase
        end
    end
endmodule

// ========== SPI Master ==========
module spi_master(
    input clk,
    input rst,
    output reg sck,
    output reg mosi,
    input miso,
    output reg cs,
    input [7:0] tx_data,
    input start,
    output reg [7:0] rx_data,
    output reg busy
);
    parameter SPI_CLK_DIV = 4;
    
    reg [2:0] state;
    reg [7:0] clk_count;
    reg [3:0] bit_count;
    reg [7:0] tx_shift;
    reg [7:0] rx_shift;
    
    parameter IDLE = 3'b000;
    parameter TRANSFER = 3'b001;
    parameter DONE = 3'b010;
    
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            state <= IDLE;
            sck <= 1'b0;
            mosi <= 1'b0;
            cs <= 1'b1;
            busy <= 1'b0;
            clk_count <= 8'b0;
            bit_count <= 4'b0;
        end else begin
            case (state)
                IDLE: begin
                    cs <= 1'b1;
                    sck <= 1'b0;
                    busy <= 1'b0;
                    if (start) begin
                        tx_shift <= tx_data;
                        state <= TRANSFER;
                        cs <= 1'b0;
                        busy <= 1'b1;
                        bit_count <= 4'b0;
                        clk_count <= 8'b0;
                    end
                end
                
                TRANSFER: begin
                    if (clk_count < SPI_CLK_DIV - 1) begin
                        clk_count <= clk_count + 1;
                    end else begin
                        clk_count <= 8'b0;
                        sck <= ~sck;
                        
                        if (sck == 1'b0) begin
                            mosi <= tx_shift[7];
                        end else begin
                            tx_shift <= {tx_shift[6:0], 1'b0};
                            rx_shift <= {rx_shift[6:0], miso};
                            bit_count <= bit_count + 1;
                            
                            if (bit_count == 4'd7) begin
                                state <= DONE;
                            end
                        end
                    end
                end
                
                DONE: begin
                    cs <= 1'b1;
                    sck <= 1'b0;
                    rx_data <= rx_shift;
                    state <= IDLE;
                end
            endcase
        end
    end
endmodule