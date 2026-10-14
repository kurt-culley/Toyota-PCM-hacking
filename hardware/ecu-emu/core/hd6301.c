// HD6301 CPU core: see hd6301.h. Semantics follow analysis/emu/cpu.py line for line.

#include "hd6301.h"

#define F_H 0x20
#define F_I 0x10
#define F_N 0x08
#define F_Z 0x04
#define F_V 0x02
#define F_C 0x01
#define CC_FIXED 0xC0

#define CC (c->cc)
#define SETF(m, cond) (CC = (cond) ? (uint8_t)(CC | (m)) : (uint8_t)(CC & ~(m)))
#define NXV ((!(CC & F_N)) != (!(CC & F_V)))
#define D ((uint16_t)((c->a << 8) | c->b))
#define SET_D(v) do { uint16_t _v = (v); c->a = (uint8_t)(_v >> 8); c->b = (uint8_t)_v; } while (0)

#define RD(a) (c->read(c->ctx, (uint16_t)(a)))
#define WR(a, v) (c->write(c->ctx, (uint16_t)(a), (uint8_t)(v)))
#define RD16(a) ((uint16_t)((RD(a) << 8) | RD((uint16_t)((a) + 1))))
#define WR16(a, v) do { uint16_t _a = (a), _w = (v); WR(_a, _w >> 8); WR((uint16_t)(_a + 1), _w); } while (0)
#define FETCH() (RD(c->pc++))
#define FETCH16() fetch16(c)
#define PUSH(v) do { WR(c->s, (v)); c->s--; } while (0)
#define PULL() (c->s++, RD(c->s))
#define PUSH16(v) do { uint16_t _p = (v); PUSH(_p & 0xFF); PUSH(_p >> 8); } while (0)
#define PULL16() pull16(c)

static inline uint16_t fetch16(hd6301_t *c) {
    uint8_t hi = FETCH();
    return (uint16_t)((hi << 8) | FETCH());
}

static inline uint16_t pull16(hd6301_t *c) {
    uint8_t hi = PULL();
    return (uint16_t)((hi << 8) | PULL());
}

static inline void nz8(hd6301_t *c, unsigned r) {
    SETF(F_N, r & 0x80);
    SETF(F_Z, (r & 0xFF) == 0);
}

static inline void nz16(hd6301_t *c, unsigned r) {
    SETF(F_N, r & 0x8000);
    SETF(F_Z, (r & 0xFFFF) == 0);
}

static inline uint8_t add8(hd6301_t *c, unsigned a, unsigned b, unsigned carry, int half) {
    unsigned r = a + b + carry;
    if (half) SETF(F_H, (a ^ b ^ r) & 0x10);
    nz8(c, r);
    SETF(F_V, (~(a ^ b) & (a ^ r)) & 0x80);
    SETF(F_C, r & 0x100);
    return (uint8_t)r;
}

static inline uint8_t sub8(hd6301_t *c, unsigned a, unsigned b, unsigned borrow) {
    unsigned r = a - b - borrow;
    nz8(c, r);
    SETF(F_V, ((a ^ b) & (a ^ r)) & 0x80);
    SETF(F_C, r & 0x100);
    return (uint8_t)r;
}

static inline uint16_t add16(hd6301_t *c, unsigned a, unsigned b) {
    unsigned r = a + b;
    nz16(c, r);
    SETF(F_V, (~(a ^ b) & (a ^ r)) & 0x8000);
    SETF(F_C, r & 0x10000);
    return (uint16_t)r;
}

static inline uint16_t sub16(hd6301_t *c, unsigned a, unsigned b) {
    unsigned r = a - b;
    nz16(c, r);
    SETF(F_V, ((a ^ b) & (a ^ r)) & 0x8000);
    SETF(F_C, r & 0x10000);
    return (uint16_t)r;
}

static inline uint8_t logic(hd6301_t *c, unsigned r) {
    nz8(c, r);
    CC &= ~F_V;
    return (uint8_t)r;
}

static inline void nxc(hd6301_t *c) { SETF(F_V, (!(CC & F_N)) != (!(CC & F_C))); }

// Unary read-modify-write operations (memory and accumulator forms).
static inline uint8_t u_neg(hd6301_t *c, uint8_t v) { return sub8(c, 0, v, 0); }
static inline uint8_t u_com(hd6301_t *c, uint8_t v) { uint8_t r = logic(c, (uint8_t)~v); CC |= F_C; return r; }
static inline uint8_t u_lsr(hd6301_t *c, uint8_t v) { SETF(F_C, v & 1); uint8_t r = v >> 1; nz8(c, r); nxc(c); return r; }
static inline uint8_t u_ror(hd6301_t *c, uint8_t v) {
    unsigned cin = CC & F_C;
    SETF(F_C, v & 1);
    uint8_t r = (uint8_t)((v >> 1) | (cin << 7));
    nz8(c, r);
    nxc(c);
    return r;
}
static inline uint8_t u_asr(hd6301_t *c, uint8_t v) { SETF(F_C, v & 1); uint8_t r = (uint8_t)((v >> 1) | (v & 0x80)); nz8(c, r); nxc(c); return r; }
static inline uint8_t u_asl(hd6301_t *c, uint8_t v) { SETF(F_C, v & 0x80); uint8_t r = (uint8_t)(v << 1); nz8(c, r); nxc(c); return r; }
static inline uint8_t u_rol(hd6301_t *c, uint8_t v) {
    unsigned cin = CC & F_C;
    SETF(F_C, v & 0x80);
    uint8_t r = (uint8_t)((v << 1) | cin);
    nz8(c, r);
    nxc(c);
    return r;
}
static inline uint8_t u_dec(hd6301_t *c, uint8_t v) { uint8_t r = (uint8_t)(v - 1); nz8(c, r); SETF(F_V, v == 0x80); return r; }
static inline uint8_t u_inc(hd6301_t *c, uint8_t v) { uint8_t r = (uint8_t)(v + 1); nz8(c, r); SETF(F_V, v == 0x7F); return r; }
static inline uint8_t u_tst(hd6301_t *c, uint8_t v) { (void)logic(c, v); CC &= ~F_C; return v; }
static inline uint8_t u_clr(hd6301_t *c, uint8_t v) { (void)v; CC = (uint8_t)((CC & ~(F_N | F_V | F_C)) | F_Z); return 0; }

static void op_lsrd(hd6301_t *c) {
    uint16_t d = D;
    SETF(F_C, d & 1);
    d >>= 1;
    nz16(c, d);
    nxc(c);
    SET_D(d);
}

static void op_asld(hd6301_t *c) {
    uint16_t d = D;
    SETF(F_C, d & 0x8000);
    d = (uint16_t)(d << 1);
    nz16(c, d);
    nxc(c);
    SET_D(d);
}

static void op_daa(hd6301_t *c) {
    unsigned a = c->a, cf = 0, msn = a & 0xF0, lsn = a & 0x0F;
    if (lsn > 9 || (CC & F_H)) cf |= 0x06;
    if ((msn > 0x80 && lsn > 9) || msn > 0x90 || (CC & F_C)) cf |= 0x60;
    unsigned t = a + cf;
    nz8(c, t);
    CC &= ~F_V;  // the handbook contradicts itself on V (STATUS conflicts log); MAME clears it
    if (t & 0x100) CC |= F_C;
    c->a = (uint8_t)t;
}

static void stack_all(hd6301_t *c) {
    PUSH16(c->pc);
    PUSH16(c->x);
    PUSH(c->a);
    PUSH(c->b);
    PUSH(c->cc);
}

static int interrupt(hd6301_t *c, uint16_t vector) {
    int cycles = c->waiting ? 4 : 12;
    if (!c->waiting) stack_all(c);
    c->waiting = c->sleeping = 0;
    CC |= F_I;
    c->pc = RD16(vector);
    return cycles;
}

void hd6301_init(hd6301_t *c, hd6301_read_fn rd, hd6301_write_fn wr, void *ctx) {
    *c = (hd6301_t){0};
    c->read = rd;
    c->write = wr;
    c->ctx = ctx;
    c->cc = CC_FIXED | F_I;
}

void hd6301_reset(hd6301_t *c) {
    c->pc = RD16(HD6301_VEC_RES);
    c->cc = CC_FIXED | F_I;
    c->waiting = c->sleeping = c->irq_inhibit = 0;
}

int hd6301_irq(hd6301_t *c, uint16_t vector) {
    if ((CC & F_I) || c->irq_inhibit) {
        c->sleeping = 0;
        return 0;
    }
    c->cycles += (uint64_t)interrupt(c, vector);
    return 1;
}

void hd6301_nmi(hd6301_t *c) { c->cycles += (uint64_t)interrupt(c, HD6301_VEC_NMI); }

int hd6301_step(hd6301_t *c) {
    if (c->waiting || c->sleeping) return 0;
    c->irq_inhibit = 0;
    uint8_t op = FETCH();
    int n;
    switch (op) {
#include "hd6301_ops.inc"
    default:  // undefined opcode: TRAP
        c->pc--;
        n = interrupt(c, HD6301_VEC_TRAP);
        break;
    }
    c->cycles += (uint64_t)n;
    return n;
}
