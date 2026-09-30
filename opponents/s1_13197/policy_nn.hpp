// Move-imitation network (ml/train.py Policy), float forward pass. Weights: policy_weights.hpp (ml/export_cpp.py).
// Input: 16 uint8 planes 15x15 (egocentric, facing up; see ml/build_dataset.py) + 3 scalars, broadcast as 3 extra
// input planes. Output: logits for forward/right/back/left/split/other.
// Activations live in zero-padded buffers so the 3x3 convolutions need no bounds checks (the judge prices every
// instruction: the checked version cost ~44M points per call).
#pragma once
#include "policy_weights.hpp"

namespace nn {
constexpr int S = 15, P = 7, C = 32, HID = 64, NIN = 19, NOUT = 6;
constexpr int SP = S + 2, PP = P + 2;   // padded sizes

static float in_[NIN][SP][SP], a1[C][S][S], p1[C][PP][PP], a2[C][PP][PP], a3[C][P][P], h[HID];

// y[oc][v][u] = b[oc] + sum_ic sum_ky,kx w[oc][ic][ky][kx] * xpad[ic][v+ky][u+kx]
template <int IC, int N, int NPAD, int YSTRIDE>
static void conv3(const float* xpad, float* y, int yoff, const float* w, const float* b) {
    for (int oc = 0; oc < C; oc++) {
        float* yo = y + oc * YSTRIDE * YSTRIDE;
        for (int v = 0; v < N; v++)
            for (int u = 0; u < N; u++) yo[(v + yoff) * YSTRIDE + u + yoff] = b[oc];
        for (int ic = 0; ic < IC; ic++) {
            const float* wk = w + (oc * IC + ic) * 9;
            const float w0 = wk[0], w1 = wk[1], w2 = wk[2], w3 = wk[3], w4 = wk[4], w5 = wk[5], w6 = wk[6], w7 = wk[7], w8 = wk[8];
            const float* xc = xpad + ic * NPAD * NPAD;
            for (int v = 0; v < N; v++) {
                const float* r0 = xc + v * NPAD;
                const float* r1 = r0 + NPAD;
                const float* r2 = r1 + NPAD;
                float* yr = yo + (v + yoff) * YSTRIDE + yoff;
                for (int u = 0; u < N; u++)
                    yr[u] += w0 * r0[u] + w1 * r0[u + 1] + w2 * r0[u + 2] + w3 * r1[u] + w4 * r1[u + 1] + w5 * r1[u + 2] +
                             w6 * r2[u] + w7 * r2[u + 1] + w8 * r2[u + 2];
            }
        }
    }
}

// planes: 16*15*15 uint8 (plane-major), scal: 3 floats
static void forward(const unsigned char* planes, const float* scal, float* logits) {
    for (int c = 0; c < NIN; c++)
        for (int v = 0; v < S; v++)
            for (int u = 0; u < S; u++)
                in_[c][v + 1][u + 1] = c < 16 ? planes[(c * S + v) * S + u] * (1.0f / 255.0f) : scal[c - 16];
    conv3<NIN, S, SP, S>(&in_[0][0][0], &a1[0][0][0], 0, NN_C1_WEIGHT, NN_C1_BIAS);
    auto r = [](float x) { return x > 0 ? x : 0.0f; };
    // relu(conv1) then 2x2 average pooling (row/column 14 dropped, as in avg_pool2d), into a padded buffer
    for (int c = 0; c < C; c++)
        for (int v = 0; v < P; v++)
            for (int u = 0; u < P; u++)
                p1[c][v + 1][u + 1] = 0.25f * (r(a1[c][2 * v][2 * u]) + r(a1[c][2 * v][2 * u + 1]) +
                                               r(a1[c][2 * v + 1][2 * u]) + r(a1[c][2 * v + 1][2 * u + 1]));
    conv3<C, P, PP, PP>(&p1[0][0][0], &a2[0][0][0], 1, NN_C2_WEIGHT, NN_C2_BIAS);
    for (int c = 0; c < C; c++)
        for (int v = 1; v <= P; v++)
            for (int u = 1; u <= P; u++) a2[c][v][u] = r(a2[c][v][u]);
    conv3<C, P, PP, P>(&a2[0][0][0], &a3[0][0][0], 0, NN_C3_WEIGHT, NN_C3_BIAS);
    for (int c = 0; c < C; c++)
        for (int v = 0; v < P; v++)
            for (int u = 0; u < P; u++) a3[c][v][u] = r(a3[c][v][u] + a2[c][v + 1][u + 1]);
    const float* x = &a3[0][0][0];
    for (int j = 0; j < HID; j++) {
        float s0 = NN_FC_BIAS[j], s1 = 0, s2 = 0, s3 = 0;
        const float* w = NN_FC_WEIGHT + j * C * P * P;
        for (int k = 0; k < C * P * P; k += 4) {   // 1568 = 4 * 392
            s0 += w[k] * x[k]; s1 += w[k + 1] * x[k + 1]; s2 += w[k + 2] * x[k + 2]; s3 += w[k + 3] * x[k + 3];
        }
        h[j] = r(s0 + s1 + s2 + s3);
    }
    for (int o = 0; o < NOUT; o++) {
        float s = NN_OUT_BIAS[o];
        const float* w = NN_OUT_WEIGHT + o * (HID + 3);
        for (int k = 0; k < HID; k++) s += w[k] * h[k];
        for (int k = 0; k < 3; k++) s += w[HID + k] * scal[k];
        logits[o] = s;
    }
}
}  // namespace nn
