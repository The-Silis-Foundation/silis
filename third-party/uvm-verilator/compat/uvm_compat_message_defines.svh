//----------------------------------------------------------------------
// Copyright 2007-2009 Cadence Design Systems, Inc.
// Copyright 2007-2009 Mentor Graphics Corporation
// Copyright 2025-2026 NVIDIA Corporation
//   All Rights Reserved Worldwide
//
//   Licensed under the Apache License, Version 2.0 (the
//   "License"); you may not use this file except in
//   compliance with the License.  You may obtain a copy of
//   the License at
//
//       http://www.apache.org/licenses/LICENSE-2.0
//
//   Unless required by applicable law or agreed to in
//   writing, software distributed under the License is
//   distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
//   CONDITIONS OF ANY KIND, either express or implied.  See
//   the License for the specific language governing
//   permissions and limitations under the License.
//----------------------------------------------------------------------

`define m_uvm_compat_print_begin(PRINTER) \
  begin \
    uvm_printer _local_printer_ = PRINTER; \
    if (_local_printer_ == null) begin \
      _local_printer_ = uvm_printer::get_default(); \
    end 

`define m_uvm_compat_print_end \
  end

// Implementations for both 1.2 and 1800.2

`define uvm_compat_print_int(FIELD, RADIX) \
  `uvm_compat_print_int3(FIELD, RADIX, null)

`define uvm_compat_print_int3(FIELD, RADIX, PRINTER) \
  `uvm_compat_print_int4(FIELD, RADIX, `"FIELD`", PRINTER)

`define uvm_compat_print_object(FIELD) \
  `uvm_compat_print_object2(FIELD, null)

`define uvm_compat_print_string(FIELD) \
  `uvm_compat_print_string2(FIELD, null)

`define uvm_compat_print_array_int(FIELD, RADIX) \
  `uvm_compat_print_array_int3(FIELD, RADIX, null)

`define uvm_compat_print_queue_int(FIELD, RADIX) \
  `uvm_compat_print_queue_int3(FIELD, RADIX, null)

`define uvm_compat_print_array_object(FIELD, FLAG) \
  `uvm_compat_print_array_object3(FIELD, null, FLAG)

`define uvm_compat_print_sarray_object(FIELD, FLAG) \
  `uvm_compat_print_sarray_object3(FIELD, null, FLAG)

`define uvm_compat_print_array_object3(FIELD, PRINTER, FLAG) \
  `uvm_compat_print_object_qda4(FIELD, PRINTER, da, FLAG)

`define uvm_compat_print_sarray_object3(FIELD, PRINTER, FLAG) \
  `uvm_compat_print_object_qda4(FIELD, PRINTER, sa, FLAG)

`define uvm_compat_print_object_queue(FIELD, FLAG) \
  `uvm_compat_print_object_queue3(FIELD, null, FLAG)

`define uvm_compat_print_array_string(FIELD) \
  `uvm_compat_print_array_string2(FIELD, null)

`define uvm_compat_print_array_string2(FIELD, PRINTER) \
  `uvm_compat_print_string_qda3(FIELD, PRINTER, da)

`define uvm_compat_print_sarray_string2(FIELD, PRINTER) \
  `uvm_compat_print_string_qda3(FIELD, PRINTER, sa)

`define uvm_compat_print_string_queue(FIELD) \
  `uvm_compat_print_string_queue2(FIELD, null)

`define uvm_compat_print_string_queue2(FIELD, PRINTER) \
  `uvm_compat_print_string_qda3(FIELD, PRINTER, queue)

// NOTE: This is a bug in 1.2.  The "RADIX" field is "R", which would 
//       likely miscompile a sim.  Someone may have worked around it, though.
`define uvm_compat_print_aa_string_int(FIELD) \
  `uvm_compat_print_aa_string_int3(FIELD, R, null)

// NOTE: Skipping uvm_print_aa_string_object [BUG in 1.2]

`define uvm_compat_print_aa_string_string(FIELD) \
  `uvm_compat_print_aa_string_string2(FIELD, null)

// NOTE: Skipping uvm_print_aa_int_object [BUG in 1.2]


`ifdef UVM_VERSION

// Implementations for 1800.2 ONLY

`define uvm_compat_print_int4(FIELD, RADIX, NAME, PRINTER) \
  `m_uvm_compat_print_begin(PRINTER) \
    `uvm_print_named_int(NAME, FIELD, $bits(FIELD), RADIX, ,_local_printer_) \
  `m_uvm_compat_print_end

`define uvm_compat_print_enum(TYPE, FIELD, NAME, PRINTER) \
  `m_uvm_compat_print_begin(PRINTER) \
    `uvm_print_named_enum(TYPE, NAME, FIELD, _local_printer_) \
  `m_uvm_compat_print_end

`define uvm_compat_print_object2(FIELD, PRINTER) \
  `m_uvm_compat_print_begin(PRINTER) \
    `uvm_print_object(FIELD, , _local_printer_) \
  `m_uvm_compat_print_end

`define uvm_compat_print_string2(FIELD, PRINTER) \
  `m_uvm_compat_print_begin(PRINTER) \
    `uvm_print_string(FIELD, _local_printer_) \
  `m_uvm_compat_print_end

`define uvm_compat_print_array_int3(FIELD, RADIX, PRINTER) \
  `m_uvm_compat_print_begin(PRINTER) \
    `uvm_print_array_int(FIELD, RADIX, , _local_printer_) \
  `m_uvm_compat_print_end

`define uvm_compat_print_sarray_int3(FIELD, RADIX, PRINTER) \
  `m_uvm_compat_print_begin(PRINTER) \
    `uvm_print_sarray_int(FIELD, RADIX, , _local_printer_) \
  `m_uvm_compat_print_end

`define uvm_compat_print_qda_int4(FIELD, RADIX, PRINTER, ARRAY_TYPE) \
  `m_uvm_compat_print_begin(PRINTER) \
    `uvm_print_qda_int(ARRAY_TYPE, FIELD, RADIX, , _local_printer_) \
  `m_uvm_compat_print_end

`define uvm_compat_print_qda_enum(FIELD, PRINTER, ARRAY_TYPE, ENUM_TYPE) \
  `m_uvm_compat_print_begin(PRINTER) \
    `uvm_print_qda_enum(ARRAY_TYPE, ENUM_TYPE, FIELD, _local_printer_) \
  `m_uvm_compat_print_end

`define uvm_compat_print_queue_int3(FIELD, RADIX, PRINTER) \
  `m_uvm_compat_print_begin(PRINTER) \
    `uvm_print_queue_int(FIELD, RADIX, , _local_printer_) \
  `m_uvm_compat_print_end

`define uvm_compat_print_object_qda4(FIELD, PRINTER, ARRAY_TYPE, FLAG) \
  `m_uvm_compat_print_begin(PRINTER) \
    `uvm_print_qda_object(ARRAY_TYPE, FIELD, uvm_pkg::uvm_recursion_policy'(FLAG), _local_printer_) \
  `m_uvm_compat_print_end

`define uvm_compat_print_object_queue3(FIELD, PRINTER, FLAG) \
  `m_uvm_compat_print_begin(PRINTER) \
    `uvm_print_queue_object(FIELD, uvm_pkg::uvm_recursion_policy'(FLAG), _local_printer_) \
  `m_uvm_compat_print_end

`define uvm_compat_print_string_qda3(FIELD, PRINTER, ARRAY_TYPE) \
  `m_uvm_compat_print_begin(PRINTER) \
    `uvm_print_qda_string(ARRAY_TYPE, FIELD, _local_printer_) \
  `m_uvm_compat_print_end

`define uvm_compat_print_aa_string_int3(FIELD, RADIX, PRINTER) \
  `m_uvm_compat_print_begin(PRINTER) \
    `uvm_print_aa_int_string(FIELD, RADIX, , _local_printer_) \
  `m_uvm_compat_print_end

`define uvm_compat_print_aa_string_object3(FIELD, PRINTER, FLAG) \
  `m_uvm_compat_print_begin(PRINTER) \
    `uvm_print_aa_object_string(FIELD, uvm_pkg::uvm_recursion_policy'(FLAG), _local_printer_) \
  `m_uvm_compat_print_end

`define uvm_compat_print_aa_string_string2(FIELD, PRINTER) \
  `m_uvm_compat_print_begin(PRINTER) \
    `uvm_print_aa_string_string(FIELD, _local_printer_) \
  `m_uvm_compat_print_end

`define uvm_compat_print_aa_int_object3(FIELD, PRINTER, FLAG) \
  `m_uvm_compat_print_begin(PRINTER) \
    `uvm_print_aa_object_int(FIELD, uvm_pkg::uvm_recursion_policy'(FLAG), _local_printer_) \
  `m_uvm_compat_print_end

`define uvm_compat_print_aa_int_key4(KEY, FIELD, RADIX, PRINTER) \
  `m_uvm_compat_print_begin(PRINTER) \
    `uvm_print_aa_int_int(FIELD, RADIX, , KEY, _local_printer_) \
  `m_uvm_compat_print_end

`else

// Implementations for 1.2 ONLY

`define uvm_compat_print_int4(FIELD, RADIX, NAME, PRINTER) \
  `uvm_print_int4(FIELD, RADIX, NAME, PRINTER)

`define uvm_compat_print_enum(TYPE, FIELD, NAME, PRINTER) \
  `uvm_print_enum(TYPE, FIELD, NAME, PRINTER)

`define uvm_compat_print_object2(FIELD, PRINTER) \
  `uvm_print_object2(FIELD, PRINTER)

`define uvm_compat_print_string2(FIELD, PRINTER) \
  `uvm_print_string2(FIELD, PRINTER)

`define uvm_compat_print_array_int3(FIELD, RADIX, PRINTER) \
  `uvm_print_array_int3(FIELD, RADIX, PRINTER)

`define uvm_compat_print_sarray_int3(FIELD, RADIX, PRINTER) \
  `uvm_print_sarray_int3(FIELD, RADIX, PRINTER)

`define uvm_compat_print_qda_int4(FIELD, RADIX, PRINTER, ARRAY_TYPE) \
  `uvm_print_qda_int4(FIELD, RADIX, PRINTER, ARRAY_TYPE)

`define uvm_compat_print_qda_enum(FIELD, PRINTER, ARRAY_TYPE, ENUM_TYPE) \
  `uvm_print_qda_enum(FIELD, PRINTER, ARRAY_TYPE, ENUM_TYPE)

`define uvm_compat_print_queue_int3(FIELD, RADIX, PRINTER) \
  `uvm_print_queue_int3(FIELD, RADIX, PRINTER)

`define uvm_compat_print_object_qda4(FIELD, PRINTER, ARRAY_TYPE, FLAG) \
  `uvm_print_object_qda4(FIELD, PRINTER, ARRAY_TYPE, FLAG)

`define uvm_compat_print_object_queue3(FIELD, PRINTER, FLAG) \
  `uvm_print_object_queue3(FIELD, PRINTER, FLAG)

`define uvm_compat_print_string_qda3(FIELD, PRINTER, ARRAY_TYPE) \
  `uvm_print_string_qda3(FIELD, PRINTER, ARRAY_TYPE)

`define uvm_compat_print_aa_string_int3(FIELD, RADIX, PRINTER) \
  `uvm_print_aa_string_int3(FIELD, RADIX, PRINTER)

`define uvm_compat_print_aa_string_object3(FIELD, PRINTER, FLAG) \
  `uvm_print_aa_string_object3(FIELD, PRINTER, FLAG)

`define uvm_compat_print_aa_string_string2(FIELD, PRINTER) \
  `uvm_print_aa_string_string2(FIELD, PRINTER)

`define uvm_compat_print_aa_int_object3(FIELD, PRINTER, FLAG) \
  `uvm_print_aa_int_object3(FIELD, PRINTER, FLAG)

`define uvm_compat_print_aa_int_key4(KEY, FIELD, RADIX, PRINTER) \
  `uvm_print_aa_int_key4(KEY, FIELD, RADIX, PRINTER)

`endif

`undef m_uvm_compat_print_begin
`undef m_uvm_compat_print_end
