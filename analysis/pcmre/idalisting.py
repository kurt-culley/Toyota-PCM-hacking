"""Import labels, comments and the code/data split from an IDA 4.9 ``.asm`` listing.

The legacy listings in this repo (e.g. ``TOYOTA Bluetop PCM/cap.asm``) carry no
addresses. They are recovered by walking the listing in step with the ROM
image: each instruction line is decoded from the real bytes (and its mnemonic
cross-checked against the listing), each ``db``/``dw``/``ds`` line advances by
its data size. Any disagreement raises ``ListingMismatch`` so a bad import can
never pass silently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .hd6301 import decode, normalise_mnemonic


class ListingMismatch(ValueError):
    pass


@dataclass
class Item:
    addr: int
    size: int
    kind: str  # "code" | "byte" | "word"
    ida_text: str  # statement as written by IDA (no label, no comment)
    comment: list[str] = field(default_factory=list)  # trailing / continuation comments
    pre: list[str] = field(default_factory=list)  # block comments shown above
    values: list[str] = field(default_factory=list)  # db/dw operand list as written


@dataclass
class Listing:
    ram_labels: dict[int, str]  # zero-page/register names from the RegRAM segment
    labels: dict[int, list[str]]  # ROM address -> label(s)
    items: list[Item]
    org: int

    def item_at(self) -> dict[int, Item]:
        return {it.addr: it for it in self.items}


_LABEL = re.compile(r"^([A-Za-z_.$?@][\w.$?@]*):")


def _split_comment(line: str) -> tuple[str, str | None]:
    """Split at the first ';' that is not inside a quoted character literal."""
    q = None
    for i, ch in enumerate(line):
        if q:
            if ch == q:
                q = None
        elif ch in "'\"":
            q = ch
        elif ch == ";":
            return line[:i], line[i + 1 :].strip()
    return line, None


def _count_values(operands: str) -> list[str]:
    vals = [v.strip() for v in operands.split(",")]
    return [v for v in vals if v]


def parse(asm_path: Path, rom: bytes) -> Listing:
    text = asm_path.read_bytes().decode("latin-1").splitlines()
    ram_labels: dict[int, str] = {}
    labels: dict[int, list[str]] = {}
    items: list[Item] = []
    pending_pre: list[str] = []
    pending_labels: list[str] = []
    in_rom = False
    addr = 0  # RegRAM segment starts at 0
    org = None

    for lineno, line in enumerate(text, 1):
        body, comment = _split_comment(line)
        stripped = body.strip()

        if not stripped:
            if comment is None:
                continue
            # Pure comment line: indented ones continue the previous statement's
            # comment; column-0 ones are block comments for the next statement.
            if line[:1] in " \t" and items and in_rom and not pending_labels:
                items[-1].comment.append(comment)
            elif in_rom:
                pending_pre.append(comment)
            continue

        m = _LABEL.match(stripped)
        label = None
        if m:
            label = m.group(1)
            stripped = stripped[m.end() :].strip()

        parts = stripped.split(None, 1)
        op = parts[0].lower() if parts else ""
        args = parts[1].strip() if len(parts) > 1 else ""
        if args.startswith("="):
            continue  # IDA stack-frame equate (e.g. "arg_FC = $FE"), not ROM content

        if not in_rom:
            if op == "org":
                in_rom = True
                org = addr = int(args.lstrip("$"), 16)
                continue
            if op == "ds":
                if label:
                    ram_labels[addr] = label
                addr += int(args)
            continue

        if label:
            pending_labels.append(label)
        if not op:
            continue  # label-only line
        if op == "end":
            break

        if op in ("db", "dw"):
            vals = _count_values(args)
            size = len(vals) * (1 if op == "db" else 2)
            it = Item(addr, size, "byte" if op == "db" else "word", stripped, values=vals)
        else:
            ins = decode(rom, addr, org)
            if ins is None:
                raise ListingMismatch(f"line {lineno}: undefined opcode at ${addr:04X} ({stripped!r})")
            if normalise_mnemonic(op) != ins.mnemonic:
                raise ListingMismatch(
                    f"line {lineno}: listing says {op!r} but ROM decodes {ins.mnemonic!r} at ${addr:04X}"
                )
            it = Item(addr, ins.length, "code", stripped)
        if comment is not None:
            it.comment.append(comment)
        it.pre, pending_pre = pending_pre, []
        if pending_labels:
            labels.setdefault(addr, []).extend(pending_labels)
            pending_labels = []
        items.append(it)
        addr += it.size

    if org is None:
        raise ListingMismatch("no 'org' found: not an IDA ROM listing?")
    if addr - org != len(rom):
        raise ListingMismatch(f"listing covers {addr - org} bytes but ROM is {len(rom)} bytes")
    return Listing(ram_labels, labels, items, org)
