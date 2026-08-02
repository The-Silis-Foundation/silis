import re

with open("/home/jerome/silis/third-party/GDS3D/gdsoglviewer/renderer.h", "r") as f:
    content = f.read()

# Add vector include
if "#include <vector>" not in content:
    content = content.replace("#include \"../math/Maths.h\"", "#include \"../math/Maths.h\"\n#include <vector>")

# Add instance_data_t
instance_struct = """
typedef struct instance_data_t {
    MATRIX4X4 mat;
    VECTOR4D color;
} instance_data_t;
"""
if "instance_data_t" not in content:
    content = content.replace("typedef struct renderRecipe_t{", instance_struct + "\ntypedef struct renderRecipe_t{")
    content = content.replace("    struct  renderRecipe_t* next;\n}renderRecipe_t;", "    std::vector<instance_data_t> instances;\n    struct  renderRecipe_t* next;\n}renderRecipe_t;")

if "GLuint instanceVBO;" not in content:
    content = content.replace("    GLuint	FBO2;\n	GLuint  RBO2_color;\n    \n    // Vertex creation", "    GLuint	FBO2;\n	GLuint  RBO2_color;\n    \n    GLuint instanceVBO;\n    // Vertex creation")

with open("/home/jerome/silis/third-party/GDS3D/gdsoglviewer/renderer.h", "w") as f:
    f.write(content)

with open("/home/jerome/silis/third-party/GDS3D/gdsoglviewer/renderer.cpp", "r") as f:
    content = f.read()

exts = """
#ifdef GL_ARB_vertex_buffer_object
PFNGLDRAWELEMENTSINSTANCEDARBPROC glDrawElementsInstancedARB = NULL;
PFNGLVERTEXATTRIBDIVISORARBPROC glVertexAttribDivisorARB = NULL;
PFNGLGETATTRIBLOCATIONARBPROC glGetAttribLocationARB = NULL;
PFNGLVERTEXATTRIBPOINTERARBPROC glVertexAttribPointerARB = NULL;
PFNGLENABLEVERTEXATTRIBARRAYARBPROC glEnableVertexAttribArrayARB = NULL;
PFNGLDISABLEVERTEXATTRIBARRAYARBPROC glDisableVertexAttribArrayARB = NULL;
#endif
"""
if "glDrawElementsInstancedARB" not in content:
    content = content.replace("PFNGLDELETEBUFFERSARBPROC glDeleteBuffersARB = NULL;			// VBO Deletion Procedure\n#endif", "PFNGLDELETEBUFFERSARBPROC glDeleteBuffersARB = NULL;			// VBO Deletion Procedure\n" + exts + "\n#endif")

load_exts_win = """
#ifdef GL_ARB_vertex_buffer_object
    glGenBuffersARB = (PFNGLGENBUFFERSARBPROC) wglGetProcAddress("glGenBuffersARB");
    glBindBufferARB = (PFNGLBINDBUFFERARBPROC) wglGetProcAddress("glBindBufferARB");
    glBufferDataARB = (PFNGLBUFFERDATAARBPROC) wglGetProcAddress("glBufferDataARB");
    glDeleteBuffersARB = (PFNGLDELETEBUFFERSARBPROC) wglGetProcAddress("glDeleteBuffersARB");
    
    glDrawElementsInstancedARB = (PFNGLDRAWELEMENTSINSTANCEDARBPROC) wglGetProcAddress("glDrawElementsInstancedARB");
    glVertexAttribDivisorARB = (PFNGLVERTEXATTRIBDIVISORARBPROC) wglGetProcAddress("glVertexAttribDivisorARB");
    glGetAttribLocationARB = (PFNGLGETATTRIBLOCATIONARBPROC) wglGetProcAddress("glGetAttribLocationARB");
    glVertexAttribPointerARB = (PFNGLVERTEXATTRIBPOINTERARBPROC) wglGetProcAddress("glVertexAttribPointerARB");
    glEnableVertexAttribArrayARB = (PFNGLENABLEVERTEXATTRIBARRAYARBPROC) wglGetProcAddress("glEnableVertexAttribArrayARB");
    glDisableVertexAttribArrayARB = (PFNGLDISABLEVERTEXATTRIBARRAYARBPROC) wglGetProcAddress("glDisableVertexAttribArrayARB");
#endif
"""

load_exts_linux = """
#ifdef GL_ARB_vertex_buffer_object
    glGenBuffersARB = (PFNGLGENBUFFERSARBPROC) glXGetProcAddress((const GLubyte *) "glGenBuffersARB");
    glBindBufferARB = (PFNGLBINDBUFFERARBPROC) glXGetProcAddress((const GLubyte *) "glBindBufferARB");
    glBufferDataARB = (PFNGLBUFFERDATAARBPROC) glXGetProcAddress((const GLubyte *) "glBufferDataARB");
    glDeleteBuffersARB = (PFNGLDELETEBUFFERSARBPROC) glXGetProcAddress((const GLubyte *) "glDeleteBuffersARB");
    
    glDrawElementsInstancedARB = (PFNGLDRAWELEMENTSINSTANCEDARBPROC) glXGetProcAddress((const GLubyte *) "glDrawElementsInstancedARB");
    glVertexAttribDivisorARB = (PFNGLVERTEXATTRIBDIVISORARBPROC) glXGetProcAddress((const GLubyte *) "glVertexAttribDivisorARB");
    glGetAttribLocationARB = (PFNGLGETATTRIBLOCATIONARBPROC) glXGetProcAddress((const GLubyte *) "glGetAttribLocationARB");
    glVertexAttribPointerARB = (PFNGLVERTEXATTRIBPOINTERARBPROC) glXGetProcAddress((const GLubyte *) "glVertexAttribPointerARB");
    glEnableVertexAttribArrayARB = (PFNGLENABLEVERTEXATTRIBARRAYARBPROC) glXGetProcAddress((const GLubyte *) "glEnableVertexAttribArrayARB");
    glDisableVertexAttribArrayARB = (PFNGLDISABLEVERTEXATTRIBARRAYARBPROC) glXGetProcAddress((const GLubyte *) "glDisableVertexAttribArrayARB");
#endif
"""

if "glDrawElementsInstancedARB = " not in content:
    content = re.sub(r'#ifdef GL_ARB_vertex_buffer_object\s+glGenBuffersARB = \(PFNGLGENBUFFERSARBPROC\) wglGetProcAddress\("glGenBuffersARB"\);\s+glBindBufferARB = \(PFNGLBINDBUFFERARBPROC\) wglGetProcAddress\("glBindBufferARB"\);\s+glBufferDataARB = \(PFNGLBUFFERDATAARBPROC\) wglGetProcAddress\("glBufferDataARB"\);\s+glDeleteBuffersARB = \(PFNGLDELETEBUFFERSARBPROC\) wglGetProcAddress\("glDeleteBuffersARB"\);\s+#endif', load_exts_win.strip(), content)
    content = re.sub(r'#ifdef GL_ARB_vertex_buffer_object\s+glGenBuffersARB = \(PFNGLGENBUFFERSARBPROC\) glXGetProcAddress\(\(const GLubyte \*\) "glGenBuffersARB"\);\s+glBindBufferARB = \(PFNGLBINDBUFFERARBPROC\) glXGetProcAddress\(\(const GLubyte \*\) "glBindBufferARB"\);\s+glBufferDataARB = \(PFNGLBUFFERDATAARBPROC\) glXGetProcAddress\(\(const GLubyte \*\) "glBufferDataARB"\);\s+glDeleteBuffersARB = \(PFNGLDELETEBUFFERSARBPROC\) glXGetProcAddress\(\(const GLubyte \*\) "glDeleteBuffersARB"\);\s+#endif', load_exts_linux.strip(), content)

content = content.replace("enableShaders = false; // Damn you, Intel", "")
content = content.replace("//loadShaderProgram(); // Damn you, Intel", "loadShaderProgram();")

vs = 'const char vertexProgramSource[1024] = "attribute vec4 instanceMat0; attribute vec4 instanceMat1; attribute vec4 instanceMat2; attribute vec4 instanceMat3; attribute vec4 instanceColor; void main(){ mat4 instanceMatrix = mat4(instanceMat0, instanceMat1, instanceMat2, instanceMat3); vec4 worldPos = instanceMatrix * gl_Vertex; gl_Position = gl_ProjectionMatrix * worldPos; mat3 m3 = mat3(instanceMatrix[0].xyz, instanceMatrix[1].xyz, instanceMatrix[2].xyz); vec3 normal = normalize(m3 * gl_Normal); gl_FrontColor = instanceColor*(vec4(0.7,0.7,0.7,1.0) + vec4(0.5,0.5,0.5,0.0)*max(dot(normal, vec3(0.0,-0.89,-0.45)),0.0)); }";'
if "instanceMat0" not in content:
    content = re.sub(r'const char vertexProgramSource\[.*?\] = .*?;', vs, content, count=1)

with open("/home/jerome/silis/third-party/GDS3D/gdsoglviewer/renderer.cpp", "w") as f:
    f.write(content)
