#!/usr/bin/env python3

# Textboxer: a python script/lib for making custom textboxes that look like they are from games
# Made by TheLastKumquat
# Licensed under MIT

import json
import math
import sys

from copy import deepcopy

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

from pathlib import Path

debug_mode = False
resource_root: Path = Path("resources")
resolve_with_paths = False


def debug(text):
    if debug_mode:
        print(text)


def resolve_next_with_path():
    global resolve_with_paths
    resolve_with_paths = True


def resolve_resource(base: Path, key: str) -> Path | None:
    global resolve_with_paths
    if resolve_with_paths and (base / key).exists():
        resolve_with_paths = False
        return base / key

    if (base / "alias.json").exists():
        alias_file = (base / "alias.json").open()
        aliases = json.load(alias_file)
        alias_file.close()
        if key in aliases:
            return base / aliases[key]

    return None


def paste_alpha(base: Image.Image, overlay: Image.Image, offset: tuple = (0, 0)) -> Image.Image:
    padded_overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    padded_overlay.paste(overlay, offset)
    return Image.alpha_composite(base, padded_overlay)


def get_filter(imgfilter: str, default: int = Image.NEAREST):
    match imgfilter.lower():
        case "bilinear":
            return Image.BILINEAR
        case "bicubic":
            return Image.BICUBIC
        case "box":
            return Image.BOX
        case "lanczos":
            return Image.LANCZOS
        case "hamming":
            return Image.HAMMING
        case "nearest":
            return Image.NEAREST
        case _:
            return default


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
        textwidth = draw.multiline_textsize(textcut, font)[0]
        if textwidth < maxwidth:
            textout += textcut
            break

        # binary search for the longest substring that can fit in the designated width
        startpos = 0
        endpos = len(textcut)
        last_below = 0
        for i in range(0, math.floor(math.log2(len(textcut)) + 1)):
            curpos = (len(textcut[startpos:endpos]) // 2) + startpos
            textwidth = draw.multiline_textsize(textcut[:curpos], font)[0]

            # some of this debug info is just wrong and i cant be bothered to fix it, since the search works correctly
            debug("began binary search iteration " + str(i + 1) + " of " + str(math.floor(math.log2(len(textcut)) + 1))
                  + " with bounds " + str(startpos) + ":" + str(endpos)
                  + " and position " + str(curpos) + "/" + str(len(textcut) - 1))
            debug("search region: " + textcut[startpos - 1:endpos])
            debug("test region:   " + textcut[:curpos])
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

        # break at the nearest space instead of the found position, if possible
        breakpos = textcut.rfind(" ", 0, last_below + 1)
        if breakpos == -1 or break_on_any:
            textout += textcut[:last_below] + "\n"
            textcut = textcut[last_below:]
        else:
            textout += textcut[:breakpos] + "\n"
            textcut = textcut[breakpos + 1:]

    return textout


def evaluate_predicate(predicate_state: dict[str, list], predicate: str) -> bool:
    for part in predicate.split("&"):
        if part == "always":
            continue
        if part == "parse":
            debug("Ignoring 'parse' predicate: it should have already been loaded")
            return False
        invert = part.startswith("!")
        if invert:
            part = part[1:]
        mid = part.find(":")
        if part[:mid] not in predicate_state:
            return True
        if (part[mid + 1:] not in predicate_state[part[:mid]]) != invert:
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


def parse_jsons(predicate_state: dict, sorts: dict[int, list]) -> dict[str]:
    output = {}

    for sort_value in sorted(sorts.keys()):
        debug("loading sort value " + str(sort_value))
        for data in sorts[sort_value]:
            if evaluate_predicate(predicate_state, data["predicate"]):
                output = merge_dicts(output, data)

    del output["sort"]
    del output["predicate"]
    return output


def resolve_jsons(predicate_state: dict, data_paths: list[Path]) -> dict[str]:
    return parse_jsons(predicate_state, load_jsons(data_paths)[0])


def apply_override(predicate_state: dict, data: dict, override: dict) -> dict:
    debug(data)
    for part in override:
        if evaluate_predicate(predicate_state, override[part]["predicate"]):
            debug("applying override " + part)
            del override[part]["predicate"]
            data = merge_dicts(data, override[part])
    return data


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
    # x y
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
    # w h
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


def parsestr(textin: str = "", *, out: str = None, presplit: list[str] = None):
    args = textin.split(" ") if presplit is None else presplit
    style = None
    text = {}
    images = {}
    flags = []
    mode = "default"
    setpredicates = None
    default_data = resource_root / "default" / "data"
    style_root = resource_root / "styles"

    # find the style to use
    if (style_root / args[0]).exists():
        style = args[0]
        del args[0]
    if style is None:
        # need to load just the default parse data to get the default style, could be cached but effort
        _, preload = load_jsons(list(default_data.rglob("*.json")))
        style = preload["defaultstyle"]

    if args[0].startswith("m:"):
        mode = args[0][2:]
        del args[0]

    style_data = style_root / style / "data"
    sorts, preload = load_jsons(list(default_data.rglob("*.json")) + list(style_data.rglob("*.json")))

    while args[0].startswith("f:"):
        flags.append(args[0][2:])
        del args[0]

    if mode in preload:
        strkey = preload[mode]["str"]
        if "setpredicates" in preload[mode]:
            setpredicates = {}
            for predicate in preload[mode]["setpredicates"]:
                mid = predicate.find(":")
                if predicate[:mid] not in setpredicates:
                    setpredicates[predicate[:mid]] = []
                setpredicates[predicate[:mid]].append(predicate[mid + 1:])
    else:
        strkey = preload["str"]

    for argdesc in strkey:
        key, value = argdesc.split(":")
        match key:
            case "text":
                if args[0] != "!NONE!":
                    text[value] = args[0]
                del args[0]
            case "image":
                if args[0] != "!NONE!":
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

    generate(style, text, images, flags, mode, preload_data=sorts, out=out, add_predicates=setpredicates)


def parsestrlist(args: list[str], *, style: str = None, text: dict[str, str] = None,
                 images: dict[str, str] = None, flags: list[str] = None, out: str = None):
    if text is None:
        text = {}
    if images is None:
        images = {}
    if flags is None:
        flags = []
    default_data = resource_root / "default" / "data"
    style_root = resource_root / "styles"

    # find the style to use
    if (style_root / args[0]).exists():
        style = args[0]
        del args[0]
    if style is None:
        # need to load just the default parse data to get the default style, could be cached but effort
        _, preload = load_jsons(list(default_data.rglob("*.json")))
        style = preload["defaultstyle"]

    style_data = style_root / style / "data"
    sorts, preload = load_jsons(list(default_data.rglob("*.json")) + list(style_data.rglob("*.json")))

    for argdesc in preload["args"]:
        key, value = argdesc.split(":")
        match key:
            case "text":
                if args[0] != "!NONE!":
                    text[value] = args[0]
                del args[0]
            case "image":
                if args[0] != "!NONE!":
                    images[value] = args[0]
                del args[0]
        if len(args) <= 0:
            break

    for remaining in args:
        flags.append(remaining)

    generate(style, text, images, flags, preload_data=sorts, out=out)


def generate(style: str, text: dict[str, str], images: dict[str, str] = None, flags: list[str] = None,
             mode: str = "default", *, out: str = None, preload_data: dict[int, list] = None,
             add_predicates: dict[str, list] = None):
    predicate_state = {
        "textbox": list(text) if text is not None else [],
        "image": list(images) if images is not None else [],
        "flag": flags if flags is not None else [],
        "mode": [mode]
    }
    if add_predicates is not None:
        for category in add_predicates:
            predicate_state[category].extend(add_predicates[category])

    debug(predicate_state)
    default_data = resource_root / "default" / "data"
    style_dir = resource_root / "styles" / style
    style_data = style_dir / "data"

    if preload_data is not None:
        data = parse_jsons(predicate_state, preload_data)
    else:
        data = resolve_jsons(predicate_state, list(default_data.rglob("*.json")) + list(style_data.rglob("*.json")))
    debug(data)

    # resolve font files
    font_data = {}
    for fontname in data["fonts"]:
        if isinstance(data["fonts"][fontname], dict):
            font_data[fontname] = deepcopy(data["fonts"][fontname])
            if "bitmap" in font_data[fontname]:
                font_data[fontname]["resolved"] = ImageFont.load(
                    style_dir / data["fonts"]["basepath"] / font_data[fontname]["bitmap"]
                )
            else:
                fontfile = (style_dir / data["fonts"]["basepath"] / font_data[fontname]["path"]).open("rb")
                font_data[fontname]["resolved"] = ImageFont.truetype(fontfile, font_data[fontname]["size"])
                fontfile.close()

    # apply image overrides and resolve dynamic image paths
    imagenames = []
    for imagename in data["images"]:
        imagenames.append(imagename)
    for imagename in imagenames:
        if isinstance(data["images"][imagename], dict):
            imagepath = style_dir / data["images"]["basepath"]
            if data["images"][imagename]["type"] == "dynamic":
                debug("resolving " + imagename)
                imgbasepath = imagepath / data["images"][imagename]["pathprefix"]
                data["images"][imagename]["resolvedpath"] = resolve_resource(imgbasepath, images[imagename])
                overridepath = imgbasepath / "overrides.json"
                debug(overridepath)
                if overridepath.exists() and imgbasepath.is_relative_to(data["images"][imagename]["resolvedpath"]):
                    imgrel = data["images"][imagename]["resolvedpath"].relative_to(imgbasepath)
                    overridefile = overridepath.open()
                    overrides = json.load(overridefile)
                    overridefile.close()
                    if str(imgrel) in overrides:
                        overridepath = imgbasepath / overrides[str(imgrel)]
                        overridefile = overridepath.open()
                        override = json.load(overridefile)
                        overridefile.close()
                        debug("loading overrides for " + imgrel.name)
                        data = apply_override(predicate_state, data, override)

    # preload some textbox data
    # dummy canvas
    canvas = ImageDraw.Draw(Image.new("RGBA", (1000, 1000), (0, 0, 0, 0)))
    default_fontmode = canvas.fontmode
    textbox_data = {}
    for textboxname in data["textboxes"]:
        if isinstance(data["textboxes"][textboxname], dict):

            canvas.fontmode = default_fontmode
            textbox = data["textboxes"][textboxname]

            # short-circuit if the data is already there, because it was calculated for
            #   a textbox that either inherits from it or a textbox it inherits from.
            # but only do this if the relevant parameters are equal
            if "inherittext" in textbox:
                inheritname = textbox["inherittext"]
                text[textboxname] = text[inheritname]
                if inheritname in textbox_data:
                    if textbox_data[inheritname]["font"] == textbox["font"] \
                            and textbox_data[inheritname]["max_width"] == textbox["max_width"] \
                            and textbox_data[inheritname]["max_lines"] == textbox["max_lines"] \
                            and textbox_data[inheritname]["line_wrap"] == textbox["line_wrap"]:
                        textbox_data[textboxname] = textbox_data[inheritname]
                        continue

            if textboxname in textbox_data:
                if textbox_data[textboxname]["font"] == textbox["font"] \
                        and textbox_data[textboxname]["max_width"] == textbox["max_width"] \
                        and textbox_data[textboxname]["max_lines"] == textbox["max_lines"] \
                        and textbox_data[textboxname]["line_wrap"] == textbox["line_wrap"]:
                    continue

            textbox_data[textboxname] = textbox
            font = font_data[textbox["font"]]
            if not font["antialias"]:
                canvas.fontmode = "1"
            text_wrapped = wrap_text(text[textboxname], textbox["max_width"], font["resolved"], canvas)

            lines = text_wrapped.count("\n") + 1
            if lines > textbox["max_lines"] and textbox["line_wrap"] == "cut":
                text_wrapped = text_wrapped[:find_nth(text_wrapped, "\n", textbox["max_lines"])]

            textbox_data[textboxname]["text"] = text_wrapped
            textbox_data[textboxname]["size"] = canvas.multiline_textsize(text_wrapped,
                                                                          spacing=font["spacing"],
                                                                          font=font["resolved"])

            if "inherittext" in textbox and textbox["inherittext"] not in textbox_data:
                textbox_data[textbox["inherittext"]] = textbox
                textbox_data[textbox["inherittext"]]["text"] = textbox_data[textboxname]["text"]
                textbox_data[textbox["inherittext"]]["size"] = textbox_data[textboxname]["size"]

    # resolve image files
    image_data = {}
    for imagename in data["images"]:
        if isinstance(data["images"][imagename], dict):
            imagepath = style_dir / data["images"]["basepath"]
            image_data[imagename] = {}

            match data["images"][imagename]["type"]:
                case "static":
                    image_data[imagename]["resolved"] = Image.open(imagepath / data["images"][imagename]["path"])
                case "dynamic":
                    image_data[imagename]["resolved"] = Image.open(data["images"][imagename]["resolvedpath"])
                case "expand":
                    # image divided into 9 regions, corners stay static
                    # edges and center are stretched out to fit designated width/height
                    match data["images"][imagename]["mode"]:
                        case "static":
                            image_data[imagename]["resolved"] = create_expand(
                                imagepath / data["images"][imagename]["path"], data["images"][imagename]
                            )
                        case "textbox":
                            tboxname = data["images"][imagename]["textbox"]
                            if "x" in data["images"][imagename]["bind_axes"]:
                                data["images"][imagename]["size"][0] = \
                                    textbox_data[tboxname]["size"][0] + data["images"][imagename]["sizemod"][0]
                            if "y" in data["images"][imagename]["bind_axes"]:
                                data["images"][imagename]["size"][1] = \
                                    textbox_data[tboxname]["size"][1] + data["images"][imagename]["sizemod"][1]
                            image_data[imagename]["resolved"] = create_expand(
                                imagepath / data["images"][imagename]["path"], data["images"][imagename]
                            )
            if "scaleto" in data["images"][imagename]:
                imgfilter = Image.BILINEAR
                if "scalefilter" in data["images"][imagename]:
                    imgfilter = get_filter(data["images"][imagename]["scalefilter"], Image.BILINEAR)
                image_data[imagename]["resolved"] = image_data[imagename]["resolved"].resize(
                    data["images"][imagename]["scaleto"], imgfilter)
    debug(font_data)
    debug(image_data)
    debug(data)

    composite = None
    if "basesize" in data["images"]:
        composite = Image.new("RGBA", data["images"]["basesize"], (0, 0, 0, 0))
    for imagename in image_data:
        image = image_data[imagename]
        if composite is None:
            composite = image["resolved"].copy()
            continue
        composite = paste_alpha(composite, image["resolved"], data["images"][imagename]["position"])

    canvas = ImageDraw.Draw(composite)
    default_fontmode = canvas.fontmode
    for textboxname in data["textboxes"]:
        if isinstance(data["textboxes"][textboxname], dict):
            canvas.fontmode = default_fontmode
            textbox = data["textboxes"][textboxname]
            font = font_data[textbox["font"]]
            fill = tuple(textbox["color"]) if "color" in textbox else None
            if not font["antialias"]:
                canvas.fontmode = "1"

            # use preloaded wrapped text, if applicable
            if textbox_data[textboxname]["font"] == textbox["font"] \
                    and textbox_data[textboxname]["max_width"] == textbox["max_width"] \
                    and textbox_data[textboxname]["max_lines"] == textbox["max_lines"] \
                    and textbox_data[textboxname]["line_wrap"] == textbox["line_wrap"]:
                text_wrapped = textbox_data[textboxname]["text"]
            else:
                text_wrapped = wrap_text(text[textboxname], textbox["max_width"], font["resolved"], canvas)

                lines = text_wrapped.count("\n") + 1
                if lines > textbox["max_lines"] and textbox["line_wrap"] == "cut":
                    text_wrapped = text_wrapped[:find_nth(text_wrapped, "\n", textbox["max_lines"])]

            anchortype = None
            align = "left"

            if "anchortype" in textbox:
                anchortype = textbox["anchortype"]
            if "align" in textbox:
                align = textbox["align"]

            canvas.multiline_text(textbox["anchor"],
                                  text_wrapped,
                                  spacing=font["spacing"],
                                  font=font["resolved"],
                                  fill=fill,
                                  anchor=anchortype,
                                  align=align)

    if "postscale" in data:
        cursize = composite.size
        postscale = data["postscale"]
        imgfilter = Image.NEAREST
        if "scalefilter" in data:
            imgfilter = get_filter(data["scalefilter"])
        composite = composite.resize((int(cursize[0] * postscale[0]), int(cursize[1] * postscale[1])), imgfilter)

    if out is not None:
        composite.save(out)
        return
    composite.show()


def gen_help() -> str:
    output = "Available styles: "
    stylelist = []
    longest_style = 0
    default_data = resource_root / "default" / "data"

    for style in (resource_root / "styles").iterdir():
        if (style / "data").exists():
            stylelist.append(style.name)
            output += style.name + ", "
            if len(style.name) > longest_style:
                longest_style = len(style.name)
    output = output[:output.rfind(", ")]

    output += "\nDefault style: "
    _, preload = load_jsons(list(default_data.rglob("*.json")))
    output += preload["defaultstyle"]

    output += "\nStyle options:"
    flags = {}
    for style in stylelist:
        style_data = resource_root / "styles" / style / "data"
        sorts, preload = load_jsons(list(style_data.rglob("*.json")))
        output += "\n" + style.ljust(longest_style + 3)
        for arg in preload["str"]:
            key, value = arg.split(":")
            match key:
                case "text":
                    output += " <text (1 word or quoted): " + value + ">"
                case "image":
                    output += " <image: " + value + ">"
                case "textfill":
                    output += " <text (rest of message): " + value + ">"

        flags[style] = set()
        for sortvalue in sorts:
            for data in sorts[sortvalue]:
                for part in data["predicate"].split("&"):
                    if part == "always":
                        continue
                    if part == "parse":
                        break
                    if part.startswith("flag"):
                        mid = part.find(":")
                        flags[style].add(part[mid + 1:])

    output += "\n1 word text and image parameters can be set to nothing by passing !NONE! instead of a value"

    output += "\nAvailable flags:"
    for style in flags:
        output += "\n" + style.ljust(longest_style + 3)
        for flag in flags[style]:
            output += " " + flag
        if len(flags[style]) == 0:
            output += " (no flags)"

    return output


def find_aliases(stylein: str = None, search: str = "") -> str:
    stylelist = []
    output = ""

    if stylein is None:
        for style in (resource_root / "styles").iterdir():
            if (style / "data").exists():
                stylelist.append(style.name)
    else:
        stylelist.append(stylein)

    for style in stylelist:
        output += style
        for aliasfilepath in (resource_root / "styles" / style).rglob("alias.json"):
            for pathpart in aliasfilepath.relative_to(resource_root / "styles" / style).parts:
                output += " / " + pathpart
            output += "\n"
            aliasfile = aliasfilepath.open()
            aliases = json.load(aliasfile)
            aliasfile.close()

            for alias in aliases:
                if search in alias:
                    output += alias + "\n"

    # trim trailing newline
    output = output[:-1]

    return output


def get_image(style: str, image: str) -> Path | None:
    for aliasfilepath in (resource_root / "styles" / style).rglob("alias.json"):
        if resolved := resolve_resource(aliasfilepath.parent, image):
            return resolved
    return None


if __name__ == '__main__':
    debug_mode = True
    if len(sys.argv) > 1:
        parsestr("", presplit=sys.argv[1:])
        exit(0)
    # generate("omori", {"main": "I hope you're having a great day!", "name": "MARI"}, {"face": "mari_happy"})
    # generate("oneshot", {"main": "mhm yep uh huh yeah got it mhm great yeah uh huh okay"}, {"face": "af"})
    # generate("omori", {"main": "I am... a gift for you... DREAMER.", "name": "ABBI"}, flags=["scared"])
    # generate("omori", {"main": "He remains the DREAMER's favorite even to this day... watching diligently... waiting for something to happen.", "name": "BRANCH CORAL"})
    # parsestrlist(["The way is blocked... by blocks!"])
    # parsestrlist(["omori", "How is it march already", "BASIL", "basil_flower_stare"])
    # parsestr("omori f:scared BASIL basil_dark_flower_cry That's mean, SUNNY. That's so mean.")
    # generate("oneshot", {"main": "My rams clock at 1333 megaherds."}, {"face": "shepherd"})
    # generate("omori", {"main": "Hi, OMORI! Cliff-faced as usual, I see.\nYou should totally smile more! I've always liked your smile.", "name": "MARI"}, {"face": "mari_dw_smile2"})
    # parsestr("omori MARI mari_dw_smile2 Hi, OMORI! Cliff-faced as usual, I see.\nYou should totally smile more! I've always liked your smile.")
    # generate("lennas-inception", {"main": "town. If you're needin' to upgrade ya arsenal, I'm ya bear!", "name": "Rupert"})
    # parsestr(presplit=["lennas-inception", "f:gothicname", "Archangel Lenna", "archangellenna", "Come out and show yourself, coward!"])
    # parsestr("lennas-inception f:smallcaps Telephone misc_default 1 file attachment(s). Open attachment?")
    # parsestr("oneshot en_huh ...yeah let's get outta here.")
    parsestr("celeste madeline_normal00 Oh... I'm just passing through.\nI'm climbing the Mountain.")
    # print(gen_help())
    # print(find_aliases(search="sad"))
    # print(get_image("oneshot", "af"))
