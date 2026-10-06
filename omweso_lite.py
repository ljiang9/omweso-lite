"""Omweso-lite: 简化版乌干达播棋 Omweso.

规则(简化, 非传统完整规则):
- 2x8 棋盘, 每坑开局 4 子, 共 64 子.
- 逆时针播种; 最后一子若落在播种前非空的坑, 则抓起该坑全部子继续播(接力/多圈).
- 最后一子落在自己一侧的空坑 -> 吃掉该子 + 对面坑全部子.
- 轮到一方而己侧无子可走, 或达到步数上限 -> 终局; 双方收回己侧残子,
  吃子 + 残子总数多者胜.
"""

import argparse
import copy
import random
import sys

PITS = 8            # 每侧坑数
POSITIONS = 16      # 总坑数
START_SEEDS = 4     # 开局每坑子数
MAX_HALF_MOVES = 600  # 防无限互绕


def own_positions(player):
    """玩家 0: 位置 0-7(南排左到右); 玩家 1: 位置 8-15(北排右到左)."""
    return range(0, 8) if player == 0 else range(8, 16)


def pit_to_pos(player, pit):
    """坑号 0..7(左到右) -> 播种环位置."""
    if not 0 <= pit < PITS:
        raise ValueError(f"坑号越界: {pit}")
    return pit if player == 0 else 15 - pit


def pos_to_pit(player, pos):
    return pos if player == 0 else 15 - pos


class Omweso:
    def __init__(self):
        self.board = [START_SEEDS] * POSITIONS
        self.captured = [0, 0]
        self.turn = 0
        self.n_moves = 0

    # ---- 走法(统一用坑号 0..7, 左到右) ----
    def legal_moves(self, player):
        return [pos_to_pit(player, p)
                for p in own_positions(player) if self.board[p] > 0]

    def apply_move(self, player, pit):
        """走一步, 返回 (吃子数, 接力次数). 非法走法抛 ValueError, 不改棋盘."""
        if player not in (0, 1):
            raise ValueError("玩家必须是 0 或 1")
        pos = pit_to_pos(player, pit)
        if self.board[pos] == 0:
            raise ValueError(f"空坑不能走: {pit}")
        # 先在副本上模拟, 保证非法时不改原棋盘(这里只有空坑一种非法, 已检查)
        hand = self.board[pos]
        self.board[pos] = 0
        last = pos
        relays = 0
        while True:
            while hand > 0:
                last = (last + 1) % POSITIONS
                self.board[last] += 1
                hand -= 1
            if self.board[last] == 1:
                break  # 落在空坑, 播种结束
            relays += 1
            if relays > 500:
                raise RuntimeError("接力次数异常, 终止防死循环")
            hand = self.board[last]
            self.board[last] = 0
        # 吃子: 最后一子落在自己一侧空坑
        captured = 0
        if last in own_positions(player):
            opp = POSITIONS - 1 - last
            captured = self.board[last] + self.board[opp]
            self.board[last] = 0
            self.board[opp] = 0
            self.captured[player] += captured
        self.turn = 1 - player
        self.n_moves += 1
        return captured, relays

    def total_seeds(self):
        return sum(self.board) + sum(self.captured)

    def is_over(self):
        return (not self.legal_moves(self.turn)) or self.n_moves >= MAX_HALF_MOVES

    def final_scores(self):
        """终局计分: 吃子 + 己侧残子."""
        scores = list(self.captured)
        for p in (0, 1):
            scores[p] += sum(self.board[pos] for pos in own_positions(p))
        return scores

    def winner(self):
        if not self.is_over():
            return None
        s = self.final_scores()
        if s[0] > s[1]:
            return 0
        if s[1] > s[0]:
            return 1
        return -1  # 和棋


# ---- AI ----
def ai_choose(game, player, rng):
    moves = game.legal_moves(player)
    if not moves:
        return None
    best, best_key = [], None
    for pit in moves:
        g = copy.deepcopy(game)
        captured, relays = g.apply_move(player, pit)
        key = (captured, relays)
        if best_key is None or key > best_key:
            best, best_key = [pit], key
        elif key == best_key:
            best.append(pit)
    return rng.choice(best)


# ---- 文本渲染 ----
def render(game):
    b = game.board
    # 北排(玩家1)按坑号左到右显示: 位置 15..8
    north = [b[15 - i] for i in range(PITS)]
    south = [b[i] for i in range(PITS)]
    lines = []
    lines.append("     " + " ".join(f"{i+1:>2}" for i in range(PITS)) + "   (坑号)")
    lines.append("北   " + " ".join(f"{n:>2}" for n in north) + f"   吃子:{game.captured[1]}")
    lines.append("南   " + " ".join(f"{s:>2}" for s in south) + f"   吃子:{game.captured[0]}")
    lines.append("     " + " ".join(f"{i+1:>2}" for i in range(PITS)))
    return "\n".join(lines)


# ---- 自动演示 ----
def play_auto(games, seed, verbose):
    rng = random.Random(seed)
    w0 = w1 = draws = 0
    for i in range(games):
        g = Omweso()
        while not g.is_over():
            pit = ai_choose(g, g.turn, rng)
            if pit is None:
                break
            g.apply_move(g.turn, pit)
        w = g.winner()
        if w == 0:
            w0 += 1
        elif w == 1:
            w1 += 1
        else:
            draws += 1
        if verbose:
            s = g.final_scores()
            print(f"第 {i+1}/{games} 局: {'南' if w == 0 else '北' if w == 1 else '和棋'}胜 ({s[0]}:{s[1]}, {g.n_moves} 半回合)")
    print(f"总计: 南胜 {w0}, 北胜 {w1}, 和棋 {draws}")
    return w0, w1, draws


# ---- 人机交互 ----
def play_interactive(seed):
    if not sys.stdin.isatty():
        print("交互模式需要终端; 无头演示请用 --auto", file=sys.stderr)
        sys.exit(2)
    rng = random.Random(seed)
    g = Omweso()
    print("Omweso-lite: 你是南(下排), 输入坑号 1-8 走子, q 退出")
    while not g.is_over():
        print(render(g))
        if g.turn == 0:
            try:
                s = input("你的走法(1-8): ").strip()
            except EOFError:
                break
            if s.lower() == "q":
                break
            try:
                pit = int(s) - 1
                cap, relays = g.apply_move(0, pit)
            except (ValueError, RuntimeError) as e:
                print(f"非法走法: {e}")
                continue
            if cap:
                print(f"吃子 +{cap}!")
        else:
            pit = ai_choose(g, 1, rng)
            if pit is None:
                break
            cap, relays = g.apply_move(1, pit)
            print(f"AI 走坑 {pit + 1}" + (f", 吃子 +{cap}" if cap else ""))
    print(render(g))
    s = g.final_scores()
    w = g.winner()
    print(f"终局 {s[0]}:{s[1]}, " + ("你胜!" if w == 0 else "AI 胜!" if w == 1 else "和棋"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Omweso-lite 简化版播棋")
    ap.add_argument("--auto", action="store_true", help="AI 对 AI 自动演示")
    ap.add_argument("--games", type=int, default=10, help="自动演示局数")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--verbose", action="store_true", help="自动演示打印每局")
    args = ap.parse_args(argv)
    if args.auto:
        play_auto(args.games, args.seed, args.verbose)
    else:
        play_interactive(args.seed)


if __name__ == "__main__":
    main()
