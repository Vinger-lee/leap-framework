"""Build the offline drop-tower SVG; no Anatomy or JS runtime is required.

Original geometry, inspired by wheresryan22/anatomy's physical-object approach.
Run with --check to verify the committed HTML without writing it.
"""
from __future__ import annotations

import argparse
from math import cos, pi, sin
from pathlib import Path

PAGE = Path(__file__).with_name("leap-04-physics-free-fall.html")
START, END = "<!-- LEAP_RIG_START -->", "<!-- LEAP_RIG_END -->"
TONES = {
    "base": ("#c8c5bb", "#96958e", "#afada3"),
    "frame": ("#e6e3db", "#aaa99f", "#c5c2b8"),
    "shell": ("#eeeae1", "#b8b5ab", "#d7d2c6"),
    "dark": ("#737b80", "#434d52", "#596369"),
}


def point(x, y, z):
    return 330 + .8660254 * (x - y), 520 + .5 * (x + y) - z


def xy(p):
    return f"{p[0]:.3f},{p[1]:.3f}"


def line(points, **attrs):
    props = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    return f'<path d="M' + " L".join(xy(p) for p in points) + f'" fill="none" {props}/>'


def block(name, x, y, z, w, d, h, tone="frame"):
    top, left, right = TONES[tone]
    a, b, c, e = [point(px, py, z) for px, py in [(x, y), (x+w, y), (x+w, y+d), (x, y+d)]]
    at, bt, ct, et = [point(px, py, z+h) for px, py in [(x, y), (x+w, y), (x+w, y+d), (x, y+d)]]
    def face(points, fill):
        return f'<polygon points="{" ".join(xy(p) for p in points)}" fill="{fill}"/>'
    return (f'<g data-solid="{name}">' + face([b, c, ct, bt], right)
            + face([e, c, ct, et], left) + face([at, bt, ct, et], top)
            + line([et, at, bt], stroke="#faf8f2", stroke_width=".65") + '</g>')


def screw(x, y, z):
    u, v = point(x, y, z)
    return (f'<ellipse cx="{u:.3f}" cy="{v:.3f}" rx="1.9" ry="1.0" fill="#60686b" stroke="none"/>'
            + line([(u-1, v), (u+1, v)], stroke="#e4e3dc", stroke_width=".45"))


def assembly(name, parts):
    return f'<g class="rig-part" data-part="{name}" id="rig-{name}">' + "\n".join(parts) + '</g>'


def build():
    groups = []
    base = []
    for x, y in [(-85, -36), (79, -36), (-85, 30), (79, 30)]:
        base += [block("foot-pad", x-7, y-7, -1, 14, 14, 5, "dark"),
                 block("leveling-foot", x-5, y-5, 4, 10, 10, 6, "base")]
    base += [block("base-plate", -106, -54, 10, 212, 108, 10, "base")]
    for x in [-94, 94]:
        for y in [-43, 43]:
            base.append(screw(x, y, 20.1))
    groups.append(assembly("base", base))

    frame = [block("rear-skin", -56, -35, 40, 112, 3, 360, "shell")]
    for x in [-65, 54]:
        frame += [block("upright-foot", x-4, -38, 20, 19, 25, 8, "base"),
                  block("rear-upright", x, -32, 28, 11, 12, 372)]
        for z in [60, 190, 340]:
            frame += [block("frame-bracket", x, -20, z, 11, 15, 7), screw(x+5, -11, z+7.1)]
    frame += [block("upper-crossbeam", -65, -32, 400, 130, 66, 10)]
    groups.append(assembly("frame", frame))

    catcher = [block("catcher-floor", -40, -24, 20, 80, 48, 9, "dark")]
    for y in [-24, 19]:
        catcher.append(block("tray-lip", -40, y, 29, 80, 5, 8, "base"))
    for x in [-40, 35]:
        catcher.append(block("tray-end", x, -19, 29, 5, 38, 8, "base"))
    catcher.append(block("catch-pad", -34, -18, 29, 68, 36, 15, "dark"))
    groups.append(assembly("catch", catcher))

    gates = []
    for i, z in enumerate([75, 190, 320]):
        pair = []
        for mount_x, sensor_x in [(-54, -40), (40, 34)]:
            pair += [block("gate-mount", mount_x, -26, z-7, 14, 38, 14, "base"),
                     block("gate-sensor", sensor_x, -8, z-4, 6, 16, 8, "dark")]
        # The optical path ends at the two real sensor faces.
        pair.append(line([point(-34, 0, z), point(34, 0, z)], stroke="#c7cbd1", stroke_width=".7", stroke_dasharray="2 3"))
        gates.append(f'<g id="rig-gate-{i}" data-level="{z}">' + "".join(pair) + '</g>')
    groups.append(assembly("gates", gates))

    # The sphere moves only vertically, in this fixed slot behind the front frame.
    ball = ('<g id="rigBall" data-time="0" data-height="50" data-fallen="0" data-speed="0">'
            '<circle cx="330" cy="161" r="9" fill="url(#rig-sphere)" stroke="#243b80" stroke-width=".8"/>'
            '<circle cx="327.6" cy="158" r="1.5" fill="#fff" stroke="none"/></g>')
    groups.append(ball)

    scale = [block("ruler-bracket", 59, 1, 20, 15, 15, 25, "base"),
             block("ruler-bracket", 59, 1, 375, 15, 15, 25, "base"),
             block("ruler-strip", 62, 8, 45, 10, 5, 330, "shell")]
    for i in range(41):
        z = 53 + i * 7.65
        scale.append(line([point(62, 13, z), point(69 if i % 5 == 0 else 65.5, 13, z)],
                          stroke="#5b6263" if i % 5 == 0 else "#8e9390", stroke_width=".7"))
    groups.append(assembly("scale", scale))

    release = [block("head-bracket", -25, -23, 390, 50, 46, 10),
               block("electromagnet", -18, -17, 376, 36, 34, 14, "dark"),
               block("pole-piece", -8, -7, 368, 16, 14, 8, "base")]
    for x in [-18, 18]:
        release.append(screw(x, 15, 400.1))
    groups.append(assembly("release", release))

    # This narrow front panel leaves an observation slit; the near face hides
    # the optical paths where it should. Opening moves it away from the subject.
    door = [block("front-upright-foot", 50, 18, 20, 19, 20, 8, "base"),
            block("front-upright", 54, 22, 28, 11, 12, 372),
            block("inspection-cover", 38, 25, 46, 7, 4, 343, "shell")]
    for z in [70, 350]:
        door += [block("hinge", 45, 22, z, 9, 10, 14, "base"), screw(49, 27, z+14.1)]
    door.append(block("cover-handle", 40, 29, 214, 5, 6, 42, "dark"))
    groups.append(assembly("door", door))

    console = [block("console-foot", 106, -30, 0, 92, 64, 20, "base"),
               block("instrument-case", 108, -28, 20, 88, 60, 37, "dark"),
               block("instrument-face", 112, -24, 57, 80, 52, 2, "shell")]
    for x, y in [(116,-20), (187,-20), (116,23), (187,23)]:
        console.append(screw(x,y,59.1))
    for x in [120, 174]:
        console += [block("control-neck", x, 13, 59, 8, 8, 3, "base"),
                    block("control-knob", x-1, 12, 62, 10, 10, 5, "dark")]
        for dx in [1, 4, 7]:
            console.append(line([point(x+dx, 12, 63), point(x+dx, 12, 66)], stroke="#aaa99f", stroke_width=".5"))
    cx, cy = point(151, -4, 60)
    dial = [f'<g transform="translate({cx:.3f},{cy:.3f}) scale(1,.5)">',
            '<circle r="20" fill="#f9f6ef" stroke="#6f7676" stroke-width="1.4"/>']
    for i in range(21):
        angle = (-140 + i * 14) * pi / 180
        r = 15 if i % 5 == 0 else 17
        dial.append(line([(r*sin(angle), -r*cos(angle)), (19*sin(angle), -19*cos(angle))], stroke="#596369", stroke_width=".8"))
    dial += ['<path id="rigNeedle" d="M0 3 V-15" transform="rotate(-140)" stroke="#2b4ac4" stroke-width="1.4"/>',
             '<circle r="2" fill="#596369" stroke="none"/></g>']
    console += dial
    groups.append(assembly("console", console))

    return ('<svg id="fallRig" viewBox="130 0 520 710" role="img" aria-labelledby="rig-title rig-desc" '
            'xmlns="http://www.w3.org/2000/svg" fill="none" stroke="#677071" stroke-width=".8" stroke-linejoin="round">\n'
            '<title id="rig-title">自由落体实验塔的剖面与拆解</title>\n'
            '<desc id="rig-desc">固定支架上方是释放头，中间是竖直运动的小球与光门，底部是承接盘，右侧为归一化标尺和速度表。</desc>\n'
            '<defs><radialGradient id="rig-sphere" cx="30%" cy="25%"><stop stop-color="#ccd5f8"/>'
            '<stop offset=".6" stop-color="#4a66ce"/><stop offset="1" stop-color="#203882"/></radialGradient></defs>\n'
            + "\n".join(groups) + '\n</svg>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    page = PAGE.read_text(encoding="utf-8")
    if page.count(START) != 1 or page.count(END) != 1:
        raise SystemExit("Expected one SVG marker pair")
    prefix, rest = page.split(START)
    _, suffix = rest.split(END)
    figure = build()
    generated = prefix + START + "\n" + figure + "\n" + END + suffix
    if args.check:
        if generated != page:
            raise SystemExit("SVG is stale; run build_figure.py")
    else:
        PAGE.write_text(generated, encoding="utf-8")
    print(f"Drop-tower SVG: {figure.count('data-solid=')} solids; {'checked' if args.check else 'built'}")


if __name__ == "__main__":
    main()
