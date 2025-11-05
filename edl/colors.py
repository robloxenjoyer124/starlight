import colorama
from colorama import Fore, Style

# Initialize colorama
colorama.init(autoreset=True)

def print_banner():
    """Print the blue ASCII banner."""
    banner = """
    ██╗    ██╗██╗  ██╗ █████╗ ████████╗██╗ ██████╗██╗  ██╗███████╗████████╗
    ██║    ██║██║  ██║██╔══██╗╚══██╔══╝██║██╔════╝██║ ██╔╝██╔════╝╚══██╔══╝
    ██║ █╗ ██║███████║███████║   ██║   ██║██║     █████╔╝ █████╗     ██║   
    ██║███╗██║██╔══██║██╔══██║   ██║   ██║██║     ██╔═██╗ ██╔══╝     ██║   
    ╚███╔███╔╝██║  ██║██║  ██║   ██║   ██║╚██████╗██║  ██╗███████╗   ██║   
     ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝   
                                                                         
    """
    print(f"{Fore.BLUE}{banner}{Style.RESET_ALL}")

def print_white(text):
    """Print text in white color."""
    print(f"{Fore.WHITE}{text}{Style.RESET_ALL}")

def print_error(text):
    """Print error message in red."""
    print(f"{Fore.RED}{text}{Style.RESET_ALL}")

def print_success(text):
    """Print success message in green."""
    print(f"{Fore.GREEN}{text}{Style.RESET_ALL}")