// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2020-2025, The OpenROAD Authors
//
// Special Tribute & Acknowledgment:
// This module directly embeds the authentic upstream OpenROAD LayoutViewer
// and RenderThread developed by The OpenROAD Authors (https://theopenroadproject.org).
// Silis extends its deep gratitude and appreciation to the OpenROAD project
// maintainers and contributors for their outstanding, ground-breaking work
// in open-source ASIC physical design automation.

#include <pybind11/pybind11.h>
#include <pybind11/functional.h>
#include <QtWidgets/QApplication>
#include <QtWidgets/QWidget>
#include <iostream>
#include <fstream>
#include <memory>
#include <vector>
#include <string>

#include "gui/gui.h"
#include "layoutViewer.h"
#include "silis_options.h"
#include "/tmp/silis_descriptors.h"
#include "odb/db.h"
#include "utl/Logger.h"

namespace py = pybind11;

class LayoutViewerWrapper : public QObject {
public:
    LayoutViewerWrapper(uintptr_t parent_ptr = 0) {
        QWidget* parent = reinterpret_cast<QWidget*>(parent_ptr);
        options_ = std::make_unique<gui::SilisDisplayOptions>();
        logger_ = std::make_unique<utl::Logger>();
        gui_ = gui::Gui::get();
        gui::registerSilisDescriptors();

        auto true_fn = []() { return true; };
        auto false_fn = []() { return false; };

        viewer_ = new gui::LayoutViewer(
            options_.get(),
            nullptr, // ScriptWidget
            selected_,
            highlighted_,
            rulers_,
            labels_,
            modules_,
            focus_,
            guides_,
            tracks_,
            gui_,
            false_fn, // using_dbu
            true_fn,  // show_ruler_as_euclidian
            false_fn, // show_db_view
            nullptr
        );

        viewer_->setLogger(logger_.get());

        // LayoutScroll constructor: (LayoutViewer*, const std::function<bool()>& zoom, const std::function<int()>& step, QWidget* parent)
        auto mouse_wheel_zoom_fn = []() { return true; };
        auto arrow_step_fn = []() { return 20; };
        scroll_ = new gui::LayoutScroll(viewer_, mouse_wheel_zoom_fn, arrow_step_fn, parent);

        // Connect LayoutViewer::selected signal to our handler
        QObject::connect(viewer_, &gui::LayoutViewer::selected,
                         [this](const gui::Selected& sel, bool connectivity) {
                             selected_.clear();
                             if (sel) {
                                 selected_.insert(sel);
                             }
                             viewer_->repaint();
                             if (on_select_cb_ && sel) {
                                 on_select_cb_(sel.getTypeName(), sel.getName());
                             }
                         });
    }

    ~LayoutViewerWrapper() {
        if (db_) {
            odb::dbDatabase::destroy(db_);
            db_ = nullptr;
        }
    }

    uintptr_t get_qwidget_ptr() const {
        return reinterpret_cast<uintptr_t>(static_cast<QWidget*>(scroll_));
    }

    void fit() {
        if (viewer_) {
            viewer_->fit();
        }
    }

    bool load_odb(const std::string& odb_path) {
        if (!viewer_) return false;
        std::ifstream f(odb_path, std::ios::binary);
        if (!f.is_open()) {
            std::cerr << "[Silis OpenROAD Viewer] Failed to open ODB file: " << odb_path << "\n";
            return false;
        }

        if (db_) {
            odb::dbDatabase::destroy(db_);
            db_ = nullptr;
        }

        db_ = odb::dbDatabase::create();
        db_->read(f);
        f.close();

        odb::dbChip* chip = db_->getChip();
        if (!chip) {
            std::cerr << "[Silis OpenROAD Viewer] No chip in ODB database: " << odb_path << "\n";
            return false;
        }

        std::cout << "[Silis OpenROAD Viewer] Successfully loaded ODB. Calling chipLoaded...\n";
        viewer_->chipLoaded(chip);
        viewer_->fit();
        viewer_->fullRepaint();
        return true;
    }

    void set_on_select_callback(std::function<void(const std::string&, const std::string&)> cb) {
        on_select_cb_ = std::move(cb);
    }

private:
    std::unique_ptr<gui::SilisDisplayOptions> options_;
    std::unique_ptr<utl::Logger> logger_;
    gui::Gui* gui_{nullptr};
    gui::LayoutViewer* viewer_{nullptr};
    gui::LayoutScroll* scroll_{nullptr};
    odb::dbDatabase* db_{nullptr};

    gui::SelectionSet selected_;
    gui::HighlightSet highlighted_;
    gui::Rulers rulers_;
    gui::Labels labels_;
    odb::PtrMap<odb::dbModule, gui::LayoutViewer::ModuleSettings> modules_;
    odb::PtrSet<odb::dbNet> focus_;
    odb::PtrSet<odb::dbNet> guides_;
    odb::PtrSet<odb::dbNet> tracks_;

    std::function<void(const std::string&, const std::string&)> on_select_cb_;
};

PYBIND11_MODULE(silis_openroad_viewer, m) {
    m.doc() = "Official Upstream OpenROAD LayoutViewer Qt6 Bridge for Silis";

    py::class_<LayoutViewerWrapper>(m, "LayoutViewerWrapper")
        .def(py::init<uintptr_t>(), py::arg("parent_ptr") = 0)
        .def("get_qwidget_ptr", &LayoutViewerWrapper::get_qwidget_ptr)
        .def("fit", &LayoutViewerWrapper::fit)
        .def("load_odb", &LayoutViewerWrapper::load_odb, py::arg("odb_path"))
        .def("set_on_select_callback", &LayoutViewerWrapper::set_on_select_callback, py::arg("callback"));
}
