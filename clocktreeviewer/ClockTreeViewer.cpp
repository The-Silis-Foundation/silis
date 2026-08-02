#include "ClockTreeViewer.h"
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QGraphicsRectItem>
#include <QGraphicsTextItem>
#include <QGraphicsLineItem>
#include <QPen>
#include <QBrush>
#include <QToolTip>
#include <QScrollBar>
#include <iostream>

ClockTreeViewer::ClockTreeViewer(QWidget* parent) 
    : QGraphicsView(parent), root_node_(nullptr), is_panning_(false) {
    scene_ = new QGraphicsScene(this);
    setScene(scene_);
    
    setRenderHint(QPainter::Antialiasing);
    setDragMode(QGraphicsView::NoDrag);
    setViewportUpdateMode(QGraphicsView::SmartViewportUpdate);
    setTransformationAnchor(QGraphicsView::AnchorUnderMouse);
    setBackgroundBrush(QBrush(QColor(30, 30, 30)));
}

ClockTreeViewer::~ClockTreeViewer() {
    clear();
}

void ClockTreeViewer::clear() {
    scene_->clear();
    if (root_node_) {
        delete root_node_;
        root_node_ = nullptr;
    }
}

ClockTreeNode* ClockTreeViewer::parse_node(const QJsonObject& obj, int depth) {
    ClockTreeNode* node = new ClockTreeNode();
    node->name = obj["name"].toString().toStdString();
    node->type = obj["type"].toString().toStdString();
    node->arrival_time = obj["arrival"].toDouble();
    node->skew = obj.contains("skew") ? obj["skew"].toDouble() : 0.0;
    node->depth = depth;
    
    QJsonArray children = obj["children"].toArray();
    int count = 0;
    int max_children = 15;
    for (const QJsonValue& child_val : children) {
        if (count >= max_children) {
            ClockTreeNode* dummy = new ClockTreeNode();
            dummy->name = "(+ " + std::to_string(children.size() - max_children) + " more sinks)";
            dummy->type = "sink";
            dummy->arrival_time = 0;
            dummy->skew = 0;
            dummy->depth = depth + 1;
            node->children.push_back(dummy);
            break;
        }
        node->children.push_back(parse_node(child_val.toObject(), depth + 1));
        count++;
    }
    return node;
}

void ClockTreeViewer::compute_layout(ClockTreeNode* node, double& current_y) {
    if (!node) return;
    
    // Fixed X position based on depth
    node->x = node->depth * 300.0;
    
    if (node->children.empty()) {
        node->y = current_y;
        current_y += 60.0; // Vertical spacing between leaves
    } else {
        double start_y = current_y;
        for (auto child : node->children) {
            compute_layout(child, current_y);
        }
        // Center parent vertically among children
        node->y = (start_y + (current_y - 60.0)) / 2.0;
    }
}

void ClockTreeViewer::draw_node(ClockTreeNode* node) {
    QColor color;
    if (node->type == "port") color = QColor(200, 50, 50);
    else if (node->type == "buffer") color = QColor(50, 150, 200);
    else color = QColor(50, 200, 50); // sink
    
    double w = 120;
    double h = 40;
    QGraphicsRectItem* rect = scene_->addRect(node->x, node->y, w, h, QPen(Qt::black), QBrush(color));
    
    QString tooltip = QString("Name: %1\nType: %2\nArrival: %3 ns\nSkew: %4 ns")
        .arg(node->name.c_str())
        .arg(node->type.c_str())
        .arg(node->arrival_time)
        .arg(node->skew);
    rect->setToolTip(tooltip);
    
    QGraphicsTextItem* text = scene_->addText(QString::fromStdString(node->name));
    text->setPos(node->x + 5, node->y + 5);
    text->setDefaultTextColor(Qt::white);
}

void ClockTreeViewer::draw_edge(ClockTreeNode* parent, ClockTreeNode* child) {
    double px = parent->x + 120;
    double py = parent->y + 20;
    double cx = child->x;
    double cy = child->y + 20;
    
    QPen pen(QColor(150, 150, 150), 2);
    // Draw manhattan routing
    scene_->addLine(px, py, px + 50, py, pen);
    scene_->addLine(px + 50, py, px + 50, cy, pen);
    scene_->addLine(px + 50, cy, cx, cy, pen);
}

void ClockTreeViewer::draw_tree(ClockTreeNode* node, ClockTreeNode* parent) {
    if (!node) return;
    
    draw_node(node);
    if (parent) {
        draw_edge(parent, node);
    }
    
    for (auto child : node->children) {
        draw_tree(child, node);
    }
}

void ClockTreeViewer::load_tree_data(const std::string& json_str) {
    clear();
    
    QJsonDocument doc = QJsonDocument::fromJson(QByteArray::fromStdString(json_str));
    if (doc.isNull() || !doc.isObject()) {
        std::cerr << "Invalid JSON provided to ClockTreeViewer" << std::endl;
        return;
    }
    
    root_node_ = parse_node(doc.object(), 0);
    
    double current_y = 0;
    compute_layout(root_node_, current_y);
    draw_tree(root_node_, nullptr);
    
    scene_->setSceneRect(scene_->itemsBoundingRect().adjusted(-50, -50, 50, 50));
    fitInView(scene_->sceneRect(), Qt::KeepAspectRatio);
}

void ClockTreeViewer::wheelEvent(QWheelEvent* event) {
    if (event->angleDelta().y() > 0) {
        scale(1.1, 1.1);
    } else {
        scale(1.0 / 1.1, 1.0 / 1.1);
    }
}

void ClockTreeViewer::mousePressEvent(QMouseEvent* event) {
    if (event->button() == Qt::MiddleButton) {
        is_panning_ = true;
        last_mouse_pos_ = event->pos();
        setCursor(Qt::ClosedHandCursor);
    } else {
        QGraphicsView::mousePressEvent(event);
    }
}

void ClockTreeViewer::mouseMoveEvent(QMouseEvent* event) {
    if (is_panning_) {
        QPoint delta = event->pos() - last_mouse_pos_;
        last_mouse_pos_ = event->pos();
        horizontalScrollBar()->setValue(horizontalScrollBar()->value() - delta.x());
        verticalScrollBar()->setValue(verticalScrollBar()->value() - delta.y());
    } else {
        QGraphicsView::mouseMoveEvent(event);
    }
}

void ClockTreeViewer::mouseReleaseEvent(QMouseEvent* event) {
    if (event->button() == Qt::MiddleButton) {
        is_panning_ = false;
        setCursor(Qt::ArrowCursor);
    } else {
        QGraphicsView::mouseReleaseEvent(event);
    }
}
