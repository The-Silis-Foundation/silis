#include "ClockTreeViewer.h"
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QGraphicsRectItem>
#include <QGraphicsTextItem>
#include <QGraphicsPathItem>
#include <QPainterPath>
#include <QFont>
#include <QFontMetrics>
#include <QPen>
#include <QBrush>
#include <QToolTip>
#include <QScrollBar>
#include <iostream>
#include <iomanip>
#include <sstream>
#include <algorithm>

ClockTreeViewer::ClockTreeViewer(QWidget* parent) 
    : QGraphicsView(parent), root_node_(nullptr), is_panning_(false) {
    scene_ = new QGraphicsScene(this);
    setScene(scene_);
    
    setRenderHint(QPainter::Antialiasing);
    setRenderHint(QPainter::TextAntialiasing);
    setDragMode(QGraphicsView::NoDrag);
    setViewportUpdateMode(QGraphicsView::SmartViewportUpdate);
    setTransformationAnchor(QGraphicsView::AnchorUnderMouse);
    
    // Deep dark obsidian canvas matching Silis EDA theme
    setBackgroundBrush(QBrush(QColor(13, 17, 23)));
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

void ClockTreeViewer::zoom_in() {
    scale(1.2, 1.2);
}

void ClockTreeViewer::zoom_out() {
    scale(1.0 / 1.2, 1.0 / 1.2);
}

void ClockTreeViewer::fit_view() {
    if (scene_ && !scene_->items().isEmpty()) {
        fitInView(scene_->itemsBoundingRect().adjusted(-60, -60, 60, 60), Qt::KeepAspectRatio);
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
    int max_children = 64; // Generous fanout support for chip-scale clock distribution
    for (const QJsonValue& child_val : children) {
        if (count >= max_children) {
            ClockTreeNode* dummy = new ClockTreeNode();
            dummy->name = "(+ " + std::to_string(children.size() - max_children) + " more sinks)";
            dummy->type = "sink";
            dummy->arrival_time = 0.0;
            dummy->skew = 0.0;
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
    
    // Dynamic X position with comfortable spacing per level
    node->x = node->depth * 320.0;
    
    if (node->children.empty()) {
        node->y = current_y;
        current_y += 56.0; // Clean vertical clearance between leaves
    } else {
        for (auto child : node->children) {
            compute_layout(child, current_y);
        }
        // Center parent vertically exactly halfway between first and last child
        double first_y = node->children.front()->y;
        double last_y = node->children.back()->y;
        node->y = (first_y + last_y) / 2.0;
    }
}

void ClockTreeViewer::draw_node(ClockTreeNode* node) {
    // Determine dynamic size based on text length to prevent ugly clipping
    QFont title_font("Segoe UI", 9, QFont::Bold);
    QFontMetrics fm(title_font);
    int text_len = fm.horizontalAdvance(QString::fromStdString(node->name));
    node->width = std::max(160.0, (double)text_len + 54.0);
    node->height = 46.0;

    QColor fill_color;
    QColor border_color;
    std::string tag;

    if (node->type == "port") {
        fill_color = QColor(14, 38, 62);      // Oceanic dark blue
        border_color = QColor(0, 229, 255);    // Electric cyan
        tag = "CLK";
    } else if (node->type == "buffer") {
        fill_color = QColor(26, 35, 50);      // Sleek slate carbon
        border_color = QColor(88, 166, 255);   // Tech blue
        tag = "BUF";
    } else {
        fill_color = QColor(16, 42, 28);      // Deep emerald dark
        border_color = QColor(52, 211, 153);   // Vibrant mint emerald
        tag = "SINK";
    }

    // 1. Draw smooth rounded rectangle
    QPen pen(border_color, 1.5);
    QBrush brush(fill_color);
    QGraphicsRectItem* rect = scene_->addRect(node->x, node->y, node->width, node->height, pen, brush);

    // 2. Format Latency & Skew strings
    std::ostringstream ss_arr;
    ss_arr << std::fixed << std::setprecision(3) << node->arrival_time;

    // 3. Add rich interactive HTML Tooltip
    QString tooltip = QString(
        "<b>Cell:</b> %1<br>"
        "<b>Type:</b> %2 (%3)<br>"
        "<b>Arrival Latency:</b> %4 ns<br>"
        "<b>Depth Level:</b> %5"
    ).arg(QString::fromStdString(node->name))
     .arg(QString::fromStdString(node->type))
     .arg(QString::fromStdString(tag))
     .arg(node->arrival_time)
     .arg(node->depth);
    rect->setToolTip(tooltip);

    // 4. Header Label: Tag badge + instance name
    QString display_title = QString("[%1] %2").arg(QString::fromStdString(tag)).arg(QString::fromStdString(node->name));
    QGraphicsTextItem* title_item = scene_->addText(display_title, title_font);
    title_item->setPos(node->x + 8, node->y + 4);
    title_item->setDefaultTextColor(QColor(240, 246, 252));

    // 5. Subtitle: Arrival Latency
    QFont sub_font("Segoe UI", 8);
    QString sub_info = QString("Arrival: %1 ns").arg(ss_arr.str().c_str());
    if (node->skew > 0.0) {
        sub_info += QString(" | Skew: %1 ps").arg(node->skew * 1000.0, 0, 'f', 1);
    }
    QGraphicsTextItem* sub_item = scene_->addText(sub_info, sub_font);
    sub_item->setPos(node->x + 8, node->y + 22);
    sub_item->setDefaultTextColor(QColor(139, 148, 158));
}

void ClockTreeViewer::draw_edge(ClockTreeNode* parent, ClockTreeNode* child) {
    double px = parent->x + parent->width;
    double py = parent->y + parent->height / 2.0;
    double cx = child->x;
    double cy = child->y + child->height / 2.0;

    // Smooth cubic bezier routing curve (standard in modern EDA clock tree analyzers)
    QPainterPath path;
    path.moveTo(px, py);
    double dx = cx - px;
    path.cubicTo(px + dx * 0.45, py, px + dx * 0.55, cy, cx, cy);

    QPen pen(QColor(88, 166, 255, 175), 1.8);
    scene_->addPath(path, pen);
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
        std::cerr << "[ClockTreeViewer] Invalid JSON provided" << std::endl;
        return;
    }
    
    root_node_ = parse_node(doc.object(), 0);
    
    double current_y = 0;
    compute_layout(root_node_, current_y);
    draw_tree(root_node_, nullptr);
    
    scene_->setSceneRect(scene_->itemsBoundingRect().adjusted(-60, -60, 60, 60));
    fit_view();
}

void ClockTreeViewer::wheelEvent(QWheelEvent* event) {
    if (event->angleDelta().y() > 0) {
        scale(1.15, 1.15);
    } else {
        scale(1.0 / 1.15, 1.0 / 1.15);
    }
}

void ClockTreeViewer::mousePressEvent(QMouseEvent* event) {
    // Both Left-click drag and Middle-button drag enable intuitive panning on trackpads & mice
    if (event->button() == Qt::LeftButton || event->button() == Qt::MiddleButton) {
        is_panning_ = true;
        last_mouse_pos_ = event->pos();
        setCursor(Qt::ClosedHandCursor);
        event->accept();
        return;
    }
    QGraphicsView::mousePressEvent(event);
}

void ClockTreeViewer::mouseMoveEvent(QMouseEvent* event) {
    if (is_panning_) {
        QPoint delta = event->pos() - last_mouse_pos_;
        last_mouse_pos_ = event->pos();
        horizontalScrollBar()->setValue(horizontalScrollBar()->value() - delta.x());
        verticalScrollBar()->setValue(verticalScrollBar()->value() - delta.y());
        event->accept();
        return;
    }
    QGraphicsView::mouseMoveEvent(event);
}

void ClockTreeViewer::mouseReleaseEvent(QMouseEvent* event) {
    if (is_panning_) {
        is_panning_ = false;
        setCursor(Qt::ArrowCursor);
        event->accept();
        return;
    }
    QGraphicsView::mouseReleaseEvent(event);
}

void ClockTreeViewer::mouseDoubleClickEvent(QMouseEvent* event) {
    // Double click resets zoom to fit the entire clock distribution network in view
    fit_view();
    event->accept();
}
