#!/usr/bin/env python

# TODO: port this program to C
# dependencies: sudo apt-get install xdotool wmctrl

from __future__ import division

import subprocess
import re

maximized_prop_map = {
    "_NET_WM_STATE_MAXIMIZED_VERT": "maximized_vert",
    "_NET_WM_STATE_MAXIMIZED_HORZ": "maximized_horz",
}

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("direction", nargs="?", choices=["up", "left", "down", "right"])
    parser.add_argument("--dx", type=int)
    parser.add_argument("--dy", type=int)
    parser.add_argument("-w", "--torus", action="store_const", dest="wrap", const="torus",
        help="toroidal wrapping, i.e. wrapping x or y doesn't change the other")
    parser.add_argument("-s", "--spill-wrap", action="store_const", dest="wrap", const="spill",
        help="wrapping x increments y, like the flow of left-to-right text. y wraps toroidally.")
    parser.add_argument("-i", "--window", help="default is `xdotool getactivewindow`")
    args = parser.parse_args()

    wrap = args.wrap

    if args.direction == args.dx == args.dy == None:
        dx, dy = 1, 0
        if wrap == None:
            # no direction args
            wrap = "spill"
    else:
        dx = args.dx or 0
        dy = args.dy or 0
        if args.direction == "up":
            dy -= 1
        elif args.direction == "left":
            dx -= 1
        elif args.direction == "down":
            dy += 1
        elif args.direction == "right":
            dx += 1

    move_window_between_monitors(args.window, dx, dy, wrap)

def move_window_between_monitors(window_id, dx, dy, wrap):
    if dx == dy == 0:
        # you don't want to go anywhere
        return
    screen_width, screen_height = get_screen_size()
    display_width, display_height = get_display_size()
    num_displays_x = screen_width // display_width
    num_displays_y = screen_height // display_height
    if num_displays_x == num_displays_y == 1:
        # nowhere to go
        return

    if window_id == None:
        # default to active window
        window_id = subprocess.check_output(["xdotool", "getactivewindow"]).strip()
    x, y, window_width, window_height = get_window_rectangle(window_id)

    # this is the move (after we adjust dx,dy for wrapping)
    get_new_x = lambda: x + dx * display_width
    get_new_y = lambda: y + dy * display_height

    # handle wrapping
    is_off_screen_right  = lambda: dx > 0 and get_new_x() >= screen_width
    is_off_screen_left   = lambda: dx < 0 and get_new_x() + window_width < 0
    is_off_screen_bottom = lambda: dy > 0 and get_new_y() >= screen_height
    is_off_screen_top    = lambda: dy < 0 and get_new_y() + window_height < 0
    if wrap == None:
        # bring the window back into view
        while is_off_screen_right():
            dx -= 1
        while is_off_screen_left():
            dx += 1
        while is_off_screen_bottom():
            dy -= 1
        while is_off_screen_top():
            dy += 1
    elif wrap == "torus":
        # each axis wraps individually
        while is_off_screen_right():
            dx -= num_displays_x
        while is_off_screen_left():
            dx += num_displays_x
        while is_off_screen_bottom():
            dy -= num_displays_y
        while is_off_screen_top():
            dy += num_displays_y
    elif wrap == "spill":
        # wrapping x increments y, like the flow of left-to-right text.
        # y wraps toroidally.
        while is_off_screen_right():
            dx -= num_displays_x
            dy += 1
        while is_off_screen_left():
            dx += num_displays_x
            dy -= 1
        while is_off_screen_bottom():
            dy -= num_displays_y
        while is_off_screen_top():
            dy += num_displays_y
    else: assert False

    if dx == dy == 0:
        # wrapping causes us to remain put
        return

    window_state_props = get_window_state(window_id)
    maximized_props = [maximized_prop_map[prop] for prop in window_state_props if prop in maximized_prop_map]
    if len(maximized_props) > 0:
        # unmaximize for two reasons:
        # * if the window is completely maximized, it can't be moved.
        # * if the window is going to a display with a different height/width
        #     (possibly due to a task bar), re-apply the maximization props to fill the new space.
        subprocess.check_call(["wmctrl", "-ir", window_id, "-b", "remove," + ",".join(maximized_props)])

    subprocess.check_call(["xdotool", "windowmove", window_id, str(get_new_x()), str(get_new_y())])
    subprocess.check_call(["xdotool", "windowsize", window_id, str(window_width), str(window_height)])

    if len(maximized_props) > 0:
        # after resizing, restore maximized properties
        subprocess.check_call(["wmctrl", "-ir", window_id, "-b", "add," + ",".join(maximized_props)])

def get_window_state(window_id):
    line = subprocess.check_output(["xprop", "-id", window_id, "_NET_WM_STATE"]).strip()
    # _NET_WM_STATE(ATOM) = _NET_WM_STATE_MAXIMIZED_HORZ, _NET_WM_STATE_MAXIMIZED_VERT, _NET_WM_STATE_FOCUSED
    return [prop.strip() for prop in line.split("=")[1].split(",")]

def get_window_rectangle(window_id):
    xwininfo_output = subprocess.check_output(["xwininfo", "-id", window_id])
    # "  Absolute upper-left X:  1992"
    window_info = dict((s.strip() for s in line.split(":")) for line in xwininfo_output.split("\n") if len(line.split(":")) == 2)
    # the "Absolute" location is where the content of the window starts relative to the screen
    inner_x = int(window_info["Absolute upper-left X"])
    inner_y = int(window_info["Absolute upper-left Y"])
    # the "Relative" location is where the content of the window starts relative to the window's title bar
    relative_x = int(window_info["Relative upper-left X"])
    relative_y = int(window_info["Relative upper-left Y"])
    # this is the location of the window's title bar, which is all we care about
    x = inner_x - relative_x
    y = inner_y - relative_y
    # this size includes the title bar and borders
    width  = int(window_info["Width"])
    height = int(window_info["Height"])
    return (x, y, width, height)

def get_screen_size():
    xdpyinfo_output = subprocess.check_output(["xdpyinfo"])
    # "  dimensions:    3840x1080 pixels (1016x286 millimeters)"
    match = re.search(r"^\s*dimensions:\s*(\d+)x(\d+)\s+pixels", xdpyinfo_output, re.MULTILINE)
    return (int(match.group(1)), int(match.group(2)))

def get_display_size():
    return tuple(int(s) for s in subprocess.check_output(["xdotool", "getdisplaygeometry"]).split())

if __name__ == "__main__":
    main()
