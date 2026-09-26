import time
import helper as unswbc
from strategy import decide_turn

ct: unswbc.Controller
game: unswbc.Game

def execute_turn() -> None:
    try:
        decide_turn(ct, game)
    except Exception as e:
        ct.output_log(f"V4 Failsafe triggered: {e}")
        ct.make_move(ct.get_dir())

def main() -> None:
    global ct, game
    ct, game = unswbc.init()

    while unswbc.update(ct, game):
        execute_turn()
        unswbc.end_turn()

if __name__ == "__main__":
    main()
