// riscv_core.v - 32-bit RISC-V RV32I CPU Core
// IEEE Std 1364-2005 Verilog Compliant
// Implements RV32I Base Integer Instruction Set
module riscv_core(
    input clk,
    input rst,
    
    // Instruction Memory Interface
    output reg [31:0] imem_addr,
    input [31:0] imem_data,
    output reg imem_valid,
    
    // Data Memory Interface
    output reg [31:0] dmem_addr,
    output reg [31:0] dmem_wdata,
    input [31:0] dmem_rdata,
    output reg [3:0] dmem_we,
    output reg dmem_valid,
    
    // Debug signals
    output reg [31:0] pc_out,
    output reg [4:0] rd_addr,
    output reg [31:0] rd_data,
    output reg reg_write
);

    // ========== Pipeline Stages ==========
    // IF - Instruction Fetch
    // ID - Instruction Decode
    // EX - Execute
    // MEM - Memory Access
    // WB - Write Back

    // ========== Program Counter ==========
    reg [31:0] pc;
    reg [31:0] pc_next;
    
    // ========== Pipeline Registers ==========
    // IF/ID Pipeline Register
    reg [31:0] if_id_pc;
    reg [31:0] if_id_instruction;
    reg if_id_valid;
    
    // ID/EX Pipeline Register
    reg [31:0] id_ex_pc;
    reg [31:0] id_ex_rs1_data;
    reg [31:0] id_ex_rs2_data;
    reg [31:0] id_ex_imm;
    reg [4:0] id_ex_rd;
    reg [4:0] id_ex_rs1;
    reg [4:0] id_ex_rs2;
    reg [6:0] id_ex_opcode;
    reg [2:0] id_ex_funct3;
    reg [6:0] id_ex_funct7;
    reg id_ex_valid;
    
    // EX/MEM Pipeline Register
    reg [31:0] ex_mem_alu_result;
    reg [31:0] ex_mem_rs2_data;
    reg [4:0] ex_mem_rd;
    reg [6:0] ex_mem_opcode;
    reg [2:0] ex_mem_funct3;
    reg ex_mem_valid;
    reg ex_mem_branch_taken;
    reg [31:0] ex_mem_branch_target;
    
    // MEM/WB Pipeline Register
    reg [31:0] mem_wb_alu_result;
    reg [31:0] mem_wb_mem_data;
    reg [4:0] mem_wb_rd;
    reg [6:0] mem_wb_opcode;
    reg mem_wb_valid;
    
    // ========== Register File ==========
    reg [31:0] registers [0:31];
    integer i;
    
    // ========== Instruction Decode Signals ==========
    wire [6:0] opcode;
    wire [4:0] rd;
    wire [2:0] funct3;
    wire [4:0] rs1;
    wire [4:0] rs2;
    wire [6:0] funct7;
    
    assign opcode = if_id_instruction[6:0];
    assign rd = if_id_instruction[11:7];
    assign funct3 = if_id_instruction[14:12];
    assign rs1 = if_id_instruction[19:15];
    assign rs2 = if_id_instruction[24:20];
    assign funct7 = if_id_instruction[31:25];
    
    // ========== Immediate Generation ==========
    reg [31:0] imm;
    reg [31:0] imm_i, imm_s, imm_b, imm_u, imm_j;
    
    always @(*) begin
        // I-type immediate
        imm_i = {{20{if_id_instruction[31]}}, if_id_instruction[31:20]};
        
        // S-type immediate
        imm_s = {{20{if_id_instruction[31]}}, if_id_instruction[31:25], if_id_instruction[11:7]};
        
        // B-type immediate
        imm_b = {{19{if_id_instruction[31]}}, if_id_instruction[31], if_id_instruction[7], 
                 if_id_instruction[30:25], if_id_instruction[11:8], 1'b0};
        
        // U-type immediate
        imm_u = {if_id_instruction[31:12], 12'b0};
        
        // J-type immediate
        imm_j = {{11{if_id_instruction[31]}}, if_id_instruction[31], if_id_instruction[19:12],
                 if_id_instruction[20], if_id_instruction[30:21], 1'b0};
        
        // Select immediate based on opcode
        case (opcode)
            7'b0010011, 7'b0000011, 7'b1100111: imm = imm_i; // I-type
            7'b0100011: imm = imm_s; // S-type
            7'b1100011: imm = imm_b; // B-type
            7'b0110111, 7'b0010111: imm = imm_u; // U-type
            7'b1101111: imm = imm_j; // J-type
            default: imm = 32'b0;
        endcase
    end
    
    // ========== ALU ==========
    reg [31:0] alu_a, alu_b;
    reg [31:0] alu_result;
    reg [3:0] alu_op;
    reg [31:0] alu_add, alu_sub, alu_sll, alu_slt, alu_sltu;
    reg [31:0] alu_xor, alu_srl, alu_sra, alu_or, alu_and;
    reg signed [31:0] alu_a_signed, alu_b_signed;
    
    // ALU Operations
    parameter ALU_ADD  = 4'b0000;
    parameter ALU_SUB  = 4'b0001;
    parameter ALU_SLL  = 4'b0010;
    parameter ALU_SLT  = 4'b0011;
    parameter ALU_SLTU = 4'b0100;
    parameter ALU_XOR  = 4'b0101;
    parameter ALU_SRL  = 4'b0110;
    parameter ALU_SRA  = 4'b0111;
    parameter ALU_OR   = 4'b1000;
    parameter ALU_AND  = 4'b1001;
    
    always @(*) begin
        alu_a = id_ex_rs1_data;
        
        if (id_ex_opcode == 7'b0010011 || id_ex_opcode == 7'b0000011 || 
            id_ex_opcode == 7'b0100011 || id_ex_opcode == 7'b1100111) begin
            alu_b = id_ex_imm;
        end else begin
            alu_b = id_ex_rs2_data;
        end
        
        // Determine ALU operation
        case (id_ex_funct3)
            3'b000: begin
                if (id_ex_funct7[5] && id_ex_opcode == 7'b0110011) begin
                    alu_op = ALU_SUB;
                end else begin
                    alu_op = ALU_ADD;
                end
            end
            3'b001: alu_op = ALU_SLL;
            3'b010: alu_op = ALU_SLT;
            3'b011: alu_op = ALU_SLTU;
            3'b100: alu_op = ALU_XOR;
            3'b101: begin
                if (id_ex_funct7[5]) begin
                    alu_op = ALU_SRA;
                end else begin
                    alu_op = ALU_SRL;
                end
            end
            3'b110: alu_op = ALU_OR;
            3'b111: alu_op = ALU_AND;
            default: alu_op = ALU_ADD;
        endcase
        
        // Perform ALU operations
        alu_add = alu_a + alu_b;
        alu_sub = alu_a - alu_b;
        alu_sll = alu_a << alu_b[4:0];
        
        alu_a_signed = alu_a;
        alu_b_signed = alu_b;
        alu_slt = (alu_a_signed < alu_b_signed) ? 32'd1 : 32'd0;
        alu_sltu = (alu_a < alu_b) ? 32'd1 : 32'd0;
        
        alu_xor = alu_a ^ alu_b;
        alu_srl = alu_a >> alu_b[4:0];
        alu_sra = alu_a_signed >>> alu_b[4:0];
        alu_or = alu_a | alu_b;
        alu_and = alu_a & alu_b;
        
        // Select result
        case (alu_op)
            ALU_ADD:  alu_result = alu_add;
            ALU_SUB:  alu_result = alu_sub;
            ALU_SLL:  alu_result = alu_sll;
            ALU_SLT:  alu_result = alu_slt;
            ALU_SLTU: alu_result = alu_sltu;
            ALU_XOR:  alu_result = alu_xor;
            ALU_SRL:  alu_result = alu_srl;
            ALU_SRA:  alu_result = alu_sra;
            ALU_OR:   alu_result = alu_or;
            ALU_AND:  alu_result = alu_and;
            default:  alu_result = 32'b0;
        endcase
    end
    
    // ========== Branch Unit ==========
    reg branch_taken;
    reg [31:0] branch_target;
    reg beq, bne, blt, bge, bltu, bgeu;
    reg signed [31:0] rs1_signed, rs2_signed;
    
    always @(*) begin
        rs1_signed = id_ex_rs1_data;
        rs2_signed = id_ex_rs2_data;
        
        beq = (id_ex_rs1_data == id_ex_rs2_data);
        bne = (id_ex_rs1_data != id_ex_rs2_data);
        blt = (rs1_signed < rs2_signed);
        bge = (rs1_signed >= rs2_signed);
        bltu = (id_ex_rs1_data < id_ex_rs2_data);
        bgeu = (id_ex_rs1_data >= id_ex_rs2_data);
        
        branch_taken = 1'b0;
        branch_target = id_ex_pc + id_ex_imm;
        
        if (id_ex_opcode == 7'b1100011) begin // Branch instructions
            case (id_ex_funct3)
                3'b000: branch_taken = beq;  // BEQ
                3'b001: branch_taken = bne;  // BNE
                3'b100: branch_taken = blt;  // BLT
                3'b101: branch_taken = bge;  // BGE
                3'b110: branch_taken = bltu; // BLTU
                3'b111: branch_taken = bgeu; // BGEU
                default: branch_taken = 1'b0;
            endcase
        end else if (id_ex_opcode == 7'b1101111) begin // JAL
            branch_taken = 1'b1;
            branch_target = id_ex_pc + id_ex_imm;
        end else if (id_ex_opcode == 7'b1100111) begin // JALR
            branch_taken = 1'b1;
            branch_target = (id_ex_rs1_data + id_ex_imm) & ~32'b1;
        end
    end
    
    // ========== Pipeline Control ==========
    reg stall;
    reg flush;
    
    always @(*) begin
        stall = 1'b0;
        flush = branch_taken;
        
        // Load-use hazard detection
        if (id_ex_opcode == 7'b0000011 && id_ex_valid) begin
            if ((id_ex_rd == rs1 || id_ex_rd == rs2) && id_ex_rd != 5'b0) begin
                stall = 1'b1;
            end
        end
    end
    
    // ========== Forwarding Unit ==========
    reg [1:0] forward_a, forward_b;
    reg [31:0] rs1_data_fwd, rs2_data_fwd;
    reg [31:0] fwd_ex_mem, fwd_mem_wb;
    
    always @(*) begin
        // Determine forwarding sources
        fwd_ex_mem = ex_mem_alu_result;
        fwd_mem_wb = (mem_wb_opcode == 7'b0000011) ? mem_wb_mem_data : mem_wb_alu_result;
        
        // Forward A
        if (ex_mem_valid && ex_mem_rd != 5'b0 && ex_mem_rd == id_ex_rs1) begin
            forward_a = 2'b10; // Forward from EX/MEM
        end else if (mem_wb_valid && mem_wb_rd != 5'b0 && mem_wb_rd == id_ex_rs1) begin
            forward_a = 2'b01; // Forward from MEM/WB
        end else begin
            forward_a = 2'b00; // No forwarding
        end
        
        // Forward B
        if (ex_mem_valid && ex_mem_rd != 5'b0 && ex_mem_rd == id_ex_rs2) begin
            forward_b = 2'b10;
        end else if (mem_wb_valid && mem_wb_rd != 5'b0 && mem_wb_rd == id_ex_rs2) begin
            forward_b = 2'b01;
        end else begin
            forward_b = 2'b00;
        end
        
        // Select forwarded data A
        case (forward_a)
            2'b00: rs1_data_fwd = id_ex_rs1_data;
            2'b01: rs1_data_fwd = fwd_mem_wb;
            2'b10: rs1_data_fwd = fwd_ex_mem;
            default: rs1_data_fwd = id_ex_rs1_data;
        endcase
        
        // Select forwarded data B
        case (forward_b)
            2'b00: rs2_data_fwd = id_ex_rs2_data;
            2'b01: rs2_data_fwd = fwd_mem_wb;
            2'b10: rs2_data_fwd = fwd_ex_mem;
            default: rs2_data_fwd = id_ex_rs2_data;
        endcase
    end
    
    // ========== Pipeline Stages ==========
    
    // Stage 1: Instruction Fetch (IF)
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            pc <= 32'h0;
            if_id_pc <= 32'h0;
            if_id_instruction <= 32'h0;
            if_id_valid <= 1'b0;
            imem_valid <= 1'b0;
        end else begin
            if (!stall) begin
                if (flush) begin
                    pc <= branch_target;
                    if_id_valid <= 1'b0;
                end else begin
                    pc <= pc_next;
                    if_id_pc <= pc;
                    if_id_instruction <= imem_data;
                    if_id_valid <= 1'b1;
                end
                imem_addr <= pc;
                imem_valid <= 1'b1;
            end
        end
    end
    
    always @(*) begin
        pc_next = pc + 4;
    end
    
    // Stage 2: Instruction Decode (ID)
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            id_ex_pc <= 32'h0;
            id_ex_rs1_data <= 32'h0;
            id_ex_rs2_data <= 32'h0;
            id_ex_imm <= 32'h0;
            id_ex_rd <= 5'h0;
            id_ex_rs1 <= 5'h0;
            id_ex_rs2 <= 5'h0;
            id_ex_opcode <= 7'h0;
            id_ex_funct3 <= 3'h0;
            id_ex_funct7 <= 7'h0;
            id_ex_valid <= 1'b0;
        end else begin
            if (stall) begin
                id_ex_valid <= 1'b0;
            end else if (flush) begin
                id_ex_valid <= 1'b0;
            end else begin
                id_ex_pc <= if_id_pc;
                id_ex_rs1_data <= (rs1 == 5'b0) ? 32'b0 : registers[rs1];
                id_ex_rs2_data <= (rs2 == 5'b0) ? 32'b0 : registers[rs2];
                id_ex_imm <= imm;
                id_ex_rd <= rd;
                id_ex_rs1 <= rs1;
                id_ex_rs2 <= rs2;
                id_ex_opcode <= opcode;
                id_ex_funct3 <= funct3;
                id_ex_funct7 <= funct7;
                id_ex_valid <= if_id_valid;
            end
        end
    end
    
    // Stage 3: Execute (EX)
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            ex_mem_alu_result <= 32'h0;
            ex_mem_rs2_data <= 32'h0;
            ex_mem_rd <= 5'h0;
            ex_mem_opcode <= 7'h0;
            ex_mem_funct3 <= 3'h0;
            ex_mem_valid <= 1'b0;
            ex_mem_branch_taken <= 1'b0;
            ex_mem_branch_target <= 32'h0;
        end else begin
            ex_mem_alu_result <= alu_result;
            ex_mem_rs2_data <= rs2_data_fwd;
            ex_mem_rd <= id_ex_rd;
            ex_mem_opcode <= id_ex_opcode;
            ex_mem_funct3 <= id_ex_funct3;
            ex_mem_valid <= id_ex_valid;
            ex_mem_branch_taken <= branch_taken;
            ex_mem_branch_target <= branch_target;
        end
    end
    
    // Stage 4: Memory Access (MEM)
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            mem_wb_alu_result <= 32'h0;
            mem_wb_mem_data <= 32'h0;
            mem_wb_rd <= 5'h0;
            mem_wb_opcode <= 7'h0;
            mem_wb_valid <= 1'b0;
            dmem_valid <= 1'b0;
            dmem_we <= 4'b0;
        end else begin
            mem_wb_alu_result <= ex_mem_alu_result;
            mem_wb_mem_data <= dmem_rdata;
            mem_wb_rd <= ex_mem_rd;
            mem_wb_opcode <= ex_mem_opcode;
            mem_wb_valid <= ex_mem_valid;
            
            // Memory operations
            if (ex_mem_opcode == 7'b0100011 && ex_mem_valid) begin // Store
                dmem_addr <= ex_mem_alu_result;
                dmem_wdata <= ex_mem_rs2_data;
                dmem_valid <= 1'b1;
                case (ex_mem_funct3)
                    3'b000: dmem_we <= 4'b0001; // SB
                    3'b001: dmem_we <= 4'b0011; // SH
                    3'b010: dmem_we <= 4'b1111; // SW
                    default: dmem_we <= 4'b0000;
                endcase
            end else if (ex_mem_opcode == 7'b0000011 && ex_mem_valid) begin // Load
                dmem_addr <= ex_mem_alu_result;
                dmem_valid <= 1'b1;
                dmem_we <= 4'b0000;
            end else begin
                dmem_valid <= 1'b0;
                dmem_we <= 4'b0000;
            end
        end
    end
    
    // Stage 5: Write Back (WB)
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            for (i = 0; i < 32; i = i + 1) begin
                registers[i] <= 32'h0;
            end
            reg_write <= 1'b0;
        end else begin
            reg_write <= 1'b0;
            if (mem_wb_valid && mem_wb_rd != 5'b0) begin
                case (mem_wb_opcode)
                    7'b0110011, 7'b0010011: begin // R-type, I-type ALU
                        registers[mem_wb_rd] <= mem_wb_alu_result;
                        reg_write <= 1'b1;
                    end
                    7'b0000011: begin // Load
                        registers[mem_wb_rd] <= mem_wb_mem_data;
                        reg_write <= 1'b1;
                    end
                    7'b0110111: begin // LUI
                        registers[mem_wb_rd] <= mem_wb_alu_result;
                        reg_write <= 1'b1;
                    end
                    7'b0010111: begin // AUIPC
                        registers[mem_wb_rd] <= mem_wb_alu_result;
                        reg_write <= 1'b1;
                    end
                    7'b1101111, 7'b1100111: begin // JAL, JALR
                        registers[mem_wb_rd] <= mem_wb_alu_result + 4;
                        reg_write <= 1'b1;
                    end
                endcase
            end
        end
    end
    
    // Debug outputs
    always @(*) begin
        pc_out = pc;
        rd_addr = mem_wb_rd;
        rd_data = (mem_wb_opcode == 7'b0000011) ? mem_wb_mem_data : mem_wb_alu_result;
    end

endmodule