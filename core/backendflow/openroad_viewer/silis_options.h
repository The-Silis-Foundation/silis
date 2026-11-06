// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2020-2025, The OpenROAD Authors
//
// Special Tribute & Acknowledgment:
// This module directly embeds the authentic upstream OpenROAD LayoutViewer
// and RenderThread developed by The OpenROAD Authors (https://theopenroadproject.org).
// Silis extends its deep gratitude and appreciation to the OpenROAD project
// maintainers and contributors for their outstanding, ground-breaking work
// in open-source ASIC physical design automation.

#pragma once
#include <array>
#include <map>
#include "options.h"
#include "odb/db.h"

namespace gui {

class SilisDisplayOptions : public Options {
public:
  SilisDisplayOptions() {
    // OpenROAD authentic upstream metal palette (displayControls.cpp:2095)
    // From http://vrl.cs.brown.edu/color seeded with #00F, #F00, #0D0
    metal_colors_ = {
        QColor(0, 0, 254),
        QColor(254, 0, 0),
        QColor(9, 221, 0),
        QColor(190, 244, 81),
        QColor(222, 33, 96),  // Metal 5
        QColor(32, 216, 253),
        QColor(253, 108, 160),
        QColor(117, 63, 194),
        QColor(128, 155, 49),
        QColor(234, 63, 252),  // Metal 10
        QColor(9, 96, 19),
        QColor(214, 120, 239),
        QColor(192, 222, 164),
        QColor(110, 68, 107)   // Metal 14
    };
    cut_colors_ = {
        QColor(126, 126, 255),
        QColor(255, 126, 126),
        QColor(4, 110, 0),
        QColor(95, 122, 40),
        QColor(111, 17, 48),
        QColor(16, 108, 126),
        QColor(126, 54, 80),
        QColor(58, 32, 97),
        QColor(225, 255, 136),
        QColor(117, 32, 126),
        QColor(18, 192, 38),
        QColor(107, 60, 119),
        QColor(96, 111, 82),
        QColor(220, 136, 214)
    };
  }
  virtual ~SilisDisplayOptions() override = default;

  QColor background() override { return QColor(15, 17, 23); }

  QColor color(const odb::dbTechLayer* const_layer) override {
    if (!const_layer) return QColor(64, 150, 238, 180);
    auto it = layer_colors_.find(const_layer);
    if (it != layer_colors_.end()) return it->second;

    odb::dbTechLayer* layer = const_cast<odb::dbTechLayer*>(const_layer);
    int idx = layer->getRoutingLevel();
    QColor c;
    if (layer->getType() == odb::dbTechLayerType::ROUTING) {
      if (idx > 0 && idx <= (int)metal_colors_.size()) {
        c = metal_colors_[idx - 1];
      } else {
        c = QColor(64, 150, 238);
      }
    } else if (layer->getType() == odb::dbTechLayerType::CUT) {
      if (idx > 0 && idx <= (int)cut_colors_.size()) {
        c = cut_colors_[idx - 1];
      } else {
        c = QColor(126, 126, 255);
      }
    } else {
      c = QColor(100, 100, 100);
    }
    c.setAlpha(180);
    layer_colors_[const_layer] = c;
    return c;
  }

  Qt::BrushStyle pattern(const odb::dbTechLayer* layer) override { return Qt::SolidPattern; }
  QColor placementBlockageColor() override { return QColor(80, 80, 80, 100); }
  Qt::BrushStyle placementBlockagePattern() override { return Qt::Dense4Pattern; }
  QColor regionColor() override { return QColor(100, 180, 255, 60); }
  Qt::BrushStyle regionPattern() override { return Qt::SolidPattern; }
  QColor instanceNameColor() override { return QColor(220, 220, 220); }
  QFont instanceNameFont() override { return QFont("Monospace", 8); }
  QColor itermLabelColor() override { return QColor(200, 200, 200); }
  QFont itermLabelFont() override { return QFont("Monospace", 7); }
  QColor siteColor(odb::dbSite* site) override { return QColor(40, 40, 40); }
  bool isVisible(const odb::dbTechLayer* layer) override { return true; }
  bool isSelectable(const odb::dbTechLayer* layer) override { return true; }
  bool isNetVisible(odb::dbNet* net) override { return true; }
  bool isNetSelectable(odb::dbNet* net) override { return true; }
  bool isInstanceVisible(odb::dbInst* inst) override { return true; }
  bool isInstanceSelectable(odb::dbInst* inst) override { return true; }
  bool areInstanceNamesVisible() override { return true; }
  bool areInstancePinsVisible() override { return true; }
  bool areInstancePinsSelectable() override { return true; }
  bool areInstancePinNamesVisible() override { return true; }
  bool areInstanceBlockagesVisible() override { return true; }
  bool areBlockagesVisible() override { return true; }
  bool areBlockagesSelectable() override { return true; }
  bool areObstructionsVisible() override { return true; }
  bool areObstructionsSelectable() override { return true; }
  bool areSitesVisible() override { return false; }
  bool areSitesSelectable() override { return false; }
  bool isSiteSelectable(odb::dbSite* site) override { return false; }
  bool isSiteVisible(odb::dbSite* site) override { return false; }
  bool arePrefTracksVisible() override { return false; }
  bool areNonPrefTracksVisible() override { return false; }

  bool areIOPinsVisible() const override { return true; }
  bool areIOPinsSelectable() const override { return true; }
  bool areIOPinNamesVisible() const override { return true; }
  QFont ioPinMarkersFont() const override { return QFont("Monospace", 8); }

  bool areRoutingSegmentsVisible() const override { return true; }
  bool areRoutingViasVisible() const override { return true; }
  bool areSpecialRoutingSegmentsVisible() const override { return true; }
  bool areSpecialRoutingViasVisible() const override { return true; }
  bool areFillsVisible() const override { return false; }

  QColor rulerColor() override { return QColor(255, 255, 0); }
  QFont rulerFont() override { return QFont("Monospace", 9); }
  bool areRulersVisible() override { return true; }
  bool areRulersSelectable() override { return true; }

  QFont labelFont() override { return QFont("Monospace", 9); }
  bool areLabelsVisible() override { return true; }
  bool areLabelsSelectable() override { return true; }

  bool isDetailedVisibility() override { return true; }
  bool areSelectedVisible() override { return true; }

  bool isScaleBarVisible() const override { return true; }
  bool areAccessPointsVisible() const override { return true; }
  bool areRegionsVisible() const override { return true; }
  bool areRegionsSelectable() const override { return true; }
  bool isManufacturingGridVisible() const override { return false; }

  bool isModuleView() const override { return false; }

  bool isGCellGridVisible() const override { return false; }
  bool isFlywireHighlightOnly() const override { return false; }
  bool areFocusedNetsGuidesVisible() const override { return true; }

private:
  std::vector<QColor> metal_colors_;
  std::vector<QColor> cut_colors_;
  std::map<const odb::dbTechLayer*, QColor> layer_colors_;
};

} // namespace gui
