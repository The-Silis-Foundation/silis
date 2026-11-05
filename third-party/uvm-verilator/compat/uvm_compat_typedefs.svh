//
//----------------------------------------------------------------------
// Copyright 2010 AMD
// Copyright 2010-2018 Cadence Design Systems, Inc.
// Copyright 2022 Marvell International Ltd.
// Copyright 2010-2011 Mentor Graphics Corporation
// Copyright 2013-2026 NVIDIA Corporation
// Copyright 2025 Qualcomm, Inc.
// Copyright 2010-2011 Synopsys, Inc.
//
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

//----------------------------------------------------------------------
// Git details (see DEVELOPMENT.md):
//
// $File:     compat/uvm_compat_typedefs.svh $
// $Rev:      2026-05-08 07:53:24 -0700 $
// $Hash:     b79027c3a6650c9072fd2772cb849c270ae4cc85 $
//
//----------------------------------------------------------------------

`ifdef UVM_VERSION // 1800.2

typedef uvm_tr_handle_t uvm_compat_tr_handle_t;

typedef uvm_pkg::uvm_default_report_server uvm_compat_default_report_server;

typedef uvm_pkg::uvm_default_factory       uvm_compat_default_factory;

`else // Pre-1800.2

typedef integer uvm_compat_tr_handle_t;

typedef uvm_pkg::uvm_report_server uvm_compat_default_report_server;

typedef uvm_pkg::uvm_factory       uvm_compat_default_factory;

`endif
