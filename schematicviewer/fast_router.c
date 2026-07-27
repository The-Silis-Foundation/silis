#include <stdlib.h>
#include <math.h>

// Struct for a segment
typedef struct {
    int uid;
    int is_h;
    int x1, x2, y1, y2;
    int x_min, x_max, y_min, y_max;
} Segment;

// Struct for a keepout rectangle
typedef struct {
    int left, top, right, bottom;
} Rect;

static inline int abs_val(int x) { return x < 0 ? -x : x; }
static inline int min_val(int a, int b) { return a < b ? a : b; }
static inline int max_val(int a, int b) { return a > b ? a : b; }

int is_keepout_collision_generic(int x1, int y1, int x2, int y2, int has_ignore, int ig_x, int ig_y, int halo, Rect* rects, int num_rects) {
    int sx1 = min_val(x1, x2);
    int sx2 = max_val(x1, x2);
    int sy1 = min_val(y1, y2);
    int sy2 = max_val(y1, y2);
    
    for (int i = 0; i < num_rects; i++) {
        if (has_ignore && (rects[i].left <= ig_x && ig_x <= rects[i].right) && (rects[i].top <= ig_y && ig_y <= rects[i].bottom)) {
            continue;
        }
        
        int bx1 = rects[i].left - halo;
        int by1 = rects[i].top - halo;
        int bx2 = rects[i].right + halo;
        int by2 = rects[i].bottom + halo;
        
        if (!(sx2 < bx1 || sx1 > bx2 || sy2 < by1 || sy1 > by2)) {
            return 1;
        }
    }
    return 0;
}

int check_keepout(int tx, int y_min, int y_max, Rect* rects, int num_rects) {
    for (int i = 0; i < num_rects; i++) {
        if (y_min <= rects[i].bottom + 15 && y_max >= rects[i].top - 15) {
            if (tx > rects[i].left - 15 && tx < rects[i].right + 15) {
                return 1;
            }
        }
    }
    return 0;
}

int check_keepout_h(int ty, int x_min, int x_max, Rect* rects, int num_rects) {
    for (int i = 0; i < num_rects; i++) {
        if (x_min <= rects[i].right + 15 && x_max >= rects[i].left - 15) {
            if (ty > rects[i].top - 15 && ty < rects[i].bottom + 15) {
                return 1;
            }
        }
    }
    return 0;
}

int space_out_channels_v(Segment* segs, int num_segs, Rect* rects, int num_rects) {
    int failure = 0;
    for (int iter = 0; iter < 3; iter++) {
        for (int i = 0; i < num_segs; i++) {
            for (int j = i + 1; j < num_segs; j++) {
                if (segs[i].uid == segs[j].uid) continue;
                
                int y1_min = segs[i].y_min;
                int y1_max = segs[i].y_max;
                int y2_min = segs[j].y_min;
                int y2_max = segs[j].y_max;
                
                if (abs_val(segs[i].x1 - segs[j].x1) < 6) {
                    if (max_val(y1_min, y2_min) < min_val(y1_max, y2_max)) {
                        int old_x = segs[j].x1;
                        int safe_x = old_x;
                        
                        for (int step = 1; step < 200; step++) {
                            int shift = (step % 2 != 0) ? ((step / 2) + 1) * 16 : -(step / 2) * 16;
                            int tx = old_x + shift;
                            
                            if (!check_keepout(tx, y2_min, y2_max, rects, num_rects)) {
                                if (abs_val(tx - segs[i].x1) >= 6) {
                                    safe_x = tx;
                                    break;
                                }
                            }
                        }
                        if (safe_x == old_x) failure = 1;
                        segs[j].x1 = safe_x;
                        segs[j].x2 = safe_x;
                    }
                }
            }
        }
    }
    return failure;
}

int space_out_channels_h(Segment* segs, int num_segs, Rect* rects, int num_rects) {
    int failure = 0;
    for (int iter = 0; iter < 3; iter++) {
        for (int i = 0; i < num_segs; i++) {
            for (int j = i + 1; j < num_segs; j++) {
                if (segs[i].uid == segs[j].uid) continue;
                
                int x1_min = segs[i].x_min;
                int x1_max = segs[i].x_max;
                int x2_min = segs[j].x_min;
                int x2_max = segs[j].x_max;
                
                if (abs_val(segs[i].y1 - segs[j].y1) < 6) {
                    if (max_val(x1_min, x2_min) < min_val(x1_max, x2_max)) {
                        int old_y = segs[j].y1;
                        int safe_y = old_y;
                        
                        for (int step = 1; step < 200; step++) {
                            int shift = (step % 2 != 0) ? ((step / 2) + 1) * 20 : -(step / 2) * 20;
                            int ty = old_y + shift;
                            
                            if (!check_keepout_h(ty, x2_min, x2_max, rects, num_rects)) {
                                if (abs_val(ty - segs[i].y1) >= 6) {
                                    safe_y = ty;
                                    break;
                                }
                            }
                        }
                        if (safe_y == old_y) failure = 1;
                        segs[j].y1 = safe_y;
                        segs[j].y2 = safe_y;
                    }
                }
            }
        }
    }
    return failure;
}
