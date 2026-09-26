import time
import helper as unswbc
from strategy import decide_turn

ct: unswbc.Controller
game: unswbc.Game

def execute_turn() -> None:
    start_time = time.perf_counter()
    try:
        decide_turn(ct, game)
    except Exception as e:
        # Failsafe: in case of any unhandled exception, do not crash and suicide!
        # Always output a legal fallback move
        ct.output_log(f"Failsafe triggered: {e}")
        ct.make_move(ct.get_dir())

def main() -> None:
    global ct, game
    ct, game = unswbc.init()

    while unswbc.update(ct, game):
        execute_turn()
        unswbc.end_turn()

if __name__ == "__main__":
    main()
