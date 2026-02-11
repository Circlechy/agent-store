"""
Fancy printing cuz we fancy people :-)
"""

import sys

# ANSI Colour Codes
CREDBG = "\033[41m"
CRED = "\033[91m"
CBLU = "\033[94m"
CCYN = "\033[96m"
CGRN = "\033[92m"
CYEL = "\033[41m"
CEND = "\033[0m"

# ascii art
TOMATO_ART = r"""
  ,d                                               ,d              
  88                                               88              
MM88MMM ,adPPYba,  88,dPYba,,adPYba,  ,adPPYYba, MM88MMM ,adPPYba, 
  88   a8"     "8a 88P'   "88"    "8a ""     `Y8   88   a8"     "8a
  88   8b       d8 88      88      88 ,adPPPPP88   88   8b       d8
  88,  "8a,   ,a8" 88      88      88 88,    ,88   88,  "8a,   ,a8"
  "Y888 `"YbbdP"'  88      88      88 `"8bbdP"Y8   "Y888 `"YbbdP"' 
""".strip("\n")

# Try to use rich if available/working; otherwise fall back to ANSI/text.
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except Exception:
    RICH_AVAILABLE = False


def apply_vertical_gradient(
    text_raw: str, start_rgb: tuple[int, int, int] = (255, 0, 0), end_rgb: tuple[int, int, int] = (255, 165, 0)
):
    """Apply vertical colour gradient to our beloved tomato (rich), else fall back to plain text."""
    if not RICH_AVAILABLE:
        return text_raw + "\n"

    lines = text_raw.splitlines()
    gradient_text = Text()

    for i, line in enumerate(lines):
        ratio = i / max(1, len(lines) - 1)
        r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * ratio)
        g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * ratio)
        b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * ratio)

        gradient_text.append(line + "\n", style=f"bold rgb({r},{g},{b})")
    return gradient_text


def print_ascii_art():
    """Bring out our wonderful ASCII art! (rich if possible; otherwise ANSI/plain)"""
    if RICH_AVAILABLE:
        try:
            styled_tomato = apply_vertical_gradient(TOMATO_ART)
            console.print(
                Panel(styled_tomato, expand=False, border_style="bright_red", title="[bold red] ⋆｡‧˚ʚ🍅ɞ˚‧｡⋆ [/]")
            )
            return
        except Exception:
            pass

    # Fallback: simple ANSI-colored ASCII art (or plain if ANSI is stripped)
    print(f"{CRED}{TOMATO_ART}{CEND}")


def print_success(message: str, end: str = "\n"):
    """Print a success message in green."""
    print(f"{CGRN}✓ {message}{CEND}", end=end)


def print_error(message: str, end: str = "\n"):
    """Print an error message in red background."""
    print(f"{CREDBG}❌ {message}{CEND}", end=end, file=sys.stderr)


def print_warning(message: str, end: str = "\n"):
    """Print a warning message in red."""
    print(f"{CRED}⚠️  {message}{CEND}", end=end, file=sys.stderr)


def print_info(message: str, end: str = "\n"):
    """Print an info message in blue."""
    print(f"{CBLU}ℹ️  {message}{CEND}", end=end)


def print_cyan(message: str, end: str = "\n"):
    """Print a message in cyan."""
    print(f"{CCYN}{message}{CEND}", end=end)


def print_green(message: str, end: str = "\n"):
    """Print a message in green."""
    print(f"{CGRN}{message}{CEND}", end=end)


def print_blue(message: str, end: str = "\n"):
    """Print a message in blue."""
    print(f"{CBLU}{message}{CEND}", end=end)


def print_red(message: str, end: str = "\n"):
    """Print a message in red."""
    print(f"{CRED}{message}{CEND}", end=end)


if __name__ == "__main__":
    print_ascii_art()
    print_cyan("Tomato Reviewer - Fancy Printing Demo")
    print()
    print_success("This is a success message!")
    print_error("This is an error message!")
    print_warning("This is a warning message!")
    print_info("This is an info message!")
    print()
    print_cyan("Cyan colored text")
    print_blue("Blue colored text")
    print_green("Green colored text")
    print_red("Red colored text")
