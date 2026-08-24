import streamlit as st
import chess
import chess.pgn
import chess.engine
import chess.svg
import chess.polyglot
from io import StringIO, BytesIO
import random
import pathlib
import os
import cairosvg
from PIL import Image
import imageio
import tempfile

st.set_page_config(
    layout="wide",
    initial_sidebar_state="expanded",
    page_title="Chesalyser",
    page_icon="logos/small.png",
)


def svg_to_png(svg_string, size=400):
    """Convert SVG string to PNG image using cairosvg"""
    png_data = cairosvg.svg2png(bytestring=svg_string.encode('utf-8'), output_width=size, output_height=size)
    return Image.open(BytesIO(png_data))

def detect_game_phase(board, move_number):
    """Detect the current phase of the game: opening, middlegame, or endgame"""
    material_count = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            material_count += 1
    
    # Phase detection based on material and move number
    if material_count > 28 or move_number < 10:
        return "opening"
    elif material_count > 16 or move_number < 25:
        return "middlegame"
    else:
        return "endgame"

def get_player_strength(game):
    """Extract player strength from PGN headers"""
    try:
        white_elo = int(game.headers.get('WhiteElo', 1200))
        black_elo = int(game.headers.get('BlackElo', 1200))
        avg_elo = (white_elo + black_elo) / 2
        return avg_elo
    except (ValueError, TypeError):
        return 1500  # Default to intermediate level

def get_strength_multiplier(avg_elo):
    """Get strength multiplier based on player rating"""
    if avg_elo < 1200:
        return 1.5  # More lenient for beginners
    elif avg_elo < 1400:
        return 1.3
    elif avg_elo < 1600:
        return 1.1
    elif avg_elo < 1800:
        return 1.0  # Standard
    elif avg_elo < 2000:
        return 0.9  # Stricter for strong players
    elif avg_elo < 2200:
        return 0.8
    else:
        return 0.7  # Very strict for masters

def get_phase_thresholds(game_phase, strength_multiplier):
    """Get dynamic thresholds based on game phase and player strength"""
    base_thresholds = {
        "opening": {
            "best": 5,
            "brilliant": 15,
            "great": 30,
            "excellent": 60,
            "good": 100,
            "inaccuracy": 180,
            "mistake": 300,
        },
        "middlegame": {
            "best": 8,
            "brilliant": 20,
            "great": 40,
            "excellent": 80,
            "good": 130,
            "inaccuracy": 220,
            "mistake": 350,
        },
        "endgame": {
            "best": 3,
            "brilliant": 10,
            "great": 25,
            "excellent": 50,
            "good": 90,
            "inaccuracy": 150,
            "mistake": 250,
        }
    }
    
    # Apply strength multiplier
    thresholds = base_thresholds[game_phase].copy()
    for key in thresholds:
        thresholds[key] = int(thresholds[key] * strength_multiplier)
    
    return thresholds

def classify_move_enhanced(score_change, is_capture=False, moved_piece=None, 
                          game_phase="middlegame", avg_elo=1500):
    """Enhanced move classification with context-aware thresholds"""
    
    # Get strength multiplier
    strength_multiplier = get_strength_multiplier(avg_elo)
    
    # Get phase-specific thresholds
    thresholds = get_phase_thresholds(game_phase, strength_multiplier)
    
    # Adjust for captures (slightly more lenient)
    if is_capture:
        for key in thresholds:
            thresholds[key] = int(thresholds[key] * 1.2)
    
    # Adjust for queen moves (more critical)
    if moved_piece == chess.QUEEN:
        for key in thresholds:
            thresholds[key] = int(thresholds[key] * 0.9)
    
    # Classify based on adjusted thresholds
    if score_change < thresholds["best"]:
        return "Best", "#00ff00"
    elif score_change < thresholds["brilliant"]:
        return "Brilliant", "#ff00ff"
    elif score_change < thresholds["great"]:
        return "Great", "#00ffff"
    elif score_change < thresholds["excellent"]:
        return "Excellent", "#00bfff"
    elif score_change < thresholds["good"]:
        return "Good", "#0000ff"
    elif score_change < thresholds["inaccuracy"]:
        return "Inaccuracy", "#ffff00"
    elif score_change < thresholds["mistake"]:
        return "Mistake", "#ff8800"
    else:
        return "Blunder", "#ff0000"

# Keep old function for backward compatibility
def classify_move(score_change, is_capture=False, moved_piece=None):
    return classify_move_enhanced(score_change, is_capture, moved_piece, "middlegame", 1500)

def get_stockfish_path(custom_path=None):
    """Use existing local Stockfish or fallback to default path"""
    if custom_path and pathlib.Path(custom_path).exists():
        return custom_path
    
    # Try existing local Stockfish first (container path first for Docker)
    existing_paths = [
        "stockfish/stockfish",  # Docker container path
        "stockfish/stockfish/stockfish-ubuntu-x86-64-sse41-popcnt",
        "stockfish_binary/stockfish-ubuntu-x86-64-modern",
        "stockfish/stockfish-ubuntu-x86-64-sse41-popcnt",
    ]
    
    for path in existing_paths:
        if pathlib.Path(path).exists():
            return path
    
    # Return None if no valid path found
    return None

def get_opening_book_path(custom_path=None):
    """Get opening book path from settings or use default"""
    if custom_path and pathlib.Path(custom_path).exists():
        return custom_path
    
    # Try common opening book paths
    existing_paths = [
        "opening_books/varied.bin",
        "opening_books/performance.bin",
        "opening_books/book.bin",
        "books/varied.bin",
        "books/performance.bin",
    ]
    
    for path in existing_paths:
        if pathlib.Path(path).exists():
            return path
    
    return None

class OpeningBookManager:
    """Manages opening book operations for chess analysis"""
    
    def __init__(self, book_path=None):
        self.book_path = book_path
        self.book_reader = None
        self._load_book()
    
    def _load_book(self):
        """Load the opening book if path is valid"""
        if self.book_path and pathlib.Path(self.book_path).exists():
            try:
                self.book_reader = chess.polyglot.open_reader(self.book_path)
            except Exception as e:
                st.warning(f"Could not load opening book: {str(e)}")
                self.book_reader = None
    
    def is_book_move(self, board, move):
        """Check if a move is in the opening book"""
        if not self.book_reader:
            return False, None
        
        try:
            # Find all entries for this position
            entries = list(self.book_reader.find_all(board))
            if not entries:
                return False, None
            
            # Check if the played move is in the book
            book_moves = [entry.move for entry in entries]
            if move in book_moves:
                # Get the weight of this move
                for entry in entries:
                    if entry.move == move:
                        return True, entry.weight
                return True, 0
            return False, None
        except Exception:
            return False, None
    
    def get_best_book_move(self, board):
        """Get the highest-weighted book move for a position"""
        if not self.book_reader:
            return None, None
        
        try:
            entry = self.book_reader.find(board)
            if entry:
                return entry.move, entry.weight
            return None, None
        except Exception:
            return None, None
    
    def get_all_book_moves(self, board):
        """Get all book moves for a position with their weights"""
        if not self.book_reader:
            return []
        
        try:
            entries = list(self.book_reader.find_all(board))
            return [(entry.move, entry.weight) for entry in entries]
        except Exception:
            return []
    
    def close(self):
        """Close the book reader"""
        if self.book_reader:
            self.book_reader.close()
            self.book_reader = None

def detect_opening_name(moves):
    """Simple opening detection based on first few moves"""
    move_sequence = " ".join(moves[:6])  # First 6 moves (3 each)
    
    # Common openings (simplified detection)
    openings = {
        "Sicilian Defense": ["e2e4", "c7c5"],
        "French Defense": ["e2e4", "e7e6"],
        "Caro-Kann": ["e2e4", "c7c6"],
        "Queen's Gambit": ["d2d4", "d7d5", "c2c4"],
        "King's Indian": ["d2d4", "g8f6", "c2c4", "g7g6"],
        "Dutch Defense": ["d2d4", "f7f5"],
        "Ruy Lopez": ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"],
        "Italian Game": ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4"],
        "Scotch Game": ["e2e4", "e7e5", "g1f3", "b8c6", "d2d4"],
        "Vienna Game": ["e2e4", "e7e5", "b1c3"],
        "Four Knights": ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6"],
        "English Opening": ["c2c4"],
        "Reti Opening": ["g1f3", "c2c4"],
        "Nimzo-Indian": ["d2d4", "g8f6", "c2c4", "e7e6", "b1c3", "f8b4"],
        "Queen's Indian": ["d2d4", "g8f6", "c2c4", "e7e6", "g2g3"],
        "Grünfeld Defense": ["d2d4", "g8f6", "c2c4", "d7d5"],
        "Benoni Defense": ["d2d4", "g8f6", "c2c4", "c7c5"],
        "Alekhine's Defense": ["e2e4", "g8f6"],
        "Pirc Defense": ["e2e4", "d7d6", "d2d4", "g8f6"],
        "Modern Defense": ["e2e4", "g7g6"],
        "Scandinavian Defense": ["e2e4", "d7d5"],
        "Philidor Defense": ["e2e4", "e7e5", "g1f3", "d7d6"],
    }
    
    for opening, pattern in openings.items():
        if all(move in move_sequence for move in pattern):
            return opening
    
    # Default detection based on first move
    if moves and moves[0] == "e2e4":
        return "Open Game (1.e4)"
    elif moves and moves[0] == "d2d4":
        return "Closed Game (1.d4)"
    elif moves and moves[0] == "c2c4":
        return "English Opening"
    elif moves and moves[0] == "g1f3":
        return "Réti Opening"
    
    return "Unknown Opening"

def detect_pin(board, square):
    """Detect if a piece at square is pinned"""
    piece = board.piece_at(square)
    if not piece:
        return False, None
    
    # Get the king of the same color
    king_square = board.king(piece.color)
    if king_square is None:
        return False, None
    
    # Check if the piece is on the same line as the king
    if not (chess.square_rank(square) == chess.square_rank(king_square) or 
            chess.square_file(square) == chess.square_file(king_square) or
            (chess.square_rank(square) - chess.square_file(square)) == (chess.square_rank(king_square) - chess.square_file(king_square)) or
            (chess.square_rank(square) + chess.square_file(square)) == (chess.square_rank(king_square) + chess.square_file(king_square))):
        return False, None
    
    # Check if there's an enemy piece that can attack along this line
    for attacker_square in chess.SQUARES:
        attacker = board.piece_at(attacker_square)
        if attacker and attacker.color != piece.color:
            # Check if attacker can see the king through this piece
            if board.is_attacked_by(attacker.color, king_square):
                # Check if the piece is between attacker and king
                between_squares = list(chess.SquareSet.between(attacker_square, king_square))
                if square in between_squares:
                    return True, attacker_square
    
    return False, None

def detect_fork(board, move):
    """Detect if a move creates a fork (attacking two or more valuable pieces)"""
    temp_board = board.copy()
    temp_board.push(move)
    
    piece = temp_board.piece_at(move.to_square)
    if not piece:
        return False, []
    
    attacked_pieces = []
    
    # Check all squares the piece attacks
    for target_square in temp_board.attacks(move.to_square):
        target_piece = temp_board.piece_at(target_square)
        if target_piece and target_piece.color != piece.color:
            # Only count valuable pieces (not pawns)
            if target_piece.piece_type != chess.PAWN:
                attacked_pieces.append(target_square)
    
    # A fork attacks at least 2 valuable pieces
    if len(attacked_pieces) >= 2:
        return True, attacked_pieces
    
    return False, []

def detect_skewer(board, move):
    """Detect if a move creates a skewer (forcing a valuable piece to move, exposing a less valuable one)"""
    temp_board = board.copy()
    temp_board.push(move)
    
    piece = temp_board.piece_at(move.to_square)
    if not piece:
        return False, None, None
    
    # Check for skewer pattern along lines
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    
    for dx, dy in directions:
        # Look for pieces along this line
        pieces_on_line = []
        current_square = move.to_square
        
        for _ in range(8):
            current_file = chess.square_file(current_square) + dx
            current_rank = chess.square_rank(current_square) + dy
            
            if 0 <= current_file < 8 and 0 <= current_rank < 8:
                next_square = chess.square(current_file, current_rank)
                target_piece = temp_board.piece_at(next_square)
                
                if target_piece:
                    pieces_on_line.append((next_square, target_piece))
                    if len(pieces_on_line) >= 2:
                        break
                current_square = next_square
            else:
                break
        
        # Check if we found a skewer pattern (valuable piece in front of less valuable one)
        if len(pieces_on_line) >= 2:
            front_piece = pieces_on_line[0]
            back_piece = pieces_on_line[1]
            
            if (front_piece[1].color != piece.color and 
                back_piece[1].color != piece.color and
                front_piece[1].piece_type > back_piece[1].piece_type):
                return True, front_piece[0], back_piece[0]
    
    return False, None, None

def detect_discovered_attack(board, move):
    """Detect if a move creates a discovered attack"""
    temp_board = board.copy()
    temp_board.push(move)
    
    # Check if any piece now has a new line of attack
    for square in chess.SQUARES:
        piece = temp_board.piece_at(square)
        if piece and piece.color == temp_board.turn:
            # Check if this piece's attacks increased significantly
            attacks_before = set(board.attacks(square)) if board.piece_at(square) else set()
            attacks_after = set(temp_board.attacks(square))
            
            new_attacks = attacks_after - attacks_before
            
            # Check if new attacks hit enemy pieces
            for target in new_attacks:
                target_piece = temp_board.piece_at(target)
                if target_piece and target_piece.color != piece.color:
                    return True, square, target
    
    return False, None, None

def detect_double_attack(board, move):
    """Detect if a move attacks two pieces simultaneously"""
    temp_board = board.copy()
    temp_board.push(move)
    
    piece = temp_board.piece_at(move.to_square)
    if not piece:
        return False, []
    
    attacked_pieces = []
    
    for target_square in temp_board.attacks(move.to_square):
        target_piece = temp_board.piece_at(target_square)
        if target_piece and target_piece.color != piece.color:
            attacked_pieces.append(target_square)
    
    if len(attacked_pieces) >= 2:
        return True, attacked_pieces
    
    return False, []

def detect_hanging_piece(board, move):
    """Detect if a move leaves a piece hanging (undefended)"""
    temp_board = board.copy()
    temp_board.push(move)
    
    # Check if the moved piece is now undefended
    moved_piece = temp_board.piece_at(move.to_square)
    if not moved_piece:
        return False, None
    
    # Check if it's attacked by enemy
    is_attacked = temp_board.is_attacked_by(not moved_piece.color, move.to_square)
    
    # Check if it's defended by own pieces
    is_defended = temp_board.is_attacked_by(moved_piece.color, move.to_square)
    
    if is_attacked and not is_defended:
        return True, move.to_square
    
    return False, None

def detect_sacrifice(board, move, material_before):
    """Detect if a move sacrifices material"""
    temp_board = board.copy()
    temp_board.push(move)
    
    material_after = calculate_material(temp_board)
    
    # If material decreased significantly, it might be a sacrifice
    if material_after < material_before - 1:  # Lost more than a pawn
        return True, material_before - material_after
    
    return False, 0

def calculate_material(board):
    """Calculate total material value on the board"""
    piece_values = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
        chess.KING: 0
    }
    
    total = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            total += piece_values[piece.piece_type]
    
    return total

def analyze_tactics(board, move):
    """Analyze a move for tactical motifs"""
    tactics = []
    
    # Check for various tactical motifs
    is_fork, fork_targets = detect_fork(board, move)
    if is_fork:
        tactics.append({
            "type": "fork",
            "description": f"Fork attacking {len(fork_targets)} pieces",
            "severity": "high"
        })
    
    is_skewer, front, back = detect_skewer(board, move)
    if is_skewer:
        front_piece = board.piece_type_at(front) if front else None
        tactics.append({
            "type": "skewer",
            "description": f"Skewer forcing {chess.piece_name(front_piece) if front_piece else 'piece'} to move",
            "severity": "high"
        })
    
    is_discovered, attacker, target = detect_discovered_attack(board, move)
    if is_discovered:
        attacker_piece = board.piece_type_at(attacker) if attacker else None
        tactics.append({
            "type": "discovered_attack",
            "description": f"Discovered attack with {chess.piece_name(attacker_piece) if attacker_piece else 'piece'}",
            "severity": "medium"
        })
    
    is_double, targets = detect_double_attack(board, move)
    if is_double:
        tactics.append({
            "type": "double_attack",
            "description": f"Double attack on {len(targets)} pieces",
            "severity": "medium"
        })
    
    is_hanging, square = detect_hanging_piece(board, move)
    if is_hanging:
        tactics.append({
            "type": "hanging_piece",
            "description": f"Left piece hanging on {chess.square_name(square)}",
            "severity": "high"
        })
    
    # Check for pin on the moved piece
    is_pinned, pin_attacker = detect_pin(board, move.to_square)
    if is_pinned:
        tactics.append({
            "type": "pin",
            "description": f"Piece pinned by {chess.piece_name(board.piece_type_at(pin_attacker))}",
            "severity": "medium"
        })
    
    return tactics

def analyze_game(game, depth, engine_path=None, book_path=None):
    engine_path = get_stockfish_path(engine_path)
    if not engine_path:
        st.error("Stockfish engine not found. Please check the engine path in settings.")
        return []
    
    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    except Exception as e:
        st.error(f"Stockfish initialization error: {str(e)}")
        return []
    
    # Initialize opening book manager
    book_path = get_opening_book_path(book_path)
    book_manager = OpeningBookManager(book_path) if book_path else None
    
    # Get player strength for enhanced classification
    avg_elo = get_player_strength(game)
    
    analysis_results = []
    board = game.board()
    moves_played = []
    in_book_phase = True
    book_exit_move = None

    previous_eval = None

    for move_index, move in enumerate(game.mainline_moves()):
        try:
            is_capture = board.is_capture(move)

            from_square = move.from_square
            moved_piece = board.piece_type_at(from_square)

            current_position = board.copy()

            # Check if move is in opening book
            is_book_move = False
            book_weight = None
            if book_manager and in_book_phase:
                is_book_move, book_weight = book_manager.is_book_move(current_position, move)
                if not is_book_move:
                    in_book_phase = False
                    book_exit_move = move_index + 1

            board.push(move)
            moves_played.append(move.uci())

            side_to_move = not board.turn

            info = engine.analyse(board, chess.engine.Limit(depth=depth))
            current_eval = info["score"].white().score(mate_score=10000)

            if previous_eval is None:
                score_change = 0
            else:
                if side_to_move:  # White just moved
                    score_change = previous_eval - current_eval
                else:  # Black just moved
                    score_change = current_eval - previous_eval

                score_change = abs(score_change)

            previous_eval = current_eval

            win_probability = 1 / (1 + 10 ** (-current_eval / 400))

            # Detect game phase for enhanced classification
            game_phase = detect_game_phase(board, move_index)
            
            # Use enhanced classification with context
            move_quality, color = classify_move_enhanced(
                score_change, is_capture, moved_piece, game_phase, avg_elo
            )

            best_move_info = engine.analyse(current_position, chess.engine.Limit(depth=depth))
            pv = best_move_info.get("pv", [])
            best_move = pv[0] if pv else None

            # Analyze tactics for this move
            tactics = analyze_tactics(current_position, move)

            analysis_results.append({
                "move": move.uci(),
                "score": round(win_probability, 3),
                "centipawn_eval": current_eval,
                "best_move": best_move.uci() if best_move else "None",
                "score_change": round(score_change, 1),
                "quality": move_quality,
                "color": color,
                "is_capture": is_capture,
                "piece_moved": chess.piece_name(moved_piece) if moved_piece else "None",
                "is_book_move": is_book_move,
                "book_weight": book_weight,
                "game_phase": game_phase,
                "tactics": tactics,
            })
        except Exception as e:
            st.error(f"Error analyzing move {move_index + 1}: {str(e)}")
            continue

    engine.quit()
    if book_manager:
        book_manager.close()
    
    # Detect opening name
    opening_name = detect_opening_name(moves_played)
    
    # Calculate book accuracy
    book_moves = sum(1 for result in analysis_results if result["is_book_move"])
    total_moves = len(analysis_results)
    book_accuracy = (book_moves / total_moves * 100) if total_moves > 0 else 0
    
    # Calculate tactical statistics
    tactic_counts = {}
    total_tactics = 0
    for result in analysis_results:
        for tactic in result.get("tactics", []):
            tactic_type = tactic["type"]
            tactic_counts[tactic_type] = tactic_counts.get(tactic_type, 0) + 1
            total_tactics += 1
    
    # Add summary information
    return {
        "moves": analysis_results,
        "opening_name": opening_name,
        "book_accuracy": round(book_accuracy, 1),
        "book_exit_move": book_exit_move,
        "total_book_moves": book_moves,
        "avg_elo": round(avg_elo),
        "tactic_counts": tactic_counts,
        "total_tactics": total_tactics,
    }


def main():
    st.logo("logos/big.png", icon_image="logos/small.png")
    file_path = pathlib.Path("style.css")
    with open(file_path) as f:
        st.html(f"<style>{f.read()}</style>")
    
    # Initialize dark mode in session state
    if "dark_mode" not in st.session_state:
        st.session_state.dark_mode = True

    st.title(":material/chess_pawn: Just Chess Analyzer")

    st.markdown("<hr style='margin: 0px 0px 30px 0px;'>", unsafe_allow_html=True)

    with st.sidebar:
        st.markdown(
            "<div style='background-image: linear-gradient(to top right, #00f0ff, #0e6fff, #8f5bff); border-radius: 8px'><h1 style='text-align: center; padding: 10px; margin: 0px 0px 15px 0px; font-weight: 700;'>⚙ SETTINGS</h1></div>",
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            engine_path = st.text_input(
                ":material/conversion_path: Stockfish Engine Path",
                value="stockfish/stockfish/stockfish-ubuntu-x86-64-sse41-popcnt",
                help="Paste your Stockfish engine path here."
            )

        with st.container(border=True):
            book_path = st.text_input(
                ":material/menu_book: Opening Book Path",
                value="opening_books/varied.bin",
                help="Path to Polyglot opening book (.bin file). Leave empty to disable opening analysis."
            )

        with st.container(border=True):
            pgn_file = st.file_uploader(":material/upload: Upload PGN file", type="pgn")
            pgn_text = st.text_area(
                ":material/content_paste: Or paste PGN text here",
                height=200,
                key="pgn_input",
                placeholder="Paste your PGN game here..."
            )

        with st.container(border=True):
            # Dark mode toggle
            dark_mode = st.toggle(
                ":material/dark_mode: Dark Mode",
                value=st.session_state.dark_mode,
                key="dark_mode_toggle"
            )
            if dark_mode != st.session_state.dark_mode:
                st.session_state.dark_mode = dark_mode
                st.rerun()

            # Force the correct theme attribute on every run
            theme = "dark" if st.session_state.dark_mode else "light"
            st.markdown(
                f"""
                <script>
                    // Set theme on the root elements
                    const root = window.parent.document.querySelector('html') || document.documentElement;
                    root.setAttribute('data-theme', '{theme}');
                    
                    // Also set on body and app container for maximum compatibility
                    document.body.setAttribute('data-theme', '{theme}');
                    const app = window.parent.document.querySelector('[data-testid="stApp"]') || 
                               document.querySelector('[data-testid="stApp"]');
                    if (app) app.setAttribute('data-theme', '{theme}');
                </script>
                """,
                unsafe_allow_html=True
            )

        with st.container(border=True):
            # Depth selection with cheeky phrases
            depth_options = {
                10: "Beginner mode",
                15: "Casual mode",
                20: "Serious mode",
                25: "Grandmaster mode",
                30: "Stockfish mode",
                35: "Super GM mode",
                40: "Engine mode",
                45: "Deep analysis",
                50: "Maximum depth",
            }
            depth = st.selectbox(
                ":material/settings: Select Analysis Depth:",
                options=list(depth_options.keys()),
                format_func=lambda x: depth_options[x],
            )

    if pgn_file or pgn_text:
        try:
            pgn = StringIO(pgn_text if pgn_text else pgn_file.getvalue().decode())
            game = chess.pgn.read_game(pgn)

            if game is None:
                st.error("Invalid PGN file or text. Please check the format.")
                return

            with st.sidebar:
                if st.button(
                    ":material/neurology: ANALYZE GAME",
                    use_container_width=True,
                    key="agame",
                ):
                    messages = [
                        "Thinking like Magnus Carlsen...",
                        "Calculating the best blunder... just kidding!",
                        "Running Stockfish at full speed!",
                        "Searching for the brilliancy move!",
                        "Did you just play a Bongcloud opening? Let's see...",
                        "Analyzing faster than Hikaru can pre-move!",
                        "Determining if this was a 200 IQ move or a disaster...",
                        "Checking if this game belongs in the Hall of Fame or Shame!",
                    ]
                    with st.spinner(random.choice(messages)):
                        st.session_state.analysis = analyze_game(
                            game, depth, engine_path, book_path
                        )
                        st.session_state.num_moves = len(st.session_state.analysis["moves"])

            if "analysis" in st.session_state and len(st.session_state.analysis["moves"]) > 0:
                if "current_move" not in st.session_state:
                    st.session_state.current_move = 0

                slider = st.session_state.current_move
                board = game.board()
                for i in range(slider + 1):
                    board.push(
                        chess.Move.from_uci(st.session_state.analysis["moves"][i]["move"])
                    )

                # Chess board at the top
                with st.container(border=True):
                    if "board_flipped" not in st.session_state:
                        st.session_state.board_flipped = False
                    orientation = chess.BLACK if st.session_state.board_flipped else chess.WHITE

                    if st.session_state.get("show_best_move", False) and st.session_state.analysis["moves"][slider]["best_move"] != "None":
                        best_move = chess.Move.from_uci(st.session_state.analysis["moves"][slider]["best_move"])
                        svg = chess.svg.board(
                            board=board,
                            size=400,
                            orientation=orientation,
                            arrows=[(best_move.from_square, best_move.to_square)],
                        )
                    else:
                        svg = chess.svg.board(
                            board=board,
                            size=400,
                            orientation=orientation,
                        )
                    png_image = svg_to_png(svg, size=400)

                    # Side panels scroll on their own; board stays in view
                    PANEL_H = 720
                    col_left, col_center, col_right = st.columns([1, 2, 1])

                    with col_left:
                        with st.container(height=PANEL_H, border=True):
                            st.markdown("**Move Chart**")
                            moves_per_row = 3
                            for i in range(0, len(st.session_state.analysis["moves"]), moves_per_row):
                                cols = st.columns(moves_per_row)
                                for j in range(moves_per_row):
                                    idx = i + j
                                    if idx < len(st.session_state.analysis["moves"]):
                                        move_data = st.session_state.analysis["moves"][idx]
                                        eval_score = move_data["centipawn_eval"]
                                        eval_str = f"+{eval_score/100:.1f}" if eval_score > 0 else f"{eval_score/100:.1f}"
                                        book_indicator = "📖" if move_data["is_book_move"] else ""
                                        with cols[j]:
                                            if st.button(
                                                f"{idx+1}. {move_data['move']}\n{eval_str} {book_indicator}",
                                                key=f"move_{idx}",
                                                use_container_width=True,
                                                help=f"Quality: {move_data['quality']} | Book Move: {move_data['is_book_move']}"
                                            ):
                                                st.session_state.current_move = idx

                    with col_center:
                        st.image(png_image, use_container_width=True)

                        # Nav stays under the board (not under the tall report)
                        left, c1, c2, c3, c4, c5, right = st.columns(
                            [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
                            gap="small"
                        )
                        with c1:
                            if st.button("|<", key="first"):
                                st.session_state.current_move = 0
                        with c2:
                            if st.button("<", key="prev"):
                                st.session_state.current_move = max(
                                    0, st.session_state.current_move - 1
                                )
                        with c3:
                            if st.button(">", key="next"):
                                st.session_state.current_move = min(
                                    st.session_state.num_moves - 1,
                                    st.session_state.current_move + 1
                                )
                        with c4:
                            if st.button(">|", key="last"):
                                st.session_state.current_move = st.session_state.num_moves - 1
                        with c5:
                            if st.button("↻", key="flip", help="Flip board (White / Black POV)"):
                                st.session_state.board_flipped = not st.session_state.board_flipped

                    with col_right:
                        with st.container(height=PANEL_H, border=True):
                            st.markdown(
                                """
                                <style>
                                [data-testid="stVerticalBlock"]:has(.game-report-scale) p,
                                [data-testid="stVerticalBlock"]:has(.game-report-scale) li,
                                [data-testid="stVerticalBlock"]:has(.game-report-scale) span {
                                    font-size: 1.2rem !important;
                                    line-height: 1.55 !important;
                                }
                                [data-testid="stVerticalBlock"]:has(.game-report-scale) h3 {
                                    font-size: 1.45rem !important;
                                }
                                </style>
                                <div class="game-report-scale"></div>
                                """,
                                unsafe_allow_html=True,
                            )
                            result = st.session_state.analysis["moves"][slider]
                            st.markdown(
                                "<div style='background-image: linear-gradient(to top right, #00f0ff, #0e6fff, #8f5bff); border-radius: 6px'><h3 style='text-align: center; padding: 10px; margin: 10px 10px 15px 10px; font-weight: 700;'>GAME REPORT</h3></div>",
                                unsafe_allow_html=True,
                            )

                            st.markdown("---")
                            st.markdown("### 📖 Opening Analysis")
                            st.markdown(f"- **Opening**: `{st.session_state.analysis['opening_name']}`")
                            st.markdown(f"- **Book Accuracy**: `{st.session_state.analysis['book_accuracy']}%`")
                            st.markdown(f"- **Book Moves**: `{st.session_state.analysis['total_book_moves']}`")
                            if st.session_state.analysis['book_exit_move']:
                                st.markdown(f"- **Left Theory**: Move `{st.session_state.analysis['book_exit_move']}`")
                            else:
                                st.markdown(f"- **Left Theory**: `Still in book`")

                            st.markdown("---")
                            st.markdown("### 🎯 Classification Context")
                            st.markdown(f"- **Player Strength**: `{st.session_state.analysis['avg_elo']} Elo`")
                            st.markdown(f"- **Game Phase**: `{result['game_phase'].capitalize()}`")

                            st.markdown("---")
                            st.markdown("### ⚔️ Game Tactical Summary")
                            if st.session_state.analysis.get('total_tactics', 0) > 0:
                                st.markdown(f"- **Total Tactical Motifs**: `{st.session_state.analysis['total_tactics']}`")
                                for tactic_type, count in st.session_state.analysis.get('tactic_counts', {}).items():
                                    st.markdown(f"- **{tactic_type.replace('_', ' ').title()}**: `{count}`")
                            else:
                                st.markdown("- No tactical motifs found in game")

                            st.markdown("---")
                            st.markdown("### 📊 Move Analysis")
                            st.markdown(f"- **Move**: `{result['move']}`")
                            st.markdown(
                                f"- **Win Probability**: `{(result['score'] * 100):.2f}%`"
                            )
                            st.markdown(f"- **Best move**: `{result['best_move']}`")
                            st.markdown(
                                f"- **Move Quality**: <span style='color:{result['color']}; font-weight:bold;'>{result['quality']}</span>",
                                unsafe_allow_html=True,
                            )
                            st.markdown(f"- **Book Move**: `{'Yes 📖' if result['is_book_move'] else 'No'}`")
                            if result['book_weight']:
                                st.markdown(f"- **Book Weight**: `{result['book_weight']}`")

                            st.markdown("---")
                            st.markdown("### ⚔️ Tactical Analysis")
                            tactics = result.get('tactics', [])
                            if tactics:
                                for tactic in tactics:
                                    severity_color = "🔴" if tactic['severity'] == 'high' else "🟡"
                                    st.markdown(f"- {severity_color} **{tactic['type'].replace('_', ' ').title()}**: {tactic['description']}")
                            else:
                                st.markdown("- No tactical motifs detected")

                            if st.button("Show Best Move on Board", key="show_best", use_container_width=True):
                                st.session_state.show_best_move = not st.session_state.get("show_best_move", False)
                # Player info below the board
                with st.container(border=True):
                    col1, col2 = st.columns([1, 1], vertical_alignment="center", gap="small")

                    with col1:
                        with st.container(border=True):
                            black_name = game.headers.get('Black', 'Unknown')
                            black_elo = game.headers.get('BlackElo', '?')
                            st.markdown(
                                f"<span style='display:inline-block; width:12px; height:12px; background-color:black; border-radius:50%; margin-right:8px; border:1px solid #333;'></span>{black_name} ({black_elo})",
                                unsafe_allow_html=True
                            )
                    
                    with col2:
                        with st.container(border=True):
                            white_name = game.headers.get('White', 'Unknown')
                            white_elo = game.headers.get('WhiteElo', '?')
                            st.markdown(
                                f"<span style='display:inline-block; width:12px; height:12px; background-color:white; border-radius:50%; margin-right:8px; border:1px solid #ccc;'></span>{white_name} ({white_elo})",
                                unsafe_allow_html=True
                            )

        except Exception as e:
            st.error(f"Error analyzing game: {str(e)}")

    with st.sidebar:
        st.markdown("###### :gray[Powered by [Stockfish](https://stockfishchess.org/)]")


if __name__ == "__main__":
    main()
