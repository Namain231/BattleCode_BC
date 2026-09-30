// msgauth.hpp -- authenticated, encrypted, round-stamped 64-bit sonar messages.
//
// Why: the current packMsg() uses a constant 12-bit header (0xB0D) and a plaintext round, and
// replays record every sonar word, so anyone can read our format and forge messages (e.g. MSG_CHOKE
// with p2 = 4095 blocks a cell for ~4000 rounds; MSG_GIANT/MSG_QUEEN can steer our queen logic).
//
// Layout (64 bits):
//   [63:40] tag     24-bit SipHash-2-4 MAC over (round, sender, type, dir, cipher)
//   [39:28] sender  12-bit dragon id (id mod 4096; used only as nonce / tie-break)
//   [27:25] type    3 bits (0..7)
//   [24:23] dir     2 bits: which ray this went out on (0..3), part of the nonce
//   [22:0]  cipher  23 data bits XOR a keystream from SipHash(round, sender, type, dir)
//
// The round is NOT transmitted.  It is mixed into the MAC and the keystream, and the receiver tries
// the only two rounds a message can belong to: a receiver with a higher id reads it the same round,
// a lower id the round after (game rules).  So a captured word replays for at most 2 rounds, and a
// forged word passes with probability ~2 / 2^24 per attempt.  Keep K0/K1 secret: never print them,
// never put them in an indicator string, and use a different pair per submission.
#pragma once
#include <cstdint>
#include <cstddef>

namespace msgauth {

// >>> REPLACE with your own random 128-bit secret before submitting <<<
constexpr uint64_t K0 = 0x9e3779b97f4a7c15ULL ^ 0x243f6a8885a308d3ULL;
constexpr uint64_t K1 = 0xb7e151628aed2a6bULL ^ 0x13198a2e03707344ULL;

static inline uint64_t rotl(uint64_t x, int b) { return (x << b) | (x >> (64 - b)); }

// Reference SipHash-2-4 (Aumasson & Bernstein).
static inline uint64_t siphash24(const uint8_t *in, size_t n, uint64_t k0, uint64_t k1) {
  uint64_t v0 = 0x736f6d6570736575ULL ^ k0, v1 = 0x646f72616e646f6dULL ^ k1;
  uint64_t v2 = 0x6c7967656e657261ULL ^ k0, v3 = 0x7465646279746573ULL ^ k1;
  auto round = [&]() {
    v0 += v1; v1 = rotl(v1, 13); v1 ^= v0; v0 = rotl(v0, 32);
    v2 += v3; v3 = rotl(v3, 16); v3 ^= v2;
    v0 += v3; v3 = rotl(v3, 21); v3 ^= v0;
    v2 += v1; v1 = rotl(v1, 17); v1 ^= v2; v2 = rotl(v2, 32);
  };
  const uint8_t *end = in + (n - (n % 8));
  for (; in != end; in += 8) {
    uint64_t m = 0;
    for (int i = 0; i < 8; i++) m |= (uint64_t)in[i] << (8 * i);
    v3 ^= m; round(); round(); v0 ^= m;
  }
  uint64_t b = (uint64_t)n << 56;
  for (size_t i = 0; i < n % 8; i++) b |= (uint64_t)in[i] << (8 * i);
  v3 ^= b; round(); round(); v0 ^= b;
  v2 ^= 0xff; round(); round(); round(); round();
  return v0 ^ v1 ^ v2 ^ v3;
}

static inline uint64_t sip64(uint64_t w, uint64_t k0, uint64_t k1) {
  uint8_t b[8];
  for (int i = 0; i < 8; i++) b[i] = (uint8_t)(w >> (8 * i));
  return siphash24(b, 8, k0, k1);
}

enum Type { T_INTENT = 0, T_FOUNTAIN, T_GIANT, T_QUEEN, T_CHOKE, T_CLAIM, T_HANDOFF, T_LANE };

struct Msg {
  int type = 0, dir = 0, sender = 0;
  uint32_t data = 0;  // 23 bits
};

static inline uint64_t header(int round, const Msg &m) {  // everything except the cipher
  return ((uint64_t)(round & 0xFFFFFF) << 40) | ((uint64_t)(m.sender & 4095) << 28) |
         ((uint64_t)(m.type & 7) << 25) | ((uint64_t)(m.dir & 3) << 23);
}
static inline uint32_t keystream(uint64_t hdr) {
  return (uint32_t)(sip64(hdr, K0 ^ 0x5bd1e9955bd1e995ULL, K1) & 0x7FFFFF);
}
static inline uint32_t tagOf(uint64_t hdr, uint32_t cipher) {
  return (uint32_t)(sip64(hdr | cipher, K0, K1 ^ 0xa5a5a5a5a5a5a5a5ULL) >> 40);
}

static inline uint64_t seal(const Msg &m, int round) {
  uint64_t hdr = header(round, m);
  uint32_t c = (m.data & 0x7FFFFF) ^ keystream(hdr);
  uint64_t tag = tagOf(hdr, c);
  return (tag << 40) | (hdr & 0x000000FFFFFFFFFFULL) | c;
}

// Accepts only if the tag verifies for `now` or `now-1`.  On success fills `out`.
static inline bool open(uint64_t v, int now, Msg &out) {
  uint32_t tag = (uint32_t)(v >> 40);
  Msg m;
  m.sender = (int)((v >> 28) & 4095);
  m.type = (int)((v >> 25) & 7);
  m.dir = (int)((v >> 23) & 3);
  uint32_t c = (uint32_t)(v & 0x7FFFFF);
  for (int r = now; r >= now - 1 && r >= 0; r--) {
    uint64_t hdr = header(r, m);
    if (tagOf(hdr, c) == tag) {
      m.data = c ^ keystream(hdr);
      out = m;
      return true;
    }
  }
  return false;
}

// Optional: drop exact duplicates seen this round or last (cheap replay/echo suppression).
struct Dedup {
  uint64_t seen[64]; int round[64]; int n = 0;
  bool fresh(uint64_t v, int now) {
    for (int i = 0; i < n; i++)
      if (seen[i] == v && round[i] >= now - 1) return false;
    if (n < 64) { seen[n] = v; round[n] = now; n++; }
    else { for (int i = 1; i < 64; i++) { seen[i-1] = seen[i]; round[i-1] = round[i]; } seen[63] = v; round[63] = now; }
    return true;
  }
};

}  // namespace msgauth
