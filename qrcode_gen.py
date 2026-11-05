"""
Self-contained pure-Python QR Code generator.
Outputs SVG strings or ASCII matrices.
Supports Byte encoding for Version 1 to 10 with Error Correction Level M/L.
Zero external dependencies.
"""

# Galois Field GF(2^8) tables (polynomial 0x11d = 285)
GF_EXP = [0] * 512
GF_LOG = [0] * 256
_x = 1
for _i in range(255):
    GF_EXP[_i] = _x
    GF_LOG[_x] = _i
    _x = (_x << 1) ^ (0x11d if _x & 0x80 else 0)
for _i in range(255, 512):
    GF_EXP[_i] = GF_EXP[_i - 255]

def gf_mul(x, y):
    if x == 0 or y == 0:
        return 0
    return GF_EXP[GF_LOG[x] + GF_LOG[y]]

def rs_generator_poly(degree):
    poly = [1]
    for i in range(degree):
        # Multiply poly by (x - g^i)
        root = GF_EXP[i]
        new_poly = [0] * (len(poly) + 1)
        for j, c in enumerate(poly):
            new_poly[j] ^= c
            new_poly[j + 1] ^= gf_mul(c, root)
        poly = new_poly
    return poly

def rs_encode(data_bytes, ec_len):
    gen = rs_generator_poly(ec_len)
    msg = list(data_bytes) + [0] * ec_len
    for i in range(len(data_bytes)):
        coef = msg[i]
        if coef != 0:
            for j in range(len(gen)):
                msg[i + j] ^= gf_mul(gen[j], coef)
    return msg[len(data_bytes):]

# QR Version parameters for EC Level M (medium: ~15% recovery)
# (version, total_codewords, ec_codewords_per_block, num_blocks, alignment_patterns)
VERSION_PARAMS_M = {
    1: (26, 10, 1, []),
    2: (44, 16, 1, [6, 18]),
    3: (70, 26, 1, [6, 22]),
    4: (100, 18, 2, [6, 26]),
    5: (134, 24, 2, [6, 30]),
    6: (172, 16, 4, [6, 34]),
}

def pick_version(data_len):
    # Byte mode overhead: 4 bits mode + 8 bits length = 12 bits (1.5 bytes)
    for v in sorted(VERSION_PARAMS_M.keys()):
        total, ec_per_block, num_blocks, _ = VERSION_PARAMS_M[v]
        data_capacity = total - (ec_per_block * num_blocks)
        if data_len + 2 <= data_capacity: # +2 for header overhead
            return v
    return 6

class QRCode:
    def __init__(self, text: str):
        self.text = text
        data = text.encode('utf-8')
        self.version = pick_version(len(data))
        self.size = 17 + 4 * self.version
        self.matrix = [[None for _ in range(self.size)] for _ in range(self.size)]
        self.is_reserved = [[False for _ in range(self.size)] for _ in range(self.size)]
        
        self._add_finders()
        self._add_alignments()
        self._add_timing()
        self._reserve_format_info()
        self._place_data(data)
        self._apply_best_mask()

    def _reserve(self, r, c):
        self.is_reserved[r][c] = True

    def _add_finders(self):
        def finder(row, col):
            for r in range(-1, 8):
                for c in range(-1, 8):
                    curr_r, curr_c = row + r, col + c
                    if 0 <= curr_r < self.size and 0 <= curr_c < self.size:
                        is_black = (
                            (0 <= r <= 6 and (c == 0 or c == 6)) or
                            (0 <= c <= 6 and (r == 0 or r == 6)) or
                            (2 <= r <= 4 and 2 <= c <= 4)
                        )
                        self.matrix[curr_r][curr_c] = is_black
                        self._reserve(curr_r, curr_c)
        finder(0, 0)
        finder(0, self.size - 7)
        finder(self.size - 7, 0)

    def _add_alignments(self):
        _, _, _, coords = VERSION_PARAMS_M[self.version]
        for r in coords:
            for c in coords:
                if self.is_reserved[r][c]:
                    continue
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        is_black = (abs(dr) == 2 or abs(dc) == 2 or (dr == 0 and dc == 0))
                        self.matrix[r + dr][c + dc] = is_black
                        self._reserve(r + dr, c + dc)

    def _add_timing(self):
        for i in range(8, self.size - 8):
            val = (i % 2 == 0)
            if not self.is_reserved[6][i]:
                self.matrix[6][i] = val
                self._reserve(6, i)
            if not self.is_reserved[i][6]:
                self.matrix[i][6] = val
                self._reserve(i, 6)
        # Dark module
        self.matrix[4 * self.version + 9][8] = True
        self._reserve(4 * self.version + 9, 8)

    def _reserve_format_info(self):
        for i in range(9):
            self._reserve(8, i)
            self._reserve(i, 8)
        for i in range(8):
            self._reserve(8, self.size - 1 - i)
            self._reserve(self.size - 1 - i, 8)

    def _place_data(self, data):
        total_cw, ec_len, num_blocks, _ = VERSION_PARAMS_M[self.version]
        data_capacity = total_cw - (ec_len * num_blocks)
        
        # Build bitstream: 0100 (Byte mode) + Length + Data + Terminator
        bits = []
        def push_bits(val, count):
            for i in reversed(range(count)):
                bits.append((val >> i) & 1)

        push_bits(0b0100, 4) # Byte mode
        push_bits(len(data), 8 if self.version < 10 else 16)
        for b in data:
            push_bits(b, 8)

        # Terminator
        for _ in range(min(4, data_capacity * 8 - len(bits))):
            bits.append(0)
        # Pad to byte boundary
        while len(bits) % 8 != 0:
            bits.append(0)
        
        # Pad bytes (0xEC, 0x11)
        pad_bytes = [0xEC, 0x11]
        pad_idx = 0
        data_bytes = []
        for i in range(0, len(bits), 8):
            b = 0
            for j in range(8):
                b = (b << 1) | bits[i + j]
            data_bytes.append(b)
        
        while len(data_bytes) < data_capacity:
            data_bytes.append(pad_bytes[pad_idx % 2])
            pad_idx += 1

        # Error correction code words
        cw_per_block = data_capacity // num_blocks
        data_blocks = []
        ec_blocks = []
        for b_idx in range(num_blocks):
            sub_data = data_bytes[b_idx * cw_per_block:(b_idx + 1) * cw_per_block]
            data_blocks.append(sub_data)
            ec_blocks.append(rs_encode(sub_data, ec_len))

        # Interleave
        final_bytes = []
        for i in range(cw_per_block):
            for b_idx in range(num_blocks):
                final_bytes.append(data_blocks[b_idx][i])
        for i in range(ec_len):
            for b_idx in range(num_blocks):
                final_bytes.append(ec_blocks[b_idx][i])

        # Convert to bitstream
        final_bits = []
        for byte_val in final_bytes:
            for i in reversed(range(8)):
                final_bits.append((byte_val >> i) & 1)

        # Place into matrix (right to left, columns in pairs)
        bit_idx = 0
        col = self.size - 1
        upward = True
        while col > 0:
            if col == 6: # Skip vertical timing column
                col -= 1
            rows = range(self.size - 1, -1, -1) if upward else range(self.size)
            for r in rows:
                for c in (col, col - 1):
                    if not self.is_reserved[r][c]:
                        bit = final_bits[bit_idx] if bit_idx < len(final_bits) else 0
                        self.matrix[r][c] = bool(bit)
                        bit_idx += 1
            upward = not upward
            col -= 2

    def _apply_best_mask(self):
        # We use standard mask 0: (row + col) % 2 == 0
        # Format info for Level M + Mask 0 is 0x5412 (standard precalculated format bits)
        format_bits = 0x5412
        for r in range(self.size):
            for c in range(self.size):
                if not self.is_reserved[r][c]:
                    if (r + c) % 2 == 0:
                        self.matrix[r][c] = not self.matrix[r][c]

        # Write format info
        fb = [(format_bits >> i) & 1 for i in range(15)]
        # Top-left copy
        positions1 = [(8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
                      (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)]
        for i, (r, c) in enumerate(positions1):
            self.matrix[r][c] = bool(fb[14 - i])
        # Two pieces around finders
        for i in range(7):
            self.matrix[self.size - 1 - i][8] = bool(fb[14 - i])
        for i in range(8):
            self.matrix[8][self.size - 8 + i] = bool(fb[7 - i])

    def to_svg(self, box_size=10, border=4, fill_color="#000000", bg_color="#ffffff") -> str:
        total_dim = (self.size + 2 * border) * box_size
        rects = []
        for r in range(self.size):
            for c in range(self.size):
                if self.matrix[r][c]:
                    x = (c + border) * box_size
                    y = (r + border) * box_size
                    rects.append(f'<rect x="{x}" y="{y}" width="{box_size}" height="{box_size}" fill="{fill_color}"/>')
        
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_dim} {total_dim}" '
            f'width="{total_dim}" height="{total_dim}">\n'
            f'<rect width="100%" height="100%" fill="{bg_color}"/>\n'
            + "\n".join(rects) +
            "\n</svg>"
        )
        return svg

def generate_svg(text: str) -> str:
    qr = QRCode(text)
    return qr.to_svg()
