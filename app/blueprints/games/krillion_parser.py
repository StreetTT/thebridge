import re

def parse_krillion_text(raw_text: str) -> dict:
    """
    Parses the raw Krillion share text to extract the game number, score, and positional emojis.
    
    Expected format:
    Krillion #113 🦐
    365

    🫧🦑🐟🦑🦑🏮🦑
    """
    if not raw_text:
        raise ValueError("No raw text provided.")

    # 1. Extract Game Number
    # Looks for 'Krillion #' followed by digits
    game_match = re.search(r'Krillion #(\d+)', raw_text)
    if not game_match:
        raise ValueError("Could not find Krillion game number in text.")
    game_number = int(game_match.group(1))

    # 2. Extract Score
    # Looks for a standalone number on its own line (usually line 2)
    score_match = re.search(r'\n(\d+)\n', raw_text)
    if not score_match:
        raise ValueError("Could not find score in text.")
    score = int(score_match.group(1))

    # 3. Extract Emojis
    # Cleans empty lines and grabs the final line which contains the dive sequence
    lines = [line.strip() for line in raw_text.strip().split('\n') if line.strip()]
    if len(lines) < 3:
        raise ValueError("Raw text does not contain enough lines for a valid dive sequence.")
    
    emoji_string = lines[-1]
    # Convert string to list of characters to map positions 1 through 7
    emojis = list(emoji_string)

    if len(emojis) != 7:
        raise ValueError(f"Expected exactly 7 emojis in the dive sequence, found {len(emojis)}.")

    # 4. Return structured dictionary
    return {
        "game": game_number,
        "score": score,
        "positions": {
            "1": emojis[0],
            "2": emojis[1],
            "3": emojis[2],
            "4": emojis[3],
            "5": emojis[4],
            "6": emojis[5],
            "7": emojis[6],
        }
    }

if __name__ == "__main__":
    print(parse_krillion_text("""Krillion #107 🦐
250
    
🐟⬛🦑🦑🫧🦑🐟"""))