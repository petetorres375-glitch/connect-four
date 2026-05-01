import random

class ConnectFour:
    def __init__(self):
        self.board = [[None for _ in range(7)] for _ in range(6)]
        self.current_player = "Red"
        self.winner = None
        self.winning_cells = []  # NEW: stores the 4 winning (row, col) pairs

    def drop_piece(self, col):
        if self.winner or col < 0 or col > 6:
            return None

        for row in reversed(range(6)):
            if self.board[row][col] is None:
                self.board[row][col] = self.current_player

                cells = self.check_winner(row, col)
                if cells:
                    self.winner = self.current_player
                    self.winning_cells = cells

                last_player = self.current_player
                if not self.winner:
                    self.current_player = "Yellow" if self.current_player == "Red" else "Red"
                return {
                    "row": row,
                    "col": col,
                    "player": last_player,
                    "winner": self.winner,
                    "winning_cells": self.winning_cells  # NEW
                }

        return None

    def check_winner(self, r, c):
        """Returns list of 4 winning (row,col) tuples, or empty list if no win."""
        player = self.board[r][c]
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        for dr, dc in directions:
            cells = [(r, c)]
            for delta in [1, -1]:
                nr, nc = r + dr * delta, c + dc * delta
                while 0 <= nr < 6 and 0 <= nc < 7 and self.board[nr][nc] == player:
                    cells.append((nr, nc))
                    nr += dr * delta
                    nc += dc * delta
            if len(cells) >= 4:
                return cells[:4]
        return []

    def get_valid_columns(self):
        return [c for c in range(7) if self.board[0][c] is None]

    def get_ai_move(self, level):
        valid_cols = self.get_valid_columns()
        if not valid_cols:
            return None

        if level == "easy":
            return random.choice(valid_cols)

        if level == "medium":
            for player in ["Yellow", "Red"]:
                for col in valid_cols:
                    row = self._get_next_open_row(col)
                    if row is not None:
                        self.board[row][col] = player
                        if self.check_winner(row, col):
                            self.board[row][col] = None
                            return col
                        self.board[row][col] = None
            return random.choice(valid_cols)

        if level == "hard":
            _, best_col = self._minimax(self.board, 5, True, float('-inf'), float('inf'))
            return best_col if best_col is not None else random.choice(valid_cols)

        return random.choice(valid_cols)

    def _get_next_open_row(self, col):
        for r in reversed(range(6)):
            if self.board[r][col] is None:
                return r
        return None

    def _score_window(self, window, player):
        opponent = "Red" if player == "Yellow" else "Yellow"
        score = 0
        if window.count(player) == 4:
            score += 100
        elif window.count(player) == 3 and window.count(None) == 1:
            score += 5
        elif window.count(player) == 2 and window.count(None) == 2:
            score += 2
        if window.count(opponent) == 3 and window.count(None) == 1:
            score -= 4
        return score

    def _score_board(self, board, player):
        score = 0
        center_col = [board[r][3] for r in range(6)]
        score += center_col.count(player) * 3
        for r in range(6):
            for c in range(4):
                score += self._score_window([board[r][c+i] for i in range(4)], player)
        for c in range(7):
            for r in range(3):
                score += self._score_window([board[r+i][c] for i in range(4)], player)
        for r in range(3, 6):
            for c in range(4):
                score += self._score_window([board[r-i][c+i] for i in range(4)], player)
        for r in range(3):
            for c in range(4):
                score += self._score_window([board[r+i][c+i] for i in range(4)], player)
        return score

    def _check_board_winner(self, board, player):
        for r in range(6):
            for c in range(4):
                if all(board[r][c+i] == player for i in range(4)):
                    return True
        for c in range(7):
            for r in range(3):
                if all(board[r+i][c] == player for i in range(4)):
                    return True
        for r in range(3, 6):
            for c in range(4):
                if all(board[r-i][c+i] == player for i in range(4)):
                    return True
        for r in range(3):
            for c in range(4):
                if all(board[r+i][c+i] == player for i in range(4)):
                    return True
        return False

    def _minimax(self, board, depth, maximizing, alpha, beta):
        valid_cols = [c for c in range(7) if board[0][c] is None]
        if self._check_board_winner(board, "Yellow"):
            return (1000000 + depth, None)
        if self._check_board_winner(board, "Red"):
            return (-1000000 - depth, None)
        if not valid_cols or depth == 0:
            return (self._score_board(board, "Yellow"), None)

        best_col = random.choice(valid_cols)
        if maximizing:
            best_score = float('-inf')
            for col in valid_cols:
                row = next(r for r in reversed(range(6)) if board[r][col] is None)
                board[row][col] = "Yellow"
                score, _ = self._minimax(board, depth-1, False, alpha, beta)
                board[row][col] = None
                if score > best_score:
                    best_score, best_col = score, col
                alpha = max(alpha, score)
                if alpha >= beta:
                    break
            return best_score, best_col
        else:
            best_score = float('inf')
            for col in valid_cols:
                row = next(r for r in reversed(range(6)) if board[r][col] is None)
                board[row][col] = "Red"
                score, _ = self._minimax(board, depth-1, True, alpha, beta)
                board[row][col] = None
                if score < best_score:
                    best_score, best_col = score, col
                beta = min(beta, score)
                if alpha >= beta:
                    break
            return best_score, best_col

    def reset(self):
        self.__init__()
