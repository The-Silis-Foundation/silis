#pragma once

#include <string>
#include <vector>
#include "SchematicViewer.h"

class SchematicRouter {
public:
    SchematicRouter(SchematicViewer* viewer);

    // Parses the json, lays out the blocks, routes the wires, and populates the viewer.
    void parse_and_draw_json(const std::string& json_path, const std::string& target_module, const std::string& mode, int channel_spacing = 400);

private:
    SchematicViewer* viewer_;
};
