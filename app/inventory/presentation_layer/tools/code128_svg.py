"""Pure-Python Code 128 (Subset B) SVG barcode generator.

Generates self-contained SVG strings for Code 128 barcode tokens (e.g., 'INTAKE-8', 'SHIP-142')
without external binary or library dependencies.
"""

from __future__ import annotations

# Code 128 patterns (widths of alternating 6 bar/space modules, plus stop character's 7 modules)
# Index 0..102 match character codes. Index 104 is Start Code B. Index 106 is Stop Code.
PATTERNS = [
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213", # 0-9
    "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132", # 10-19
    "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211", # 20-29
    "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313", # 30-39
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331", # 40-49
    "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111", # 50-59
    "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214", # 60-69
    "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111", # 70-79
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141", # 80-89
    "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141", # 90-99
    "114131", "311141", "411131", "211412", "211214", "211232", "2331112"                                # 100-106
]

START_CODE_B = 104
STOP_CODE = 106


def generate_code128_svg(text: str, height: int = 50, module_width: float = 2.0) -> str:
    """Generate an SVG string for text encoded in Code 128 (Subset B)."""
    text = str(text or "").strip()
    if not text:
        return ""

    # Convert text characters to Code 128 Subset B character values (ASCII - 32)
    char_codes = []
    for ch in text:
        val = ord(ch) - 32
        if 0 <= val <= 95:
            char_codes.append(val)
        else:
            # Fallback to '?' (code 31) for unsupported characters
            char_codes.append(31)

    # Compute checksum: (104 + sum(pos * val for pos, val in enumerate(char_codes, 1))) % 103
    checksum = (START_CODE_B + sum(pos * code for pos, code in enumerate(char_codes, 1))) % 103

    # Sequence of pattern indices
    sequence = [START_CODE_B] + char_codes + [checksum, STOP_CODE]

    # Convert sequence to binary bar modules (1 = bar, 0 = space)
    bars = []
    for pat_idx in sequence:
        pattern = PATTERNS[pat_idx]
        is_bar = True
        for digit in pattern:
            width = int(digit)
            bars.extend([1 if is_bar else 0] * width)
            is_bar = not is_bar

    total_modules = len(bars)
    quiet_zone_modules = 10
    total_width = (total_modules + (2 * quiet_zone_modules)) * module_width
    svg_height = height + 20  # Extra space for text below bars

    rects = []
    current_x = quiet_zone_modules * module_width
    for b in bars:
        if b == 1:
            rects.append(
                f'<rect x="{current_x:.1f}" y="0" width="{module_width:.1f}" height="{height}" fill="#000000" />'
            )
        current_x += module_width

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_width:.1f} {svg_height}" width="{total_width:.1f}" height="{svg_height}">',
        f'<rect x="0" y="0" width="{total_width:.1f}" height="{svg_height}" fill="#ffffff" />',
        "".join(rects),
        f'<text x="{total_width / 2:.1f}" y="{height + 14}" font-family="monospace" font-size="12" text-anchor="middle" fill="#000000">{text}</text>',
        '</svg>'
    ]
    return "".join(svg_parts)
