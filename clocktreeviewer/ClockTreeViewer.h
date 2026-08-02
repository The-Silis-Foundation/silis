#pragma once

#include <QGraphicsView>
#include <QGraphicsScene>
#include <QGraphicsItem>
#include <QWheelEvent>
#include <QMouseEvent>
#include <string>
#include <vector>
#include <unordered_map>

class ClockTreeNode {
public:
    std::string name;
    std::string type;
    double arrival_time;
    double skew;
    
    // UI Layout properties
    double x = 0;
    double y = 0;
    int depth = 0;
    
    std::vector<ClockTreeNode*> children;
    
    ~ClockTreeNode() {
        for (auto child : children) {
            delete child;
        }
    }
};

class ClockTreeViewer : public QGraphicsView {
    Q_OBJECT
public:
    explicit ClockTreeViewer(QWidget* parent = nullptr);
    ~ClockTreeViewer();

    // Loads JSON data from OpenSTA and builds the visual tree
    void load_tree_data(const std::string& json_str);
    void clear();

protected:
    void wheelEvent(QWheelEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;

private:
    QGraphicsScene* scene_;
    ClockTreeNode* root_node_;
    
    // Panning state
    bool is_panning_;
    QPoint last_mouse_pos_;
    
    // Internal parsers and layout algorithms
    ClockTreeNode* parse_node(const class QJsonObject& obj, int depth);
    void compute_layout(ClockTreeNode* node, double& current_y);
    void draw_tree(ClockTreeNode* node, ClockTreeNode* parent);
    void draw_node(ClockTreeNode* node);
    void draw_edge(ClockTreeNode* parent, ClockTreeNode* child);
};
