# main.py
import curses
from player import PlayerState
from ui import TUI

def main(stdscr):
    player = PlayerState()
    tui = TUI(stdscr, player)
    tui.start()

if __name__ == "__main__":
    curses.wrapper(main)
