"""Metalines generation.

In Bebop we use a list of elements as produced by our parser. These elements are
converted into so-called "metalines", which are the text lines as they will be
displayed, along with associated meta-data such as its type or a link's URL.

Note that metalines can be generated by custom functions without relying on the
elements classes as they are quite coupled to Gemtext parsing/rendering.

The metalines are tuples (ltype, line, lextra):
- ltype is the LineType.
- line is the text content itself.
- lextra is either a dict of additional data, or None.

The lextra part is currently only used for links, and can contain the following
keys:
- url: the URL the link on this line refers to. Note that this key is present
  only for the first line of the link, i.e. long link descriptions wrapped on
  multiple lines will not have a this key except for the first line.
- link_id: only alongside "url" key, ID generated for this link.
"""

import string
from dataclasses import dataclass
from enum import IntEnum
from typing import List

from bebop.gemtext import (
    Blockquote, Link, ListItem, Paragraph, Preformatted, Title)


SPLIT_CHARS = " \t-"
JOIN_CHAR = "-"


class LineType(IntEnum):
    """Type of line.

    Keep lines type along with the content for later rendering.
    Title type values match the title level to avoid looking it up.
    """
    NONE = 0
    TITLE_1 = 1
    TITLE_2 = 2
    TITLE_3 = 3
    PARAGRAPH = 4
    LINK = 5
    PREFORMATTED = 6
    BLOCKQUOTE = 7
    LIST_ITEM = 8
    ERROR = 9  # Not part of Gemtext but useful internally.


RENDER_MODES = ("fancy", "dumb")


@dataclass
class RenderOptions:
    """Rendering options."""
    width: int
    mode: str
    bullet: str


def generate_metalines(elements: list, options: RenderOptions) -> list:
    """Format elements into a list of lines with metadata.

    Arguments:
    - elements: list of elements to use.
    - options: RenderOptions to respect when generating metalines.
    """
    metalines = []
    separator = (LineType.NONE, "", None)
    has_margins = False
    thin_type = None
    for index, element in enumerate(elements):
        previous_had_margins = has_margins
        last_thin_type = thin_type
        has_margins = False
        thin_type = None
        if isinstance(element, Title):
            element_metalines = format_title(element, options)
            has_margins = True
        elif isinstance(element, Paragraph):
            element_metalines = format_paragraph(element, options)
            has_margins = True
        elif isinstance(element, Link):
            element_metalines = format_link(element, options)
            thin_type = LineType.LINK
        elif isinstance(element, Preformatted):
            element_metalines = format_preformatted(element, options)
            has_margins = True
        elif isinstance(element, Blockquote):
            element_metalines = format_blockquote(element, options)
            has_margins = True
        elif isinstance(element, ListItem):
            element_metalines = format_list_item(element, options)
            thin_type = LineType.LIST_ITEM
        else:
            continue
        # In dumb mode, elements producing no metalines still need to be
        # rendered as empty lines.
        if options.mode == "dumb":
            if not element_metalines:
                element_metalines = [(LineType.PARAGRAPH, "", None)]
        # If current element requires margins and is not the first elements,
        # separate from previous element. Also do it if the current element does
        # not require margins but follows an element that required it (e.g. link
        # after a paragraph). Also do it if both the current and previous
        # elements do not require margins but differ in type.
        elif (
            (has_margins and index > 0)
            or (not has_margins and previous_had_margins)
            or (not has_margins and thin_type != last_thin_type)
        ):
            metalines.append(separator)
        # Append the element metalines now.
        metalines += element_metalines
    return metalines


def generate_dumb_metalines(lines):
    """Generate dumb metalines: all lines are given the PARAGRAPH line type."""
    return [(LineType.PARAGRAPH, line, None) for line in lines]


def format_title(title: Title, options: RenderOptions):
    """Return metalines for this title."""
    width = options.width
    if title.level == 1:
        wrapped = wrap_words(title.text, width)
        line_template = f"{{:^{width}}}"
        lines = (line_template.format(line) for line in wrapped)
    else:
        if title.level == 2:
            lines = wrap_words(title.text, width, indent=2)
        else:
            lines = wrap_words(title.text, width)
    # Title levels match the type constants of titles.
    return [(LineType(title.level), line, None) for line in lines]


def format_paragraph(paragraph: Paragraph, options: RenderOptions):
    """Return metalines for this paragraph."""
    lines = wrap_words(paragraph.text, options.width)
    return [(LineType.PARAGRAPH, line, None) for line in lines]


def format_link(link: Link, options: RenderOptions):
    """Return metalines for this link."""
    # Get a new link and build the "[id]" anchor.
    link_anchor = f"[{link.ident}] "
    link_text = link.text or link.url
    # Wrap lines, indented by the link anchor length.
    lines = wrap_words(link_text, options.width, indent=len(link_anchor))
    first_line_extra = {
        "url": link.url,
        "link_id": link.ident
    }
    # Replace first line indentation with the anchor.
    first_line_text = link_anchor + lines[0][len(link_anchor):]
    first_line = [(LineType.LINK, first_line_text, first_line_extra)]
    other_lines = [(LineType.LINK, line, None) for line in lines[1:]]
    return first_line + other_lines  # type: ignore


def format_preformatted(preformatted: Preformatted, options: RenderOptions):
    """Return metalines for this preformatted block."""
    return [(LineType.PREFORMATTED, line, None) for line in preformatted.lines]


def format_blockquote(blockquote: Blockquote, options: RenderOptions):
    """Return metalines for this blockquote."""
    lines = wrap_words(blockquote.text, options.width, indent=2)
    return [(LineType.BLOCKQUOTE, line, None) for line in lines]


def format_list_item(item: ListItem, options: RenderOptions):
    """Return metalines for this list item."""
    indent = len(options.bullet)
    lines = wrap_words(item.text, options.width, indent=indent)
    first_line = options.bullet + lines[0][indent:]
    lines[0] = first_line
    return [(LineType.LIST_ITEM, line, None) for line in lines]


def wrap_words(text: str, width: int, indent: int =0) -> List[str]:
    """Wrap a text in several lines according to the renderer's width."""
    lines = []
    line = " " * indent
    words = _explode_words(text)
    for word in words:
        line_len, word_len = len(line), len(word)
        # If adding the new word would overflow the line, use a new line.
        if line_len + word_len > width:
            # Push only non-empty lines.
            if line_len > 0:
                lines.append(line)
                line = " " * indent
            # Force split words that are longer than the width.
            while word_len > width:
                split_offset = width - 1 - indent
                word_line = " " * indent + word[:split_offset] + JOIN_CHAR
                lines.append(word_line)
                word = word[split_offset:]
                word_len = len(word)
            word = word.lstrip()
        line += word
    if line:
        lines.append(line)
    return lines


def _explode_words(text: str) -> List[str]:
    """Split a string into a list of words."""
    words = []
    pos = 0
    while True:
        sep, sep_index = _find_next_sep(text[pos:])
        if not sep:
            words.append(text[pos:])
            return words
        word = text[pos : pos + sep_index]
        # If the separator is not a space char, append it to the word.
        if sep in string.whitespace:
            words.append(word)
            words.append(sep)
        else:
            words.append(word + sep)
        pos += sep_index + 1


def _find_next_sep(text: str):
    """Find the next separator index and return both the separator and index."""
    indices = []
    for sep in SPLIT_CHARS:
        try:
            indices.append((sep, text.index(sep)))
        except ValueError:
            pass
    if not indices:
        return ("", 0)
    return min(indices, key=lambda e: e[1])
