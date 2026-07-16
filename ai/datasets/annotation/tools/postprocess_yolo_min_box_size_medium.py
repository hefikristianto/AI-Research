from pathlib import Path

LABEL_DIR = Path("ai/datasets/annotation/auto_labels_v5_medium/labels/yolo")

MIN_WIDTH_BY_CLASS = {
    0: 0.025,  # order_block, sekitar 16px dari 640
    1: 0.045,  # fair_value_gap, sekitar 28px dari 640
}

MIN_HEIGHT = 0.015  # sekitar 10px dari 640


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def fix_line(line: str):
    parts = line.strip().split()

    if len(parts) != 5:
        return line.strip()

    class_id = int(float(parts[0]))
    x = float(parts[1])
    y = float(parts[2])
    w = float(parts[3])
    h = float(parts[4])

    min_w = MIN_WIDTH_BY_CLASS.get(class_id, 0.025)

    w = max(w, min_w)
    h = max(h, MIN_HEIGHT)

    # Jaga supaya box tidak keluar batas gambar.
    half_w = w / 2
    half_h = h / 2

    x = clamp(x, half_w, 1.0 - half_w)
    y = clamp(y, half_h, 1.0 - half_h)

    return f"{class_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}"


def main():
    if not LABEL_DIR.exists():
        raise FileNotFoundError(f"Label dir not found: {LABEL_DIR}")

    fixed_files = 0
    fixed_lines = 0

    for label_path in LABEL_DIR.glob("*.txt"):
        original = label_path.read_text(encoding="utf-8").splitlines()

        if not original:
            continue

        fixed = []
        changed = False

        for line in original:
            if not line.strip():
                continue

            new_line = fix_line(line)
            fixed.append(new_line)

            if new_line != line.strip():
                changed = True
                fixed_lines += 1

        if changed:
            label_path.write_text("\n".join(fixed) + "\n", encoding="utf-8")
            fixed_files += 1

    print(f"Fixed files : {fixed_files}")
    print(f"Fixed lines : {fixed_lines}")
    print("Done: YOLO label minimum box size applied.")


if __name__ == "__main__":
    main()
