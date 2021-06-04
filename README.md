Bebop
=====

Bebop is a [Gemini][gemini] browser for the terminal, focusing on practicality
and laziness. It is a personal project to learn how to use ncurses and try new
ways to explore the Geminispace. It borrows some ideas from [Amfora][amfora],
another great terminal browser, Vim for interactivity and tries to support mouse
usage decently.

[gemini]: https://gemini.circumlunar.space/
[amfora]: https://github.com/makeworld-the-better-one/amfora

If you are interested in Gemini and looking for a desktop/laptop client, I
recommend trying a graphical one like the excellent [Lagrange][lagrange] or
[Kristall][kristall], or Amfora if you're feeling more at home in the terminal.
Bebop won't attempt to support every feature other clients might have, but if
you want to try something a bit different, keep reading…

[lagrange]: https://git.skyjake.fi/skyjake/lagrange
[kristall]: https://kristall.random-projects.net/

Screenshots:

![welcome screenshot](https://files.dece.space/img/bebop/bebop-welcome.png)
![browsing Medusae screenshot](https://files.dece.space/img/bebop/bebop-medusae.png)
![browsing Spacewalk screenshot](https://files.dece.space/img/bebop/bebop-spacewalk.png)

The changelog is in the annotated tags.



Features
--------

Why use Bebop instead of something else?

- Lightweight, no external Python dependencies.
- Nice keybinds are defined, and Vim users should get quickly familiar with
    them.
- Fun! Link navigation is done by entering the link ID with automatic
    validation so you can just smash your numpad to take your ship to unknown
    places (see usage section below for details).
- History, cache, client certificates, bookmarks (it's just a text file with
    bindings), downloads and more!



Install
-------

You need Python 3.7 or more recent. If you don't know what Python is or if you
have it installed, check out this Gemini link `gemini://dece.space/dev/faq/using-python-programs.gmi` ([Web version][py-faq-http]).

[py-faq-http]: https://portal.mozz.us/gemini/dece.space/dev/faq/using-python-programs.gmi

The easier installation method is using Pip, either user or system-wide
installation:

```bash
# User installation:
pip3 install --user bebop-browser
# System-wide installation:
sudo pip3 install bebop-browser
```

To update:

```bash
# User update:
pip3 install --user --upgrade bebop-browser
# System-wide update:
sudo pip3 install --upgrade bebop-browser
```

Note that you can also simply clone this repo and use `python3 -m bebop` to run
from the source instead of installing it.

Now for platform specific info…

### Linux

Linux is the main platform I can test so you should be good to go, and don't
hesitate to report issues.

### BSD

I don't know! Let me know your experience with it if you did try it.

### macOS

It should work on macOS like on other UNIX-like systems. I have limited access
to devices running macOS so cross your fingers… The main difference I've seen is
that some keys may behave a bit differently and that text attributes such as
italics or dim may not work.

### Windows

Bebop relies heavily on ncurses to display its content to the terminal, and it
does not work great on Windows. You need to install the curses support
separately as most Python distributions on Windows do not have it: the package
`windows-curses` on PyPI seems to work here.

Seems like there is no color support out of the box nor text attributes. It
works OK in cmd.exe, but it feels completely broken on Windows Terminal.



Usage
-----

Just run `bebop`, optionally following by an URL (`bebop -h` to see options). I
have it aliased to "bop" but that is up to you.

Documentation about the keybinds, config values and commands are embed into the
software itself: press "?" to display the help page.

The first thing you will want to get used to is the link navigation. All links
have an ID written before them and you press the corresponding number to access
it. If there are less than 10 links on a page, pressing the link ID will take
you to the page directly. If there are 30 links, pressing "1" will wait for
another digit. If there are 1000 links but you wish to visit link 5, pressing 5
and enter will do.

There is an FAQ at `gemini://dece.space/dev/bebop.gmi`.

Happy browsing!



About
-----

Licensed under GPLv3.

Name comes from [this song][bop] which is good background music for browsing
Gemini. Oh and Cowboy Bebop.

[bop]: https://www.youtube.com/watch?v=tWyUYAmmtNg
