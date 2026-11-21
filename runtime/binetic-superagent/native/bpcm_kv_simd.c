#define _GNU_SOURCE
#include <arm_neon.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static inline uint64_t now_ns(void) {
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

// Warm-up-sensitive SIMD KV byte-slot fold: accumulate XOR of two rows and
// commit the per-row fold into a rolling checksum.
static inline uint64_t kv_fold_neon(const uint8_t *a, const uint8_t *b, size_t n) {
    uint8x16_t acc0 = vdupq_n_u8(0), acc1 = vdupq_n_u8(0);
    size_t i = 0;
    for (; i + 32 <= n; i += 32) {
        acc0 = veorq_u8(acc0, veorq_u8(vld1q_u8(a + i), vld1q_u8(b + i)));
        acc1 = veorq_u8(acc1, veorq_u8(vld1q_u8(a + i + 16), vld1q_u8(b + i + 16)));
    }
    uint64x2_t wide = vreinterpretq_u64_u8(veorq_u8(acc0, acc1));
    uint64_t out = vgetq_lane_u64(wide, 0) ^ vgetq_lane_u64(wide, 1);
    for (; i < n; ++i) out ^= ((uint64_t)(a[i] ^ b[i])) << ((i & 7) * 8);
    return out;
}

int main(int argc, char **argv) {
    size_t rows = argc > 1 ? strtoull(argv[1], NULL, 10) : 100000;
    size_t bytes = argc > 2 ? strtoull(argv[2], NULL, 10) : 512;
    uint32_t rounds = argc > 3 ? (uint32_t)strtoul(argv[3], NULL, 10) : 3;
    uint8_t *a = malloc(bytes), *b = malloc(bytes);
    if (!a || !b) return 1;
    uint32_t x = 0x9E3779B9u;
    for (size_t i = 0; i < bytes; ++i) { x ^= x << 13; x ^= x >> 17; x ^= x << 5; a[i] = (uint8_t)x; b[i] = (uint8_t)(x >> 7); }
    uint64_t best = UINT64_MAX, check = 0;
    for (uint32_t r = 0; r < rounds; ++r) {
        uint64_t t0 = now_ns();
        uint64_t fold = 0;
        for (size_t row = 0; row < rows; ++row) {
            fold = (fold << 1) ^ kv_fold_neon(a, b + (row & 63), bytes) ^ (uint64_t)row;
        }
        uint64_t dt = now_ns() - t0; if (dt < best) best = dt;
        check ^= fold;
    }
    double mib = (double)rows * bytes * 2 / (1024 * 1024);
    printf("{\"kind\":\"native_kv_fold\",\"rows\":%zu,\"bytes_per_row\":%zu,\"best_ms\":%.6f,\"MiB_per_s\":%.1f,\"check\":%" PRIu64 "}\n",
           rows, bytes, best / 1e6, mib / (best / 1e9), check);
    free(a); free(b); return 0;
}
