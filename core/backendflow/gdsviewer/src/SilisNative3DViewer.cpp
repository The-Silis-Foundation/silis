#include "SilisNative3DViewer.h"
#include <algorithm>
#include <cmath>

static const char* VERT_SHADER = R"(
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
layout(location = 2) in vec2 aUV;
layout(location = 3) in vec4 aInstRect; // x, y, w, h

uniform mat4 uMVP;
uniform float uZMin;
uniform float uZMax;
uniform float uZScale;

out vec3 vNormal;
out vec2 vUV;
out vec3 vWorldPos;

void main() {
    float z0 = uZMin * uZScale;
    float z1 = uZMax * uZScale;
    vec3 worldPos = vec3(
        aInstRect.x + aPos.x * aInstRect.z,
        aInstRect.y + aPos.y * aInstRect.w,
        mix(z0, z1, aPos.z)
    );
    vNormal = aNormal;
    vUV = aUV;
    vWorldPos = worldPos;
    gl_Position = uMVP * vec4(worldPos, 1.0);
}
)";

static const char* FRAG_SHADER = R"(
#version 330 core
in vec3 vNormal;
in vec2 vUV;
in vec3 vWorldPos;

uniform vec4 uColor;
uniform float uClipZ;
uniform vec3 uEyePos;

out vec4 FragColor;

void main() {
    if (vWorldPos.z > uClipZ) {
        discard;
    }
    vec3 N = normalize(vNormal);
    vec3 L = normalize(vec3(0.45, 0.35, 0.82));
    vec3 V = normalize(uEyePos - vWorldPos);
    vec3 H = normalize(L + V);

    float diff = max(dot(N, L), 0.0);
    float hemi = 0.5 + 0.5 * N.z;
    float spec = pow(max(dot(N, H), 0.0), 16.0) * 0.58;
    float fresnel = pow(1.0 - max(dot(N, V), 0.0), 3.0) * 0.22;

    // Feather-light procedural brushed grain
    float grain = sin(vWorldPos.x * 12.0) * sin(vWorldPos.y * 12.0) * 0.025;
    vec3 lit = uColor.rgb * (0.32 + 0.58 * diff + 0.18 * hemi + grain) + vec3(spec + fresnel);

    // Machined edge bevel for crisp track separation
    vec2 edge = min(vUV, 1.0 - vUV);
    float min_e = min(edge.x, edge.y);
    float rim = smoothstep(0.0, 0.035, min_e);
    lit *= mix(0.72, 1.0, rim);

    FragColor = vec4(lit, uColor.a);
}
)";

SilisNative3DViewer::SilisNative3DViewer(QWidget* parent)
    : QOpenGLWidget(parent) {
    setFocusPolicy(Qt::StrongFocus);
    m_fly_timer = new QTimer(this);
    m_fly_timer->setInterval(16);
    connect(m_fly_timer, &QTimer::timeout, this, &SilisNative3DViewer::tickCamera);
}

SilisNative3DViewer::~SilisNative3DViewer() {
    makeCurrent();
    for (auto& b : m_batches) {
        if (b.instance_vbo) {
            glDeleteBuffers(1, &b.instance_vbo);
            b.instance_vbo = 0;
        }
    }
    delete m_program;
    m_vao.destroy();
    m_cube_vbo.destroy();
    m_cube_ebo.destroy();
    doneCurrent();
}

uintptr_t SilisNative3DViewer::getPtr() const {
    return reinterpret_cast<uintptr_t>(static_cast<const QWidget*>(this));
}

void SilisNative3DViewer::clear() {
    if (m_gl_ready) {
        makeCurrent();
        for (auto& b : m_batches) {
            if (b.instance_vbo) {
                glDeleteBuffers(1, &b.instance_vbo);
            }
        }
        doneCurrent();
    }
    m_batches.clear();
    m_batch_map.clear();
    m_max_z_stack = 15.0f;
    update();
}

void SilisNative3DViewer::setBounds(float min_x, float min_y, float max_x, float max_y) {
    m_min_x = min_x;
    m_min_y = min_y;
    m_max_x = max_x;
    m_max_y = max_y;
    float w = std::max(1.0f, max_x - min_x);
    float h = std::max(1.0f, max_y - min_y);
    setLayerData("substrate", {min_x}, {min_y}, {w}, {h}, -1.5f, 0.0f, 0.14f, 0.16f, 0.20f, 1.0f);
    fitInView();
}

void SilisNative3DViewer::setLayerData(
    const std::string& name,
    const std::vector<float>& x,
    const std::vector<float>& y,
    const std::vector<float>& w,
    const std::vector<float>& h,
    float z_min,
    float z_max,
    float r, float g, float b, float a
) {
    size_t n = std::min({x.size(), y.size(), w.size(), h.size()});
    size_t idx = 0;
    auto it = m_batch_map.find(name);
    if (it == m_batch_map.end()) {
        idx = m_batches.size();
        m_batches.emplace_back();
        m_batch_map[name] = idx;
    } else {
        idx = it->second;
    }
    Layer3DBatch& batch = m_batches[idx];
    batch.name = name;
    batch.z_min = z_min;
    batch.z_max = z_max;
    batch.color = QVector4D(r, g, b, a);
    batch.instances.resize(n * 4);
    for (size_t i = 0; i < n; ++i) {
        batch.instances[i * 4 + 0] = x[i];
        batch.instances[i * 4 + 1] = y[i];
        batch.instances[i * 4 + 2] = w[i];
        batch.instances[i * 4 + 3] = h[i];
    }
    batch.instance_count = n;
    batch.dirty = true;
    m_max_z_stack = std::max(m_max_z_stack, z_max);
    update();
}

void SilisNative3DViewer::setLayerVisible(const std::string& name, bool visible) {
    auto it = m_batch_map.find(name);
    if (it != m_batch_map.end()) {
        m_batches[it->second].visible = visible;
        update();
    }
}

void SilisNative3DViewer::setZScale(float scale) {
    m_z_scale = std::max(0.1f, scale);
    update();
}

void SilisNative3DViewer::setClipZ(float max_z) {
    m_clip_z = max_z;
    update();
}

void SilisNative3DViewer::setCameraPreset(const std::string& preset) {
    if (preset == "top") {
        m_yaw = 0.0f;
        m_pitch = 89.0f;
    } else if (preset == "front") {
        m_yaw = 0.0f;
        m_pitch = 5.0f;
    } else {
        m_yaw = 45.0f;
        m_pitch = 35.0f;
    }
    update();
}

void SilisNative3DViewer::fitInView() {
    float cx = 0.5f * (m_min_x + m_max_x);
    float cy = 0.5f * (m_min_y + m_max_y);
    float span = std::max(m_max_x - m_min_x, m_max_y - m_min_y);
    if (span < 1.0f) span = 100.0f;
    m_target = QVector3D(cx, cy, 0.5f * m_max_z_stack * m_z_scale);
    m_distance = span * 1.15f;
    update();
}

void SilisNative3DViewer::buildCubeGeometry() {
    // 24 vertices: pos(3), normal(3), uv(2)
    static const float verts[] = {
        // +Z (top)
        0,0,1,  0,0,1,  0,0,
        1,0,1,  0,0,1,  1,0,
        1,1,1,  0,0,1,  1,1,
        0,1,1,  0,0,1,  0,1,
        // -Z (bottom)
        0,0,0,  0,0,-1, 0,0,
        0,1,0,  0,0,-1, 0,1,
        1,1,0,  0,0,-1, 1,1,
        1,0,0,  0,0,-1, 1,0,
        // +Y (north)
        0,1,0,  0,1,0,  0,0,
        0,1,1,  0,1,0,  0,1,
        1,1,1,  0,1,0,  1,1,
        1,1,0,  0,1,0,  1,0,
        // -Y (south)
        0,0,0,  0,-1,0, 0,0,
        1,0,0,  0,-1,0, 1,0,
        1,0,1,  0,-1,0, 1,1,
        0,0,1,  0,-1,0, 0,1,
        // +X (east)
        1,0,0,  1,0,0,  0,0,
        1,1,0,  1,0,0,  1,0,
        1,1,1,  1,0,0,  1,1,
        1,0,1,  1,0,0,  0,1,
        // -X (west)
        0,0,0, -1,0,0,  0,0,
        0,0,1, -1,0,0,  0,1,
        0,1,1, -1,0,0,  1,1,
        0,1,0, -1,0,0,  1,0,
    };
    static const unsigned int indices[] = {
        0,1,2, 0,2,3,
        4,5,6, 4,6,7,
        8,9,10, 8,10,11,
        12,13,14, 12,14,15,
        16,17,18, 16,18,19,
        20,21,22, 20,22,23
    };

    m_vao.create();
    m_vao.bind();

    m_cube_vbo.create();
    m_cube_vbo.bind();
    m_cube_vbo.allocate(verts, sizeof(verts));

    m_cube_ebo.create();
    m_cube_ebo.bind();
    m_cube_ebo.allocate(indices, sizeof(indices));

    const int stride = 8 * sizeof(float);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, reinterpret_cast<void*>(0));
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, reinterpret_cast<void*>(3 * sizeof(float)));
    glEnableVertexAttribArray(2);
    glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, stride, reinterpret_cast<void*>(6 * sizeof(float)));

    m_vao.release();
}

void SilisNative3DViewer::initializeGL() {
    initializeOpenGLFunctions();
    glEnable(GL_DEPTH_TEST);
    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);

    m_program = new QOpenGLShaderProgram(this);
    m_program->addShaderFromSourceCode(QOpenGLShader::Vertex, VERT_SHADER);
    m_program->addShaderFromSourceCode(QOpenGLShader::Fragment, FRAG_SHADER);
    m_program->link();

    buildCubeGeometry();
    m_gl_ready = true;
}

void SilisNative3DViewer::resizeGL(int w, int h) {
    glViewport(0, 0, w, std::max(1, h));
}

void SilisNative3DViewer::uploadDirtyBatches() {
    for (auto& b : m_batches) {
        if (!b.dirty) continue;
        if (!b.instance_vbo) {
            glGenBuffers(1, &b.instance_vbo);
        }
        glBindBuffer(GL_ARRAY_BUFFER, b.instance_vbo);
        glBufferData(GL_ARRAY_BUFFER, b.instances.size() * sizeof(float), b.instances.data(), GL_STATIC_DRAW);
        glBindBuffer(GL_ARRAY_BUFFER, 0);
        b.dirty = false;
    }
}

void SilisNative3DViewer::paintGL() {
    glClearColor(0.09f, 0.10f, 0.12f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
    if (!m_program || !m_gl_ready) return;

    uploadDirtyBatches();

    float aspect = static_cast<float>(width()) / std::max(1, height());
    QMatrix4x4 proj;
    float near_p = std::max(0.0001f, m_distance * 0.001f);
    float far_p = std::max(5000.0f, m_distance * 50.0f);
    proj.perspective(45.0f, aspect, near_p, far_p);

    float rad_yaw = m_yaw * 3.14159265f / 180.0f;
    float rad_pitch = m_pitch * 3.14159265f / 180.0f;
    QVector3D eye(
        m_target.x() + m_distance * std::cos(rad_pitch) * std::sin(rad_yaw),
        m_target.y() - m_distance * std::cos(rad_pitch) * std::cos(rad_yaw),
        m_target.z() + m_distance * std::sin(rad_pitch)
    );
    QMatrix4x4 view;
    view.lookAt(eye, m_target, QVector3D(0.0f, 0.0f, 1.0f));
    QMatrix4x4 mvp = proj * view;

    m_program->bind();
    m_program->setUniformValue("uMVP", mvp);
    m_program->setUniformValue("uZScale", m_z_scale);
    m_program->setUniformValue("uClipZ", m_clip_z * m_z_scale);
    m_program->setUniformValue("uEyePos", eye);

    m_vao.bind();
    for (const auto& b : m_batches) {
        if (!b.visible || b.instance_count == 0 || !b.instance_vbo) continue;

        m_program->setUniformValue("uZMin", b.z_min);
        m_program->setUniformValue("uZMax", b.z_max);
        m_program->setUniformValue("uColor", b.color);

        glBindBuffer(GL_ARRAY_BUFFER, b.instance_vbo);
        glEnableVertexAttribArray(3);
        glVertexAttribPointer(3, 4, GL_FLOAT, GL_FALSE, 4 * sizeof(float), nullptr);
        glVertexAttribDivisor(3, 1);

        glDrawElementsInstanced(GL_TRIANGLES, 36, GL_UNSIGNED_INT, nullptr, static_cast<GLsizei>(b.instance_count));
    }
    m_vao.release();
    m_program->release();
}

void SilisNative3DViewer::mousePressEvent(QMouseEvent* event) {
    setFocus(Qt::MouseFocusReason);
    m_last_mouse = event->pos();
    m_drag_btn = event->button();
}

void SilisNative3DViewer::mouseMoveEvent(QMouseEvent* event) {
    QPoint delta = event->pos() - m_last_mouse;
    m_last_mouse = event->pos();

    if (m_mouse_look || m_drag_btn == Qt::LeftButton) {
        m_yaw += delta.x() * 0.25f;
        m_pitch = std::clamp(m_pitch - delta.y() * 0.25f, -89.0f, 89.0f);
        update();
    } else if (m_drag_btn == Qt::RightButton || m_drag_btn == Qt::MiddleButton) {
        float pan_speed = m_distance * 0.0008f;
        float rad_yaw = m_yaw * 3.14159265f / 180.0f;
        QVector3D right(std::cos(rad_yaw), std::sin(rad_yaw), 0.0f);
        QVector3D forward(-std::sin(rad_yaw), std::cos(rad_yaw), 0.0f);
        m_target += right * (delta.x() * pan_speed);
        m_target -= forward * (delta.y() * pan_speed);
        update();
    }
}

void SilisNative3DViewer::wheelEvent(QWheelEvent* event) {
    int delta = event->angleDelta().y();
    if (delta == 0) return;

    float steps = static_cast<float>(delta) / 120.0f;
    float factor = std::pow(0.72f, steps);
    if (delta > 0 && m_distance < 5.0f) {
        // Dolly forward along view ray so zoom never locks at m_target
        float rad_yaw = m_yaw * 3.14159265f / 180.0f;
        float rad_pitch = m_pitch * 3.14159265f / 180.0f;
        QVector3D look_dir(
            -std::cos(rad_pitch) * std::sin(rad_yaw),
            std::cos(rad_pitch) * std::cos(rad_yaw),
            -std::sin(rad_pitch)
        );
        m_target += look_dir * (std::max(0.5f, m_distance) * 0.35f * steps);
    } else {
        m_distance = std::max(0.05f, m_distance * factor);
    }
    update();
}

bool SilisNative3DViewer::event(QEvent* event) {
    if (event->type() == QEvent::ShortcutOverride) {
        auto* ke = static_cast<QKeyEvent*>(event);
        switch (ke->key()) {
            case Qt::Key_W: case Qt::Key_A: case Qt::Key_S: case Qt::Key_D:
            case Qt::Key_Q: case Qt::Key_Z: case Qt::Key_R: case Qt::Key_M:
            case Qt::Key_Up: case Qt::Key_Down: case Qt::Key_Left: case Qt::Key_Right:
                ke->accept();
                return true;
            default:
                break;
        }
    }
    return QOpenGLWidget::event(event);
}

void SilisNative3DViewer::keyPressEvent(QKeyEvent* event) {
    int k = event->key();
    if (k == Qt::Key_R) {
        fitInView();
        event->accept();
        return;
    }
    if (k == Qt::Key_M) {
        m_mouse_look = !m_mouse_look;
        setMouseTracking(m_mouse_look);
        setCursor(m_mouse_look ? Qt::CrossCursor : Qt::ArrowCursor);
        m_last_mouse = mapFromGlobal(QCursor::pos());
        event->accept();
        return;
    }
    if (k == Qt::Key_W || k == Qt::Key_A || k == Qt::Key_S || k == Qt::Key_D ||
        k == Qt::Key_Q || k == Qt::Key_Z || k == Qt::Key_Shift ||
        k == Qt::Key_Up || k == Qt::Key_Down || k == Qt::Key_Left || k == Qt::Key_Right) {
        m_keys.insert(k);
        if (!m_fly_timer->isActive()) m_fly_timer->start();
        event->accept();
        return;
    }
    QOpenGLWidget::keyPressEvent(event);
}

void SilisNative3DViewer::keyReleaseEvent(QKeyEvent* event) {
    m_keys.erase(event->key());
    if (m_keys.empty() && m_fly_timer->isActive()) {
        m_fly_timer->stop();
    }
    QOpenGLWidget::keyReleaseEvent(event);
}

void SilisNative3DViewer::focusOutEvent(QFocusEvent* event) {
    m_keys.clear();
    if (m_fly_timer->isActive()) m_fly_timer->stop();
    QOpenGLWidget::focusOutEvent(event);
}

void SilisNative3DViewer::tickCamera() {
    if (m_keys.empty()) return;
    float mult = m_keys.count(Qt::Key_Shift) ? 3.0f : 1.0f;
    float span = std::max(10.0f, std::max(m_max_x - m_min_x, m_max_y - m_min_y));
    float step = std::max(1.0f, span * 0.008f) * mult;
    float rad_yaw = m_yaw * 3.14159265f / 180.0f;
    QVector3D right(std::cos(rad_yaw), std::sin(rad_yaw), 0.0f);
    QVector3D forward(-std::sin(rad_yaw), std::cos(rad_yaw), 0.0f);

    bool moved = false;
    if (m_keys.count(Qt::Key_W) || m_keys.count(Qt::Key_Up))    { m_target += forward * step; moved = true; }
    if (m_keys.count(Qt::Key_S) || m_keys.count(Qt::Key_Down))  { m_target -= forward * step; moved = true; }
    if (m_keys.count(Qt::Key_A) || m_keys.count(Qt::Key_Left))  { m_target -= right * step;   moved = true; }
    if (m_keys.count(Qt::Key_D) || m_keys.count(Qt::Key_Right)) { m_target += right * step;   moved = true; }
    if (m_keys.count(Qt::Key_Q)) { m_target.setZ(m_target.z() + step); moved = true; }
    if (m_keys.count(Qt::Key_Z)) { m_target.setZ(m_target.z() - step); moved = true; }
    if (moved) update();
}
