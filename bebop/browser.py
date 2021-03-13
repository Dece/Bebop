"""Main browser logic."""

import curses
import curses.ascii
import curses.textpad
import os
from math import inf
from webbrowser import open_new_tab

from bebop.colors import ColorPair, init_colors
from bebop.command_line import (CommandLine, EscapeCommandInterrupt,
    TerminateCommandInterrupt)
from bebop.history import History
from bebop.links import Links
from bebop.mouse import ButtonState
from bebop.navigation import join_url, parse_url, sanitize_url, set_parameter
from bebop.page import Page
from bebop.protocol import Request, Response


class Browser:
    """Manage the events, inputs and rendering."""
    
    def __init__(self, cert_stash):
        self.stash = cert_stash or {}
        self.screen = None
        self.dim = (0, 0)
        self.page = None
        self.status_line = None
        self.command_line = None
        self.status_data = ("", 0, 0)
        self.current_url = ""
        self.running = True
        self.history = History()

    @property
    def h(self):
        return self.dim[0]

    @property
    def w(self):
        return self.dim[1]

    def run(self, *args, **kwargs):
        """Use curses' wrapper around _run."""
        os.environ.setdefault("ESCDELAY", "25")
        curses.wrapper(self._run, *args, **kwargs)

    def _run(self, stdscr, start_url=None):
        """Start displaying content and handling events."""
        self.screen = stdscr
        self.screen.clear()
        self.screen.refresh()

        curses.mousemask(curses.ALL_MOUSE_EVENTS)
        curses.curs_set(0)
        init_colors()

        self.dim = self.screen.getmaxyx()
        self.page = Page(self.h - 2)
        self.status_line = self.screen.subwin(
            *self.line_dim,
            *self.status_line_pos,
        )
        command_line_window = self.screen.subwin(
            *self.line_dim,
            *self.command_line_pos,
        )
        self.command_line = CommandLine(command_line_window)

        if start_url:
            self.open_url(start_url, assume_absolute=True)

        while self.running:
            try:
                self.handle_inputs()
            except KeyboardInterrupt:
                self.set_status("Cancelled.")

    def handle_inputs(self):
        char = self.screen.getch()
        if char == ord(":"):
            self.quick_command("")
        elif char == ord("r"):
            self.reload_page()
        elif char == ord("h"):
            self.scroll_page_horizontally(-3)
        elif char == ord("H"):
            pass  # TODO h-scroll whole page left
        elif char == ord("j"):
            self.scroll_page_vertically(3)
        elif char == ord("J"):
            self.scroll_whole_page_down()
        elif char == ord("k"):
            self.scroll_page_vertically(-3)
        elif char == ord("K"):
            self.scroll_whole_page_up()
        elif char == ord("l"):
            self.scroll_page_horizontally(3)
        elif char == ord("L"):
            pass  # TODO h-scroll whole page right
        elif char == ord("^"):
            pass # TODO reset horizontal scrolling
        elif char == ord("g"):
            char = self.screen.getch()
            if char == ord("g"):
                self.scroll_page_vertically(-inf)
        elif char == ord("G"):
            self.scroll_page_vertically(inf)
        elif char == ord("o"):
            self.quick_command("open")
        elif char == ord("p"):
            self.go_back()
        elif curses.ascii.isdigit(char):
            self.handle_digit_input(char)
        elif char == curses.KEY_MOUSE:
            self.handle_mouse(*curses.getmouse())
        elif char == curses.KEY_RESIZE:
            self.handle_resize()
        elif char == curses.ascii.ESC:  # Can be ESC or ALT char.
            self.screen.nodelay(True)
            char = self.screen.getch()
            if char == -1:
                self.set_status(self.current_url)
            else:  # ALT keybinds.
                if char == ord("h"):
                    self.scroll_page_horizontally(-1)
                elif char == ord("j"):
                    self.scroll_page_vertically(1)
                elif char == ord("k"):
                    self.scroll_page_vertically(-1)
                elif char == ord("l"):
                    self.scroll_page_horizontally(1)
            self.screen.nodelay(False)

        ctrl_char = curses.unctrl(char)
        if ctrl_char == "a":
            self.set_status("yup!")

    @property
    def page_pad_size(self):
        return self.h - 3, self.w - 1

    @property
    def status_line_pos(self):
        return self.h - 2, 0

    @property
    def command_line_pos(self):
        return self.h - 1, 0

    @property
    def line_dim(self):
        return 1, self.w

    def refresh_windows(self):
        """Refresh all windows and clear command line."""
        self.refresh_page()
        self.refresh_status_line()
        self.command_line.clear()

    def refresh_page(self):
        """Refresh the current page pad; it does not reload the page."""
        self.page.refresh_content(*self.page_pad_size)

    def refresh_status_line(self):
        """Refresh status line contents."""
        text, pair, attributes = self.status_data
        text = text[:self.w - 1]
        color = curses.color_pair(pair)
        self.status_line.addstr(0, 0, text, color | attributes)
        self.status_line.clrtoeol()
        self.status_line.refresh()

    def set_status(self, text):
        """Set a regular message in the status bar."""
        self.status_data = text, ColorPair.NORMAL, curses.A_ITALIC
        self.refresh_status_line()

    def set_status_error(self, text):
        """Set an error message in the status bar."""
        self.status_data = text, ColorPair.ERROR, 0
        self.refresh_status_line()

    def quick_command(self, command):
        """Shortcut method to take user input with a prefixed command string."""
        prefix = f"{command} " if command else ""
        user_input = self.command_line.focus(":", prefix=prefix)
        if not user_input:
            return
        self.process_command(user_input)

    def process_command(self, command_text: str):
        """Handle a client command."""
        words = command_text.split()
        num_words = len(words)
        if num_words == 0:
            return
        command = words[0]
        if num_words == 1:
            if command in ("q", "quit"):
                self.running = False
            return
        if command in ("o", "open"):
            self.open_url(words[1], assume_absolute=True)

    def open_url(self, url, base_url=None, redirects=0, assume_absolute=False):
        """Try to open an URL.

        This function assumes that the URL can be from an user and thus tries a
        few things to make it work.

        If there is no current URL (e.g. we just started) or `assume_absolute`
        is True, assume it is an absolute URL. In other cases, parse it normally
        and later check if it has to be used relatively to the current URL.
        
        Arguments:
        - url: an URL string, may not be completely compliant.
        - base_url: an URL string to use as base in case `url` is relative.
        - redirections: number of redirections we did yet for the same request.
        - assume_absolute: assume we intended to use an absolute URL if True.
        """
        if redirects > 5:
            self.set_status_error(f"Too many redirections ({url}).")
            return
        if assume_absolute or not self.current_url:
            parts = parse_url(url, absolute=True)
            join = False
        else:
            parts = parse_url(url)
            join = True
        if parts.scheme == "gemini":
            # If there is no netloc, this is a relative URL.
            if join or base_url:
                url = join_url(base_url or self.current_url, url)
            self.open_gemini_url(sanitize_url(url), redirects)
        elif parts.scheme.startswith("http"):
            self.open_web_url(url)
        elif parts.scheme == "file":
            self.open_file(parts.path)
        else:
            self.set_status_error(f"Protocol {parts.scheme} not supported.")

    def open_gemini_url(self, url, redirects=0, history=True):
        """Open a Gemini URL and set the formatted response as content.

        After initiating the connection, TODO
        """
        self.set_status(f"Loading {url}")
        req = Request(url, self.stash)
        connected = req.connect()
        if not connected:
            if req.state == Request.STATE_ERROR_CERT:
                error = f"Certificate was missing or corrupt ({url})."
                self.set_status_error(error)
            elif req.state == Request.STATE_UNTRUSTED_CERT:
                self.set_status_error(f"Certificate has been changed ({url}).")
                # TODO propose the user ways to handle this.
            elif req.state == Request.STATE_CONNECTION_FAILED:
                error = f": {req.error}" if req.error else "."
                self.set_status_error(f"Connection failed ({url}){error}")
            else:
                self.set_status_error(f"Connection failed ({url}).")
            return

        if req.state == Request.STATE_INVALID_CERT:
            # TODO propose abort / temp trust
            pass
        elif req.state == Request.STATE_UNKNOWN_CERT:
            # TODO propose abort / temp trust / perm trust
            pass
        else:
            pass # TODO

        data = req.proceed()
        if not data:
            self.set_status_error(f"Server did not respond in time ({url}).")
            return
        response = Response.parse(data)
        if not response:
            self.set_status_error(f"Server response parsing failed ({url}).")
            return

        if response.code == 20:
            self.load_page(response.content)
            if self.current_url and history:
                self.history.push(self.current_url)
            self.current_url = url
            self.set_status(url)
        elif response.generic_code == 30 and response.meta:
            self.open_url(response.meta, base_url=url, redirects=redirects + 1)
        elif response.generic_code in (40, 50):
            error = f"Server error: {response.meta or Response.code.name}"
            self.set_status_error(error)
        elif response.generic_code == 10:
            self.handle_input_request(url, response)
        else:
            error = f"Unhandled response code {response.code}"
            self.set_status_error(error)

    def load_page(self, gemtext: bytes):
        """Load Gemtext data as the current page."""
        old_pad_height = self.page.dim[0]
        self.page.show_gemtext(gemtext)
        if self.page.dim[0] < old_pad_height:
            self.screen.clear()
            self.screen.refresh()
            self.refresh_windows()
        else:
            self.refresh_page()

    def handle_digit_input(self, init_char: int):
        """Focus command-line to select the link ID to follow."""
        if not self.page or self.page.links is None:
            return
        links = self.page.links
        err, val = self.command_line.focus_for_link_navigation(init_char, links)
        if err == 0:
            self.open_link(links, val)  # type: ignore
        elif err == 2:
            self.set_status_error(val)

    def open_link(self, links: Links, link_id: int):
        """Open the link with this link ID."""
        if not link_id in links:
            self.set_status_error(f"Unknown link ID {link_id}.")
            return
        self.open_url(links[link_id])

    def handle_input_request(self, from_url: str, response: Response):
        """Focus command-line to pass input to the server."""
        if response.meta:
            self.set_status(f"Input needed: {response.meta}")
        else:
            self.set_status("Input needed:")
        user_input = self.command_line.focus("?")
        if user_input:
            url = set_parameter(from_url, user_input)
            self.open_gemini_url(url)

    def handle_mouse(self, mouse_id: int, x: int, y: int, z: int, bstate: int):
        """Handle mouse events.

        Right now, only vertical scrolling is handled.
        """
        if bstate & ButtonState.SCROLL_UP:
            self.scroll_page_vertically(-3)
        elif bstate & ButtonState.SCROLL_DOWN:
            self.scroll_page_vertically(3)

    def handle_resize(self):
        """Try to not make everything collapse on resizes."""
        # Refresh the whole screen before changing windows to avoid random
        # blank screens.
        self.screen.refresh()
        old_dim = self.dim
        self.dim = self.screen.getmaxyx()
        # Avoid work if the resizing does not impact us.
        if self.dim == old_dim:
            return
        # Resize windows to fit the new dimensions. Content pad will be updated
        # on its own at the end of the function.
        self.status_line.resize(*self.line_dim)
        self.command_line.window.resize(*self.line_dim)
        # Move the windows to their new position if that's still possible.
        if self.status_line_pos[0] >= 0:
            self.status_line.mvwin(*self.status_line_pos)
        if self.command_line_pos[0] >= 0:
            self.command_line.window.mvwin(*self.command_line_pos)
        # If the content pad does not fit its whole place, we have to clean the
        # gap between it and the status line. Refresh all screen.
        if self.page.dim[0] < self.h - 2:
            self.screen.clear()
            self.screen.refresh()
        self.refresh_windows()

    def scroll_page_vertically(self, by_lines):
        """Scroll page vertically.

        If `by_lines` is an integer (positive or negative), scroll the page by
        this amount of lines. If `by_lines` is one of the floats inf and -inf,
        go to the end of file and beginning of file, respectively.
        """
        window_height = self.h - 2
        require_refresh = False
        if by_lines == inf:
            require_refresh = self.page.go_to_end(window_height)
        elif by_lines == -inf:
            require_refresh = self.page.go_to_beginning()
        else:
            require_refresh = self.page.scroll_v(by_lines, window_height)
        if require_refresh:
            self.refresh_page()

    def scroll_whole_page_down(self):
        """Scroll down by a whole page."""
        self.scroll_page_vertically(self.page_pad_size[0])

    def scroll_whole_page_up(self):
        """Scroll up by a whole page."""
        self.scroll_page_vertically(-self.page_pad_size[0])

    def scroll_page_horizontally(self, by_columns):
        """Scroll page horizontally."""
        if self.page.scroll_h(by_columns, self.w):
            self.refresh_page()

    def reload_page(self):
        """Reload the page, if one has been previously loaded."""
        if self.current_url:
            self.open_gemini_url(self.current_url, history=False)

    def go_back(self):
        """Go back in history if possible."""
        if self.history.has_links():
            self.open_gemini_url(self.history.pop(), history=False)

    def open_web_url(self, url):
        """Open a Web URL. Currently relies in Python's webbrowser module."""
        self.set_status(f"Opening {url}")
        open_new_tab(url)

    def open_file(self, filepath):
        """Open a file and render it.

        This should be used only on Gemtext files or at least text files.
        Anything else will produce garbage and may crash the program.
        """
        try:
            with open(filepath, "rb") as f:
                self.load_page(f.read())
        except (OSError, ValueError) as exc:
            self.set_status_error(f"Failed to open file: {exc}")
