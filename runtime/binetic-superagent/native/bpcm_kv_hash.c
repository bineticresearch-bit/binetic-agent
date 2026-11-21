#define _GNU_SOURCE
#include <arm_acle.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static inline uint64_t now_ns(void) {
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

static inline uint32_t crc32c_mem(uint32_t crc, const uint8_t *p, size_t n) {
    for (size_t i = 0; i < n; ++i) crc = __crc32cb(crc, p[i]);
    return crc;
}

int main(int argc, char **argv) {
    size_t rows = argc > 1 ? strtoull(argv[1], NULL, 10) : 100000;
    size_t bytes = argc > 2 ? strtoull(argv[2], NULL, 10) : 512;
    uint32_t rounds = argc > 3 ? (uint32_t)strtoul(argv[3], NULL, 10) : 3;
    uint8_t *buf = malloc(bytes);
    if (!buf) return 1;
    uint32_t x = 0x9E3779B9u;
    for (size_t i = 0; i < bytes; ++i) { x ^= x << 13; x ^= x >> 17; x ^= x << 5; buf[i] = (uint8_t)x; }
    uint64_t best = UINT64_MAX, check = 0;
    for (uint32_t r = 0; r < rounds; ++r) {
        uint64_t t0 = now_ns();
        uint32_t crc = 0;
        for (size_t row = 0; row < rows; ++row) crc = crc32c_mem(crc, buf, bytes);
        uint64_t dt = now_ns() - t0; if (dt < best) best = dt;
        check ^= crc;
    }
    double mib = (double)rows * bytes / (1024 * 1024);
    printf("{\"kind\":\"native_kv_crc32c\",\"rows\":%zu,\"bytes_per_row\":%zu,\"best_ms\":%.6f,\"MiB_per_s\":%.1f,\"check\":%" PRIu64 "}\n",
           rows, bytes, best / 1e6, mib / (best / 1e9), check);
    free(buf); return 0;
}
