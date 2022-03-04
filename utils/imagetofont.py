#!/usr/bin/env python3

# Helper script for converting an image containing 256 font glyphs into a Pillow-format bitmap font
# Uses bmp2pcf from https://github.com/yyny/ccmono to convert the image into a PCF font, slightly modified
# Uses pilfont from https://github.com/python-pillow/pillow-scripts/ to convert the PCF font into a Pillow bitmap font
# These can be found in the ccmono and pillow-scripts subdirectories, and are subject to their respective licenses
# Requires a system-wide installation of Lua 5.3 or greater on the PATH (for bmp2pcf)
# Requires convert from Imagemagick on the PATH (Pillow and ffmpeg do not create transparent BMPs)

import subprocess
import sys
import shutil

from pathlib import Path

bmp2pcf = Path("utils/ccmono/bmp2pcf.lua").resolve()
pilfont = Path("utils/pillow-scripts/pilfont.py").resolve()
temppath = Path("utils/temp").resolve()

if len(sys.argv) < 2:
    print("Usage: imagetofont.py <input image> [arguments for bmp2pcf...]")
    print("bmp2pcf help (Don't worry about infile and outfile, just the options):")
    subprocess.run(["lua", bmp2pcf], cwd=bmp2pcf.parent)
    sys.exit(1)

infile = Path(sys.argv[1])
argv = sys.argv[2:]

bmppath = (temppath / (infile.stem + ".bmp"))
pcfpath = (temppath / (infile.stem + ".pcf"))

print("converting file to bmp with imagemagick")
subprocess.run(["convert", infile, bmppath])
print("converting bmp to pcf with ccmono")
subprocess.run(["lua", bmp2pcf, bmppath, pcfpath] + argv, cwd=bmp2pcf.parent, stdout=subprocess.DEVNULL)
print("converting pcf to pil with pilfont")
subprocess.run([pilfont, pcfpath], stdout=subprocess.DEVNULL)

pilpath = (temppath / (infile.stem + ".pil"))
pbmpath = (temppath / (infile.stem + ".pbm"))

shutil.copy2(pilpath, infile.parent)
shutil.copy2(pbmpath, infile.parent)

print("done! output to " + pilpath.name + " and " + pbmpath.name)
print(pbmpath.name + " is a renamed png file and can be edited.")
print("keep in mind it must be either greyscale or b/w, with no alpha data!")
