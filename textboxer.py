#!/usr/bin/env python

import json
import math
import sys

from copy import deepcopy

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

from pathlib import Path

debug_mode = False


def debug(text):
    if debug_mode:
        print(text)


def resolve_resource(base: Path, key: str) -> Path:
    if (base / key).exists():
        return base / key
    if (base / "alias.json").exists():
        alias_file = (base / "alias.json").open()
        aliases = json.load(alias_file)
        alias_file.close()
        if key in aliases:
            return base / aliases[key]
    return base


def paste_alpha(base: Image.Image, overlay: Image.Image, offset: tuple = (0, 0)) -> Image.Image:
    padded_overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    padded_overlay.paste(overlay, offset)
    return Image.alpha_composite(base, padded_overlay)


def find_nth(haystack, needle, n):
    start = haystack.find(needle)
    while start >= 0 and n > 1:
        start = haystack.find(needle, start+len(needle))
        n -= 1
    return start


def wrap_text(text: str, maxwidth: int, font: ImageFont.FreeTypeFont,
              draw: ImageDraw.ImageDraw, break_on_any: bool = False) -> str:
    textcut = text[:]
    textout = ""
    while len(textcut) > 0:
        textwidth = draw.textlength(textcut, font)
        if textwidth < maxwidth:
            textout += textcut
            break
        # binary search for the longest substring that can fit in the designated width
        startpos = 0
        endpos = len(textcut)
        last_below = 0
        for i in range(0, math.floor(math.log2(len(textcut)) + 1)):
            curpos = (len(textcut[startpos:endpos]) // 2) + startpos
            debug("began binary search iteration " + str(i + 1) + " of " + str(math.floor(math.log2(len(textcut)) + 1))
                  + " with bounds " + str(startpos) + ":" + str(endpos)
                  + " and position " + str(curpos) + "/" + str(len(textcut) - 1))
            debug("search region: " + textcut[startpos - 1:endpos])
            debug("test region:   " + textcut[:curpos])
            textwidth = draw.textlength(textcut[:curpos], font)
            debug("found width " + str(textwidth) + " (target " + str(maxwidth) + ")")
            if textwidth < maxwidth:
                startpos = curpos + 1
                last_below = curpos
            elif textwidth > maxwidth:
                endpos = curpos - 1
            else:
                debug("found exact match, broke search")
                last_below = curpos
                break
        debug("finished binary search with bounds " + str(startpos) + ":" + str(endpos)
              + " and position " + str(last_below) + "/" + str(len(textcut) - 1))
        debug("fit region: " + textcut[:last_below])
        debug("remaining:  " + textcut[last_below:])
        breakpos = textcut.rfind(" ", 0, last_below + 1)
        if breakpos == -1 or break_on_any:
            textout += textcut[:last_below] + "\n"
            textcut = textcut[last_below:]
        else:
            textout += textcut[:breakpos] + "\n"
            textcut = textcut[breakpos + 1:]
    return textout


def test():
    metaf = open("resources/styles/oneshot/meta.json")
    meta = json.load(metaf)
    metaf.close()
    facex, facey = meta["face"]["x"], meta["face"]["y"]
    frame = Image.open("resources/styles/oneshot/frame.png")
    face = Image.open("resources/styles/oneshot/face.png")
    fontf = open("resources/styles/oneshot/font.ttf", 'rb')
    font = ImageFont.truetype(fontf, meta["font"]["size"])
    fontf.close()
    composite = paste_alpha(frame, face, (facex, facey))
    canvas = ImageDraw.Draw(composite)
    if not meta["text"]["main"]["antialias"]:
        canvas.fontmode = "1"
    text = "(oh goodness gracious I'm stuck in an elevator with the messiah and also literally god themself this is awkward)"
    canvas.multiline_text((meta["text"]["main"]["anchor_x"], meta["text"]["main"]["anchor_y"]),
                          wrap_text(text, meta["text"]["main"]["max_width"], font, canvas),
                          spacing=meta["text"]["main"]["spacing"], font=font)
    # print(wrap_text("(oh goodness gracious I'm stuck in an elevator with the messiah and also literally god themself this is awkward)", 460, font, canvas))
    # print(canvas.textlength("(oh goodness gracious I'm stuck in an elevator", font))
    composite.show()


def evaluate_predicate(predicate_state: dict[str, list], predicate: str) -> bool:
    for part in predicate.split("&"):
        if part == "always":
            continue
        if part == "parse":
            debug("Ignoring 'parse' predicate: it should have already been loaded")
            return False
        mid = part.find(":")
        if part[mid + 1:] not in predicate_state[part[:mid]]:
            return False
    return True


def load_jsons(data_paths: list[Path]) -> (dict[int, list], dict[str, dict]):
    sorts = {}
    preloads = {}
    for path in data_paths:
        data_file = path.open()
        cdata: dict = json.load(data_file)
        data_file.close()
        debug("loading " + str(path))
        if cdata["predicate"] == "parse":
            preloads = merge_dicts(preloads, cdata)
            continue
        if cdata["sort"] not in sorts:
            sorts[cdata["sort"]] = []
        sorts[cdata["sort"]].append(cdata)
    debug(sorts)
    debug(preloads)
    return sorts, preloads


def parse_jsons(predicate_state: dict, sorts: dict[int, list]) -> dict[str, dict]:
    output = {}
    for sort_value in sorted(sorts.keys()):
        debug("loading sort value " + str(sort_value))
        for data in sorts[sort_value]:
            if evaluate_predicate(predicate_state, data["predicate"]):
                output = merge_dicts(output, data)
    del output["sort"]
    del output["predicate"]
    return output


def resolve_jsons(predicate_state: dict, data_paths: list[Path]) -> dict[str, dict]:
    return parse_jsons(predicate_state, load_jsons(data_paths)[0])


def merge_dicts(a: dict, b: dict) -> dict:
    output = {}
    for key in a:
        if key in b:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                debug("merge " + key)
                output[key] = merge_dicts(a[key], b[key])
            else:
                debug("overwrite " + key)
                output[key] = deepcopy(b[key])
        else:
            debug("keep " + key)
            output[key] = deepcopy(a[key])
    for key in b:
        if key not in a:
            debug("append " + key)
            output[key] = deepcopy(b[key])
    return output


def create_expand(base_imagepath: Path, image_data: dict) -> Image.Image:
    base_image = Image.open(base_imagepath)
    # target width and height
    w, h = image_data["size"]
    # division lines on base image
    dx1, dx2, dy1, dy2 = image_data["divide"]
    # max x and y for base image
    mx, my = base_image.size
    # right section width, bottom section height
    rsw, bsh = mx - dx2, my - dy2
    # transformed right/bottom division line locations for target
    dtx, dty = w - rsw, h - bsh
    # size values for scalable regions
    xs, ys = (dtx - dx1), (dty - dy1)
    # [x1 [y1 x2) y2)
    section_bounds = {
        "tl": (0, 0, dx1, dy1),
        "tm": (dx1, 0, dx2, dy1),
        "tr": (dx2, 0, mx, dy1),
        "ml": (0, dy1, dx1, dy2),
        "mm": (dx1, dy1, dx2, dy2),
        "mr": (dx2, dy1, mx, dy2),
        "bl": (0, dy2, dx1, my),
        "bm": (dx1, dy2, dx2, my),
        "br": (dx2, dy2, mx, my)
    }
    section_locations = {
        "tl": (0, 0),
        "tm": (dx1, 0),
        "tr": (dtx, 0),
        "ml": (0, dy1),
        "mm": (dx1, dy1),
        "mr": (dtx, dy1),
        "bl": (0, dty),
        "bm": (dx1, dty),
        "br": (dtx, dty)
    }
    section_sizes = {
        "tl": (dx1, dy1),
        "tm": (xs, dy1),
        "tr": (rsw, dy1),
        "ml": (dx1, ys),
        "mm": (xs, ys),
        "mr": (rsw, ys),
        "bl": (dx1, bsh),
        "bm": (xs, bsh),
        "br": (rsw, bsh)
    }
    output = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for section in section_locations:
        output.paste(base_image.resize(section_sizes[section], Image.NEAREST, section_bounds[section]),
                     section_locations[section])
    return output


def parsestr(textin: str, *, out: str = None):
    args = textin.split(" ")
    style = None
    text = {}
    images = {}
    flags = []
    default_data = Path("resources/default/data/")
    style_root = Path("resources/styles/")
    if (style_root / args[0]).exists():
        style = args[0]
        del args[0]
    if style is None:
        # need to load just the default parse data to get the default style, could be cached but effort
        _, preload = load_jsons(list(default_data.glob("*.json")))
        style = preload["defaultstyle"]
    style_data = style_root / style / "data"
    sorts, preload = load_jsons(list(default_data.glob("*.json")) + list(style_data.glob("*.json")))
    while args[0].startswith("f:") or args[0].startswith("flag:"):
        flags.append(args[0][args[0].find(":") + 1:])
        del args[0]
    for argdesc in preload["str"]:
        key, value = argdesc.split(":")
        match key:
            case "text":
                text[value] = args[0]
                del args[0]
            case "image":
                images[value] = args[0]
                del args[0]
            case "textfill":
                remaining = ""
                for arg in args:
                    remaining += arg + " "
                text[value] = remaining
                args = []
        if len(args) <= 0:
            break
    generate(style, text, images, flags, preload_data=sorts, out=out)


def parsestrlist(args: list[str], *, style: str = None, text: dict[str, str] = None,
                 images: dict[str, str] = None, flags: list[str] = None, out: str = None):
    if text is None:
        text = {}
    if images is None:
        images = {}
    if flags is None:
        flags = []
    default_data = Path("resources/default/data/")
    style_root = Path("resources/styles/")
    if (style_root / args[0]).exists():
        style = args[0]
        del args[0]
    if style is None:
        # need to load just the default parse data to get the default style, could be cached but effort
        _, preload = load_jsons(list(default_data.glob("*.json")))
        style = preload["defaultstyle"]
    style_data = style_root / style / "data"
    sorts, preload = load_jsons(list(default_data.glob("*.json")) + list(style_data.glob("*.json")))
    for argdesc in preload["args"]:
        key, value = argdesc.split(":")
        match key:
            case "text":
                text[value] = args[0]
                del args[0]
            case "image":
                images[value] = args[0]
                del args[0]
        if len(args) <= 0:
            break
    for remaining in args:
        flags.append(remaining)
    generate(style, text, images, flags, preload_data=sorts, out=out)


def generate(style: str, text: dict[str, str], images: dict[str, str] = None,
             flags: list[str] = None, *, out: str = None, preload_data: dict[int, list] = None):
    predicate_state = {
        "textbox": list(text) if text is not None else [],
        "image": list(images) if images is not None else [],
        "flag": flags if flags is not None else []
    }
    debug(predicate_state)
    default_data = Path("resources/default/data/")
    style_dir = Path("resources/styles/" + style)
    style_data = style_dir / "data"
    if preload_data is not None:
        data = parse_jsons(predicate_state, preload_data)
    else:
        data = resolve_jsons(predicate_state, list(default_data.glob("*.json")) + list(style_data.glob("*.json")))
    debug(data)

    # resolve font and image files
    font_data = {}
    for fontname in data["fonts"]:
        if isinstance(data["fonts"][fontname], dict):
            font_data[fontname] = data["fonts"][fontname]
            fontfile = (style_dir / data["fonts"]["basepath"] / font_data[fontname]["path"]).open("rb")
            font_data[fontname]["resolved"] = ImageFont.truetype(fontfile, font_data[fontname]["size"])
            fontfile.close()

    image_data = {}
    deferred_images = {}
    for imagename in data["images"]:
        if isinstance(data["images"][imagename], dict):
            image_data[imagename] = data["images"][imagename]
            imagepath = style_dir / data["images"]["basepath"]
            match image_data[imagename]["type"]:
                case "static":
                    image_data[imagename]["resolved"] = Image.open(imagepath / image_data[imagename]["path"])
                case "dynamic":
                    image_data[imagename]["resolved"] = Image.open(
                        resolve_resource(imagepath / image_data[imagename]["pathprefix"],
                                         images[image_data[imagename]["key"]])
                    )
                case "expand":
                    # image divided into 9 regions, corners stay static
                    # edges and center are stretched out to fit designated width/height
                    match image_data[imagename]["mode"]:
                        case "static":
                            image_data[imagename]["resolved"] = create_expand(imagepath / image_data[imagename]["path"],
                                                                              image_data[imagename])
                        case "textbox":
                            textboxname = image_data[imagename]["textbox"]
                            deferred_images[textboxname] = image_data[imagename]
                            deferred_images[textboxname]["path_resolved"] = imagepath / image_data[imagename]["path"]
                            del image_data[imagename]
    debug(font_data)
    debug(image_data)

    composite = None
    if "basesize" in data["images"]:
        composite = Image.new("RGBA", data["images"]["basesize"], (0, 0, 0, 0))
    for imagename in image_data:
        image = image_data[imagename]
        if composite is None:
            composite = image["resolved"].copy()
            continue
        composite = paste_alpha(composite, image["resolved"], image["position"])
    canvas = ImageDraw.Draw(composite)
    default_fontmode = canvas.fontmode
    for textboxname in data["textboxes"]:
        if isinstance(data["textboxes"][textboxname], dict):
            canvas.fontmode = default_fontmode
            textbox = data["textboxes"][textboxname]
            font = font_data[textbox["font"]]
            if not font["antialias"]:
                canvas.fontmode = "1"
            text_wrapped = wrap_text(text[textboxname], textbox["max_width"], font["resolved"], canvas)
            lines = text_wrapped.count("\n") + 1
            if lines > textbox["max_lines"] and textbox["line_wrap"] == "cut":
                text_wrapped = text_wrapped[:find_nth(text_wrapped, "\n", textbox["max_lines"])]
            if textboxname in deferred_images:
                tx1, ty1, tx2, ty2 = canvas.multiline_textbbox(textbox["anchor"],
                                                               text_wrapped,
                                                               spacing=font["spacing"],
                                                               font=font["resolved"])
                tw, th = tx2 - tx1, ty2 - ty1
                image = deferred_images[textboxname]
                if "x" in image["bind_axes"]:
                    image["size"][0] = tw + image["sizemod"][0]
                if "y" in image["bind_axes"]:
                    image["size"][1] = th + image["sizemod"][1]
                composite = paste_alpha(composite, create_expand(image["path_resolved"], image), image["position"])
                canvas = ImageDraw.Draw(composite)
            canvas.multiline_text(textbox["anchor"],
                                  text_wrapped,
                                  spacing=font["spacing"],
                                  font=font["resolved"])
    if out is not None:
        composite.save(out)
        return
    composite.show()


if __name__ == '__main__':
    debug_mode = True
    # generate("omori", {"main": "I hope you're having a great day!", "name": "MARI"}, {"face": "mari_happy"})
    # generate("oneshot", {"main": "mhm yep uh huh yeah got it mhm great yeah uh huh okay"}, {"face": "af"})
    # generate("omori", {"main": "I am... a gift for you... DREAMER.", "name": "ABBI"}, flags=["scared"])
    # generate("omori", {"main": "i'm in your website. what will you do. おやすみ、オヤスミ。", "name": "SOMETHING"}, {"face": "something"})
    # parsestr(["The way is blocked... by blocks!"])
    # parsestrlist(["omori", "How is it march already", "BASIL", "basil_flower_stare"])
    parsestr("omori f:scared BASIL basil_dark_flower_cry That's mean, SUNNY. That's so mean.")
    # test()
