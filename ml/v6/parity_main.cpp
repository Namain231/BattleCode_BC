// Reads N states (uint8 planes 19*225 + float scalars 6) from argv[1], writes N*7 float logits to argv[2].
#include <cstdio>
#include <vector>
#include "policy_nn_v6.hpp"
int main(int argc, char** argv) {
    if (argc < 3) return 2;
    FILE* f = fopen(argv[1], "rb"); if (!f) return 3;
    int n; if (fread(&n, 4, 1, f) != 1) return 4;
    std::vector<unsigned char> P((size_t)n * nn::NPL * 225); std::vector<float> S((size_t)n * nn::NSC), L((size_t)n * nn::NOUT);
    if (fread(P.data(), 1, P.size(), f) != P.size() || fread(S.data(), 4, S.size(), f) != S.size()) return 5;
    fclose(f);
    for (int i = 0; i < n; i++) nn::forward(&P[(size_t)i * nn::NPL * 225], &S[(size_t)i * nn::NSC], &L[(size_t)i * nn::NOUT]);
    FILE* g = fopen(argv[2], "wb"); fwrite(L.data(), 4, L.size(), g); fclose(g); return 0;
}
