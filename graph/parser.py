"""Path of Exile 2 passive-tree URL codec (v7 format).

Decodes the base64url-encoded binary that follows
`pathofexile2.com/game/passive-skill-tree/` into a structured AST, and re-encodes
the AST back into the canonical byte stream. Round-trip is byte-exact.

The format is documented at pathofexile.com/developer/docs/game (Version 7).
"""

from __future__ import annotations

import base64
import struct
from dataclasses import dataclass, field
from typing import Optional

FLAG_WEAPON_SET = 0b00000001
FLAG_SKILL_OVERRIDE = 0b00000010
SUPPORTED_VERSION = 7


@dataclass
class NodeRecord:
    """One allocated node in a build.

    `node_hash` is the uint16 numeric id (matches `node.skill` in the tree JSON).
    `flags` carries the format's flag bits. `weapon_set` is 0 or 1 when the node
    is set-specific. `skill_override` is the uint16 row id into
    `tree.skillOverrides` when the node carries a multi-choice resolution.
    """
    node_hash: int
    flags: int
    weapon_set: Optional[int] = None
    skill_override: Optional[int] = None

    @property
    def is_weapon_set_specific(self) -> bool:
        return bool(self.flags & FLAG_WEAPON_SET)

    @property
    def has_skill_override(self) -> bool:
        return bool(self.flags & FLAG_SKILL_OVERRIDE)


@dataclass
class Build:
    version: int
    character_class: int
    ascendancy: int
    records: list[NodeRecord] = field(default_factory=list)

    def encoded_size(self) -> int:
        size = 8  # header
        for r in self.records:
            size += 4
            if r.is_weapon_set_specific:
                size += 1
            if r.has_skill_override:
                size += 2
        return size


def _strip_url_prefix(url_or_code: str) -> str:
    """Accept a full PoE2 URL or a bare base64 code."""
    if "/" in url_or_code:
        return url_or_code.rsplit("/", 1)[-1]
    return url_or_code


def _decode_b64url(code: str) -> bytes:
    code = code.strip()
    code += "=" * ((4 - len(code) % 4) % 4)
    return base64.urlsafe_b64decode(code)


def _encode_b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def parse(url_or_code: str) -> Build:
    """Parse a PoE 2 build URL or bare code into a Build."""
    raw = _decode_b64url(_strip_url_prefix(url_or_code))

    if len(raw) < 8:
        raise ValueError(f"build payload too short: {len(raw)} bytes")

    (version,) = struct.unpack(">I", raw[0:4])
    if version != SUPPORTED_VERSION:
        raise ValueError(f"unsupported build format version {version}; expected {SUPPORTED_VERSION}")

    character_class = raw[4]
    ascendancy = raw[5]
    (n_records,) = struct.unpack(">H", raw[6:8])

    i = 8
    records: list[NodeRecord] = []
    for _ in range(n_records):
        if i + 4 > len(raw):
            raise ValueError(f"truncated record at offset {i}")
        (node_hash,) = struct.unpack(">H", raw[i : i + 2])
        (flags,) = struct.unpack(">H", raw[i + 2 : i + 4])
        i += 4

        weapon_set: Optional[int] = None
        skill_override: Optional[int] = None

        if flags & FLAG_WEAPON_SET:
            if i + 1 > len(raw):
                raise ValueError(f"truncated weapon_set byte at offset {i}")
            weapon_set = raw[i]
            i += 1

        if flags & FLAG_SKILL_OVERRIDE:
            if i + 2 > len(raw):
                raise ValueError(f"truncated skill_override at offset {i}")
            (skill_override,) = struct.unpack(">H", raw[i : i + 2])
            i += 2

        records.append(NodeRecord(node_hash, flags, weapon_set, skill_override))

    if i != len(raw):
        raise ValueError(f"trailing bytes after {n_records} records: consumed {i}, total {len(raw)}")

    return Build(version, character_class, ascendancy, records)


def encode(build: Build) -> bytes:
    """Encode a Build back into the canonical v7 byte stream."""
    if build.version != SUPPORTED_VERSION:
        raise ValueError(f"only v{SUPPORTED_VERSION} encoding supported")
    if not (0 <= build.character_class <= 255):
        raise ValueError(f"character_class out of uint8 range: {build.character_class}")
    if not (0 <= build.ascendancy <= 255):
        raise ValueError(f"ascendancy out of uint8 range: {build.ascendancy}")
    if not (0 <= len(build.records) <= 0xFFFF):
        raise ValueError(f"too many records for uint16 count: {len(build.records)}")

    out = bytearray()
    out += struct.pack(">I", build.version)
    out.append(build.character_class)
    out.append(build.ascendancy)
    out += struct.pack(">H", len(build.records))

    for r in build.records:
        out += struct.pack(">H", r.node_hash)
        out += struct.pack(">H", r.flags)
        if r.flags & FLAG_WEAPON_SET:
            if r.weapon_set is None:
                raise ValueError(f"flag set but weapon_set missing: {r}")
            out.append(r.weapon_set)
        if r.flags & FLAG_SKILL_OVERRIDE:
            if r.skill_override is None:
                raise ValueError(f"flag set but skill_override missing: {r}")
            out += struct.pack(">H", r.skill_override)

    return bytes(out)


def encode_url(build: Build, base: str = "https://pathofexile2.com/game/passive-skill-tree/") -> str:
    return base + _encode_b64url(encode(build))


def flag_summary(build: Build) -> dict[int, int]:
    """Count records by flag value — useful for parser sanity checks."""
    counts: dict[int, int] = {}
    for r in build.records:
        counts[r.flags] = counts.get(r.flags, 0) + 1
    return counts
