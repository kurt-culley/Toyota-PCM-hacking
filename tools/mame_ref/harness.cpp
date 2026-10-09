// Single-instruction reference runner around MAME's HD6301 instruction handlers.
//
// Built by tools/setup_mame_ref.sh, which downloads MAME's m6800 core at a
// pinned tag and extracts the fragments included below. MAME's handlers are
// used unchanged; this file only supplies the minimal device class they need
// and a flat 64 KB memory.
//
//   hd6301ref SEED CASES_PER_OPCODE
//
// For every opcode, CASES_PER_OPCODE random cases are run. Initial memory and
// registers come from mix(case_seed, addr), which tests/test_emu_cpu.py
// reproduces exactly. One line per case (hex):
//   op case_seed pc s x d cc -> pc s x d cc cycles nwrites addr=val ...
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int16_t s16;

union PAIR {
	struct { u8 l, h, h2, h3; } b;
	struct { u16 l, h; } w;
	u32 d;
};

static u8 g_mem[0x10000];
static std::vector<std::pair<u16, u8>> g_writes;

struct Space {
	u8 read_byte(u32 a) { return g_mem[a & 0xffff]; }
	void write_byte(u32 a, u8 v) { g_mem[a & 0xffff] = v; g_writes.push_back({u16(a & 0xffff), v}); }
};

class m6800_cpu_device {
public:
	typedef void (m6800_cpu_device::*op_func)();
	enum { M6800_WAI = 8, M6800_SLP = 0x10 };
	PAIR m_ppc, m_pc, m_s, m_x, m_d, m_ea;
	u8 m_cc = 0;
	u8 m_wai_state = 0;
	Space m_program, m_cprogram, m_copcodes;
	static const u8 flags8i[256], flags8d[256];

	u32 RM16(u32 a) { return (m_program.read_byte(a) << 8) | m_program.read_byte((a + 1) & 0xffff); }
	void WM16(u32 a, PAIR *p) { m_program.write_byte(a, p->b.h); m_program.write_byte((a + 1) & 0xffff, p->b.l); }
	void logerror(const char *, ...) {}
	// In MAME, TAP and CLI run the next instruction before checking IRQs (the
	// one-instruction interrupt shadow). That is interrupt timing, not part of
	// a single-instruction comparison, so these are no-ops here.
	void execute_one() {}
	void check_irq_lines() {}
	void eat_cycles() {}
	void take_trap();
#include "ops_decl.inc"
};

#include "macros.inc"
#include "6800ops.hxx"

// MAME's enter_interrupt() for a CPU that is not in WAI (m6800.cpp).
void m6800_cpu_device::take_trap() {
	PUSHWORD(pPC); PUSHWORD(pX); PUSHBYTE(A); PUSHBYTE(B); PUSHBYTE(CC);
	SEI;
	PCD = RM16(0xffee);
}

#define m6801_cpu_device m6800_cpu_device
#include "insn.inc"
#define XX 0
#include "cycles.inc"
#undef XX

// Shared with the Python test: a 32-bit integer hash.
static u32 mix(u32 seed, u32 addr) {
	u32 h = seed * 0x9E3779B1u + addr * 0x85EBCA77u;
	h ^= h >> 15; h *= 0x2C1B3C6Du;
	h ^= h >> 12; h *= 0x297A2D39u;
	h ^= h >> 15;
	return h;
}

int main(int argc, char **argv) {
	if (argc != 3) { fprintf(stderr, "usage: hd6301ref SEED CASES_PER_OPCODE\n"); return 2; }
	u32 seed = strtoul(argv[1], nullptr, 0);
	int n = atoi(argv[2]);
	m6800_cpu_device cpu;
	for (int op = 0; op < 256; op++) {
		for (int i = 0; i < n; i++) {
			u32 cs = mix(seed, (u32(op) << 16) | u32(i));
			for (u32 a = 0; a < 0x10000; a++) g_mem[a] = u8(mix(cs, a));
			cpu.m_pc.d = mix(cs, 0x10000) & 0xffff;
			cpu.m_s.d = mix(cs, 0x10001) & 0xffff;
			cpu.m_x.d = mix(cs, 0x10002) & 0xffff;
			cpu.m_d.d = mix(cs, 0x10003) & 0xffff;
			cpu.m_cc = u8(mix(cs, 0x10004)) | 0xc0;
			cpu.m_wai_state = 0;
			g_mem[cpu.m_pc.w.l] = u8(op);
			printf("%02x %08x %04x %04x %04x %04x %02x ->", op, cs, cpu.m_pc.w.l, cpu.m_s.w.l, cpu.m_x.w.l,
				cpu.m_d.w.l, cpu.m_cc);
			g_writes.clear();
			cpu.m_ppc = cpu.m_pc;
			u8 opcode = g_mem[cpu.m_pc.w.l];
			cpu.m_pc.w.l++;
			(cpu.*hd63701_insn_tbl[opcode])();
			printf(" %04x %04x %04x %04x %02x %d %zu", cpu.m_pc.w.l, cpu.m_s.w.l, cpu.m_x.w.l, cpu.m_d.w.l, cpu.m_cc,
				cycles_tbl[opcode], g_writes.size());
			for (auto &w : g_writes) printf(" %04x=%02x", w.first, w.second);
			printf("\n");
		}
	}
	return 0;
}
