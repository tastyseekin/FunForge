import os
import io
import time
import psutil
import zipfile
import rarfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn, BarColumn, TaskProgressColumn  
from pathlib import Path
from pymediainfo import MediaInfo
from rich.console import Console
from rich.text import Text
from rich.progress import track
from rich.prompt import Prompt
from rich.panel import Panel
from rich.prompt import Confirm
from rich.style import Style
from rapidfuzz import fuzz, process
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed

APP_NAME = "FunForge"
APP_VERSION = "v1.0.0"
APP_AUTHOR = "tastyseekin"
APP_DATE = "2025-01-04"


console = Console()

#Already Same Name Function
TYPEWRITER_DELAY = 0.03    
MOVE_DELAY = 0.8        
PROGRESS_DELAY = 0.3    
MESSAGE_DELAY = 0.5     

# Easy-to-tweak parameters
FUZZ_THRESHOLD = 45  # Threshold for fuzzy matching
SPINNER_DURATION = 2  # Duration for spinner animation in seconds
ARCHIVE_EXTENSIONS = [".zip", ".rar"]
VIDEO_EXTENSIONS = [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mpeg"]
MULTI_AXIS_EXTENSIONS = [".pitch.funscript", ".roll.funscript", ".sway.funscript", ".surge.funscript", ".twist.funscript"]
SUBTITLE_EXTENSIONS = [".srt", ".sub", ".ass", ".ssa", ".vtt"]
BUZZWORDS = ["extended", "hd", "1080p", "4k", "remastered", "director's cut", "hq"]

ASCII_ART = r"""
>>==================================================<<
||                                                  ||
||                                                  ||
||     ______            ______                     ||
||    / ____/_  ______  / ____/___  _________ ____  ||
||   / /_  / / / / __ \/ /_  / __ \/ ___/ __ `/ _ \ ||
||  / __/ / /_/ / / / / __/ / /_/ / /  / /_/ /  __/ ||
|| /_/    \__,_/_/ /_/_/    \____/_/   \__, /\___/  ||
||                                    /____/        ||
||                                                  ||
||                                                  ||
>>==================================================<<
"""


def print_header():
    header = r"""
╔══════════════════════════════════════════════════════════╗
║              FunForge Version 1.0.0                      ║
║          by Tastyseekin (2025-01-25)                     ║
╚══════════════════════════════════════════════════════════╝"""
    console.print(header, style="rgb(48,209,204)")

def clear_console():
    """Clear the console output while keeping the ASCII art."""
    os.system("cls" if os.name == "nt" else "clear")

def spinner_animation(message, duration=SPINNER_DURATION):
    """Display a loading spinner with a message."""
    console.print(f"{message}", end="")
    for _ in track(range(duration * 10), description=message):
        time.sleep(0.1)
    console.print("")

def create_styled_prompt(question):
    """Create a styled yes/no prompt using Rich."""
    prompt_style = Style(color="cyan", bold=True)
    return Panel(
        f"[white]{question}[/white]",
        style=prompt_style,
        title="✨ Prompt",
        border_style="cyan"
    )

def collect_files_with_extension(directory, extensions, recursive):
    files = []
    if recursive:
        for root, _, filenames in os.walk(directory):
            if "FunForge" in root:  
                continue
            for filename in filenames:
                if any(filename.endswith(ext) for ext in extensions):
                    files.append(Path(root) / filename)
    else:
        for entry in os.scandir(directory):
            if entry.is_file() and any(entry.name.endswith(ext) for ext in extensions):
                files.append(Path(entry.path))
    return files

def contains_buzzwords(filename):
    """Check if a filename contains any buzzwords."""
    return sum(1 for word in BUZZWORDS if word.lower() in filename.lower())

def similarity_score(name1, name2):
    """Calculate a similarity score between two file names."""
    return fuzz.ratio(name1.lower(), name2.lower())

def clean_name(name):
    """Remove square brackets, parentheses and return the cleaned name for better matching."""
    return name.replace("[", "").replace("]", "").replace("(", "").replace(")", "").replace("_", " ").lower()

def get_resolution(file_path):
    """Extract resolution from a video file using pymediainfo."""
    media_info = MediaInfo.parse(file_path)
    for track in media_info.tracks:
        if track.track_type == "Video":
            return f"{track.width}x{track.height}"
    return "unknown_resolution"

def remove_resolution_tags(name):
    """Remove resolution tags like 1080p, 4k, 2160p, 1920x1080, 3840x2160 from the filename."""
    resolutions = ['720p', '1080p', '4k', '2160p', '1920x1080', '3840x2160']
    for res in resolutions:
        name = name.replace(f"_{res}", "").replace(f"{res}_", "").replace(res, "")
    return name

def choose_better_name(name1, name2, prefer_funscript=False):
    """Choose the more descriptive and informative name."""
    name1_cleaned = clean_name(name1)
    name2_cleaned = clean_name(name2)

    name1_buzzwords = contains_buzzwords(name1)
    name2_buzzwords = contains_buzzwords(name2)

    comparison_details = []

    # Check if one name contains common identifiers like '[PMV]' or artist name
    is_name1_funscript = "[PMV]" in name1 or "funscript" in name1.lower()
    is_name2_funscript = "[PMV]" in name2 or "funscript" in name2.lower()

    if prefer_funscript:
        # Prefer the `.funscript` name when it has script-type identifiers or more buzzwords
        if is_name2_funscript and not is_name1_funscript:
            comparison_details.append("Funscript contains script type or artist information.")
            return name2, comparison_details
        elif is_name1_funscript and not is_name2_funscript:
            comparison_details.append("Funscript contains script type or artist information.")
            return name1, comparison_details

    # Prioritize the name with more buzzwords
    if name1_buzzwords > name2_buzzwords:
        comparison_details.append("Contains more buzzwords.")
        return name1, comparison_details
    elif name2_buzzwords > name1_buzzwords:
        comparison_details.append("Contains more buzzwords.")
        return name2, comparison_details

    # If buzzwords are equal, prioritize the longer name
    if len(name1) > len(name2):
        comparison_details.append("Is longer and more descriptive.")
        return name1, comparison_details
    else:
        comparison_details.append("Is longer and more descriptive.")
        return name2, comparison_details

def is_resolution_difference(name1, name2):
    """Check if there is a resolution difference in the filenames."""
    resolutions = ['720p', '1080p', '4k', '1920x1080', '3840x2160']
    for res in resolutions:
        if res in name1 and res not in name2:
            return True
        if res in name2 and res not in name1:
            return True
    return False

def extract_with_progress(archive_path, extract_dir, password=None):
    """Extract an archive with progress bar and proper password handling."""
    # Increase chunk size for better performance
    CHUNK_SIZE = 1024 * 1024  # Increase to 1MB chunks (from 64KB)
    BUFFER_SIZE = 8192 * 1024  # 8MB buffer size
    
    try:
        if archive_path.suffix.lower() == ".zip":
            with zipfile.ZipFile(archive_path) as archive:
                # Check if archive is password protected
                is_encrypted = any(zip_info.flag_bits & 0x1 for zip_info in archive.filelist)
                if is_encrypted and not password:
                    return False, extract_dir, "encrypted archive"

                total_size = sum(info.file_size for info in archive.filelist)
                extracted_size = 0

                with Progress(
                    SpinnerColumn(),
                    "[progress.description]{task.description}",
                    BarColumn(),
                    TaskProgressColumn(),
                    TimeElapsedColumn(),
                ) as progress:
                    task = progress.add_task(
                        description=f"Extracting {archive_path.name}",
                        total=total_size
                    )

                    # Use ThreadPoolExecutor for parallel processing
                    with ThreadPoolExecutor(max_workers=4) as executor:
                        futures = []
                        
                        for file_info in archive.filelist:
                            try:
                                source = archive.open(file_info, pwd=password.encode() if password else None)
                                target_path = Path(extract_dir) / file_info.filename
                                target_path.parent.mkdir(parents=True, exist_ok=True)

                                with open(target_path, 'wb', buffering=BUFFER_SIZE) as target:
                                    while True:
                                        chunk = source.read(CHUNK_SIZE)
                                        if not chunk:
                                            break
                                        target.write(chunk)
                                        extracted_size += len(chunk)
                                        progress.update(task, 
                                                     completed=extracted_size,
                                                     description=f"Extracting: {file_info.filename}",
                                                     refresh=True)
                                source.close()

                            except Exception as e:
                                return False, extract_dir, str(e)

                return True, extract_dir, None

        elif archive_path.suffix.lower() == ".rar":
            with rarfile.RarFile(archive_path) as archive:
                # Check if archive is password protected
                is_encrypted = archive.needs_password()
                if is_encrypted and not password:
                    return False, extract_dir, "encrypted archive"

                total_size = sum(info.file_size for info in archive.infolist())
                extracted_size = 0

                with Progress(
                    SpinnerColumn(),
                    "[progress.description]{task.description}",
                    BarColumn(),
                    TaskProgressColumn(),
                    TimeElapsedColumn(),
                ) as progress:
                    task = progress.add_task(
                        description=f"Extracting {archive_path.name}",
                        total=total_size
                    )

                    # Use ThreadPoolExecutor for parallel processing
                    with ThreadPoolExecutor(max_workers=4) as executor:
                        futures = []

                        for file_info in archive.infolist():
                            try:
                                source = archive.open(file_info, pwd=password if password else None)
                                target_path = Path(extract_dir) / file_info.filename
                                target_path.parent.mkdir(parents=True, exist_ok=True)

                                with open(target_path, 'wb', buffering=BUFFER_SIZE) as target:
                                    while True:
                                        chunk = source.read(CHUNK_SIZE)
                                        if not chunk:
                                            break
                                        target.write(chunk)
                                        extracted_size += len(chunk)
                                        progress.update(task, 
                                                     completed=extracted_size,
                                                     description=f"Extracting: {file_info.filename}",
                                                     refresh=True)
                                source.close()

                            except Exception as e:
                                return False, extract_dir, str(e)

                return True, extract_dir, None

    except Exception as e:
        return False, extract_dir, str(e)

def process_extracted_directory(directory, extracted_dir, reference_names, tag_with_resolution):
    """Process files from extracted directory and clean up if all files are matched."""
    console.print(f"\n[yellow]Processing files from: {extracted_dir.name}[/yellow]")
    
    # Create FunForge directory structure in the main directory
    funforge_dir = directory / "FunForge"  
    already_same_name_dir = funforge_dir / "Already Same Name"
    already_same_name_dir.mkdir(parents=True, exist_ok=True)
    
    # Collect files from the extracted directory
    video_files = collect_files_with_extension(extracted_dir, VIDEO_EXTENSIONS, recursive=False)
    funscript_files = collect_files_with_extension(extracted_dir, [".funscript"] + MULTI_AXIS_EXTENSIONS, recursive=False)
    subtitle_files = collect_files_with_extension(extracted_dir, SUBTITLE_EXTENSIONS, recursive=False)
    
    # Create maps for matching
    video_map = {f.stem: f for f in video_files}
    funscript_map = {f.stem: f for f in funscript_files}
    subtitle_map = {f.stem: f for f in subtitle_files}
    
    all_matched = True
    unmatched_files = []
    
    # Check for exact matches
    for video_base, video_path in video_map.items():
        matching_funscripts = [
            f for f_stem, f in funscript_map.items()
            if f_stem == video_base or f_stem.startswith(f"{video_base}.")
        ]
        matching_subtitles = [
            s for s_stem, s in subtitle_map.items()
            if s_stem == video_base
        ]
        
        if matching_funscripts or matching_subtitles:
            # Move matched files to Already Same Name
            console.print(f"Moving matched files for: [green]{video_base}[/green]")
            
            # Check if files exist in destination
            if not (already_same_name_dir / video_path.name).exists():
                video_path.rename(already_same_name_dir / video_path.name)
            else:
                console.print(f"[yellow]File already exists in destination: {video_path.name}[/yellow]")
            
            for funscript in matching_funscripts:
                if not (already_same_name_dir / funscript.name).exists():
                    funscript.rename(already_same_name_dir / funscript.name)
                else:
                    console.print(f"[yellow]File already exists in destination: {funscript.name}[/yellow]")
            
            for subtitle in matching_subtitles:
                if not (already_same_name_dir / subtitle.name).exists():
                    subtitle.rename(already_same_name_dir / subtitle.name)
                else:
                    console.print(f"[yellow]File already exists in destination: {subtitle.name}[/yellow]")
        else:
            all_matched = False
            unmatched_files.append(video_path)
    
    # Check for any remaining unmatched files
    remaining_funscripts = [f for f_stem, f in funscript_map.items() if f.exists()]
    remaining_subtitles = [s for s_stem, s in subtitle_map.items() if s.exists()]
    
    if remaining_funscripts or remaining_subtitles:
        all_matched = False
        unmatched_files.extend(remaining_funscripts)
        unmatched_files.extend(remaining_subtitles)
    
    # If all files were matched, remove the extracted directory
    if all_matched:
        try:
            import shutil
            shutil.rmtree(extracted_dir)
            console.print(f"[green]All files matched and moved. Removed extracted directory: {extracted_dir.name}[/green]")
            return True
        except Exception as e:
            console.print(f"[red]Error removing directory {extracted_dir}: {str(e)}[/red]")
    else:
        console.print(f"[yellow]Some files remain unmatched in {extracted_dir.name}[/yellow]")
        for file in unmatched_files:
            console.print(f"[red]Unmatched: {file.name}[/red]")
    
    return all_matched

def handle_archives(directory):
    """Unpack zip and rar archives and prepare files for renaming."""
    archive_files = collect_files_with_extension(directory, ARCHIVE_EXTENSIONS, recursive=False)
    
    if not archive_files:
        return []

    console.print("[yellow]Found the following archives:[/yellow]")
    for archive_path in archive_files:
        console.print(f"  - {archive_path.name}")

    # Updated prompt style
    console.print(create_styled_prompt("Extract and process these archives?"))
    confirm = Confirm.ask("", default=True)
    if not confirm:
        return []

    extracted_directories = []
    processed_archives = []  # Keep track of successfully processed archives
    
    # Create Directory Structure
    funforge_dir = directory / "FunForge"  
    already_same_name_dir = funforge_dir / "Already Same Name"
    already_same_name_dir.mkdir(parents=True, exist_ok=True)
    
    # Process each archive
    for archive_path in archive_files:
        extract_dir = directory / archive_path.stem
        extract_dir.mkdir(exist_ok=True)
        
        console.print(f"\n[yellow]Processing {archive_path.name}...[/yellow]")
        
        extraction_successful = False
        password = None
        max_attempts = 3
        attempt = 0

        while not extraction_successful and attempt < max_attempts:
            try:
                success, _, error = extract_with_progress(archive_path, extract_dir, password)
                
                if success:
                    extraction_successful = True
                    console.print(f"[green]Successfully extracted to {extract_dir}[/green]")
                    break
                elif 'encrypted' in str(error).lower() or 'password' in str(error).lower():
                    password = Prompt.ask(
                        f"[red]Archive is password-protected. Enter password (attempt {attempt + 1}/{max_attempts}, or 'skip' to skip)[/red]"
                    )
                    if password.lower() == 'skip':
                        break
                    attempt += 1
                else:
                    console.print(f"[red]Error extracting: {error}[/red]")
                    break
            except Exception as e:
                console.print(f"[red]Unexpected error: {str(e)}[/red]")
                break

        # Process the extracted files immediately if extraction was successful
        if extraction_successful and extract_dir.exists() and any(extract_dir.iterdir()):
            # Collect all files from the extracted directory
            video_files = collect_files_with_extension(extract_dir, VIDEO_EXTENSIONS, recursive=False)
            funscript_files = collect_files_with_extension(extract_dir, [".funscript"] + MULTI_AXIS_EXTENSIONS, recursive=False)
            subtitle_files = collect_files_with_extension(extract_dir, SUBTITLE_EXTENSIONS, recursive=False)

            # Check for exact matches directly in the extracted directory
            all_matched = True
            for video_file in video_files:
                video_stem = video_file.stem
                matching_funscripts = [f for f in funscript_files if f.stem == video_stem]
                matching_subtitles = [s for s in subtitle_files if s.stem == video_stem]

                if matching_funscripts or matching_subtitles:
                    # Move files directly to Already Same Name
                    console.print(f"Found exact match for {video_file.name}")
                    
                    # Check if files already exist in destination
                    if not (already_same_name_dir / video_file.name).exists():
                        try:
                            video_file.rename(already_same_name_dir / video_file.name)
                        except Exception as e:
                            console.print(f"[yellow]Could not move {video_file.name}: {str(e)}[/yellow]")
                    else:
                        console.print(f"[yellow]File already exists in destination: {video_file.name}[/yellow]")
                    
                    for funscript in matching_funscripts:
                        if not (already_same_name_dir / funscript.name).exists():
                            try:
                                funscript.rename(already_same_name_dir / funscript.name)
                            except Exception as e:
                                console.print(f"[yellow]Could not move {funscript.name}: {str(e)}[/yellow]")
                        else:
                            console.print(f"[yellow]File already exists in destination: {funscript.name}[/yellow]")
                    
                    for subtitle in matching_subtitles:
                        if not (already_same_name_dir / subtitle.name).exists():
                            try:
                                subtitle.rename(already_same_name_dir / subtitle.name)
                            except Exception as e:
                                console.print(f"[yellow]Could not move {subtitle.name}: {str(e)}[/yellow]")
                        else:
                            console.print(f"[yellow]File already exists in destination: {subtitle.name}[/yellow]")
                else:
                    # Only move unmatched files to main directory
                    all_matched = False
                    if not (directory / video_file.name).exists():
                        try:
                            video_file.rename(directory / video_file.name)
                        except Exception as e:
                            console.print(f"[yellow]Could not move {video_file.name}: {str(e)}[/yellow]")
                    else:
                        console.print(f"[yellow]File already exists in destination: {video_file.name}[/yellow]")

            # Move any remaining unmatched files to main directory
            remaining_funscripts = [f for f in funscript_files if f.exists()]
            remaining_subtitles = [s for s in subtitle_files if s.exists()]
            
            for file in remaining_funscripts + remaining_subtitles:
                if not (directory / file.name).exists():
                    try:
                        file.rename(directory / file.name)
                    except Exception as e:
                        console.print(f"[yellow]Could not move {file.name}: {str(e)}[/yellow]")
                else:
                    console.print(f"[yellow]File already exists in destination: {file.name}[/yellow]")
                all_matched = False

            # Clean up extraction directory
            try:
                if extract_dir.exists():
                    import shutil
                    shutil.rmtree(extract_dir)
            except Exception as e:
                console.print(f"[red]Error cleaning up extraction directory: {str(e)}[/red]")

            if all_matched:
                # Mark archive for deletion only if all files were matched
                processed_archives.append(archive_path)
                console.print(f"[green]All files matched and moved to Already Same Name.[/green]")
            else:
                # Add to extracted_directories only if some files need renaming
                extracted_directories.append(directory)
                console.print(f"[yellow]Some files need to be processed for renaming.[/yellow]")
        else:
            if extract_dir.exists() and not any(extract_dir.iterdir()):
                try:
                    extract_dir.rmdir()
                except Exception as e:
                    console.print(f"[red]Error removing empty extraction directory: {str(e)}[/red]")

    # Delete processed archives
    for archive_path in processed_archives:
        try:
            archive_path.unlink()
            console.print(f"[green]Deleted processed archive: {archive_path.name}[/green]")
        except Exception as e:
            console.print(f"[red]Error deleting archive {archive_path.name}: {str(e)}[/red]")

    return extracted_directories

def load_reference_names(reference_files):
    """Load reference names from text files."""
    reference_names = set()
    for file_path in reference_files:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                reference_names.add(line.strip())
    return reference_names

def refine_buzzwords(reference_files):
    """Refine the BUZZWORDS list based on the content of the reference files."""
    global BUZZWORDS
    additional_buzzwords = set()
    for file_path in reference_files:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                words = line.strip().split()
                for word in words:
                    if word.lower() not in BUZZWORDS:
                        additional_buzzwords.add(word.lower())
    BUZZWORDS = list(set(BUZZWORDS + list(additional_buzzwords)))

def fuzzy_match(target, choices, threshold=FUZZ_THRESHOLD):
    """Find the best fuzzy match for a target string from a list of choices."""
    matches = process.extract(target, choices, scorer=fuzz.ratio, limit=3)
    return [match for match, score, _ in matches if score >= threshold]

def is_exact_match(name1, name2, debug=False):
    """
    Determines if two filenames are exactly matching before their extensions.
    Returns True only if the filenames are identical (case-insensitive).
    """
    # Remove extensions and convert to lowercase
    base1 = Path(name1).stem.lower()
    base2 = Path(name2).stem.lower()
    
    # Only print debug information if debug is True
    if debug:
        console.print(f"Comparing: '{base1}' with '{base2}'")
    
    # Check if names are identical after lowercase conversion
    return base1 == base2

def typewriter_print(text, delay=0.03, style=None):
    """Enhanced typewriter effect with optional styling."""
    for char in text:
        if style:
            console.print(char, end='', style=style)
        else:
            console.print(char, end='')
        time.sleep(delay)
    console.print()  # New line at the end

def typewriter_print(text, delay=0.03, style=None):
    """Enhanced typewriter effect with optional styling."""
    for char in text:
        if style:
            console.print(char, end='', style=style)
        else:
            console.print(char, end='')
        time.sleep(delay)
    console.print()  # New line at the end

def typewriter_print(text, delay=0.03, style=None):
    """Enhanced typewriter effect with optional styling."""
    for char in text:
        if style:
            console.print(char, end='', style=style)
        else:
            console.print(char, end='')
        time.sleep(delay)
    console.print()  # New line at the end

def move_exact_matches(video_files, funscript_files, subtitle_files, already_same_name_dir, dry_run=False, show_progress=True):
    """Move files with exact matching base names to Already Same Name directory."""
    video_map = {f.stem: f for f in video_files}
    funscript_map = {f.stem: f for f in funscript_files}
    subtitle_map = {f.stem: f for f in subtitle_files}

    if not show_progress:
        # Silent mode - just move files without any display
        moved_files = set()
        remaining_videos = []
        remaining_funscripts = []
        remaining_subtitles = []
        matching_sets = []

        # Find matching sets silently
        for video_base, video_path in list(video_map.items()):
            matched_files = [(video_path, "Video")]
            matching_funscripts = [f for f_stem, f in funscript_map.items() 
                                 if is_exact_match(video_base, f_stem, debug=False)]
            matching_subtitles = [s for s_stem, s in subtitle_map.items() 
                                if is_exact_match(video_base, s_stem, debug=False)]
            
            if matching_funscripts or matching_subtitles:
                matched_files.extend((f, "Funscript") for f in matching_funscripts)
                matched_files.extend((s, "Subtitle") for s in matching_subtitles)
                matching_sets.append(matched_files)
            else:
                remaining_videos.append(video_path)

        # Move files silently
        if matching_sets and not dry_run:
            for matched_set in matching_sets:
                for file_path, _ in matched_set:
                    if file_path not in moved_files and file_path.exists():
                        try:
                            file_path.rename(already_same_name_dir / file_path.name)
                            moved_files.add(file_path)
                        except Exception as e:
                            console.print(f"[red]Error moving {file_path.name}: {str(e)}[/red]")

        # Handle remaining files and return
        matched_funscripts = {f for matched_set in matching_sets for f, ftype in matched_set if ftype == "Funscript"}
        matched_subtitles = {s for matched_set in matching_sets for s, ftype in matched_set if ftype == "Subtitle"}
        
        remaining_funscripts.extend([f for f_stem, f in funscript_map.items() 
                                   if f not in matched_funscripts and f.exists()])
        remaining_subtitles.extend([s for s_stem, s in subtitle_map.items() 
                                   if s not in matched_subtitles and s.exists()])

        return remaining_videos, remaining_funscripts, remaining_subtitles

    else:
        # Progress mode - show detailed progress
        remaining_videos = []
        remaining_funscripts = []
        remaining_subtitles = []
        moved_files = set()
        matching_sets = []
        
        # Find matching sets
        for video_base, video_path in list(video_map.items()):
            matched_files = [(video_path, "Video")]
            matching_funscripts = [f for f_stem, f in funscript_map.items() 
                                 if is_exact_match(video_base, f_stem, debug=True)]
            matching_subtitles = [s for s_stem, s in subtitle_map.items() 
                                if is_exact_match(video_base, s_stem, debug=True)]
            
            if matching_funscripts or matching_subtitles:
                matched_files.extend((f, "Funscript") for f in matching_funscripts)
                matched_files.extend((s, "Subtitle") for s in matching_subtitles)
                matching_sets.append(matched_files)
            else:
                remaining_videos.append(video_path)

        if matching_sets:
            console.print("\n[cyan]════════ Moving Exact Matches ════════[/cyan]")
            
            with Progress(
                SpinnerColumn(),
                "[progress.description]{task.description}",
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                transient=False
            ) as progress:
                move_task = progress.add_task("Moving matched files...", total=len(matching_sets))
                
                for matched_set in matching_sets:
                    files_str = " + ".join(f"[{ftype}] {f.name}" for f, ftype in matched_set)
                    progress.update(move_task, description=f"Moving: {files_str}")
                    
                    if not dry_run:
                        for file_path, file_type in matched_set:
                            if file_path not in moved_files and file_path.exists():
                                try:
                                    file_path.rename(already_same_name_dir / file_path.name)
                                    moved_files.add(file_path)
                                except Exception as e:
                                    console.print(f"\n[red]Error moving {file_path.name}: {str(e)}[/red]")
                    
                    progress.advance(move_task)
                    time.sleep(MOVE_DELAY)

            # Summary after moving files
            if not dry_run:
                console.print(f"\n[green]✓ Moved {len(matching_sets)} sets of matching files to 'Already Same Name'[/green]")
            else:
                console.print(f"\n[yellow]DRY RUN: Would move {len(matching_sets)} sets of matching files[/yellow]")

        # Handle remaining files
        matched_funscripts = {f for matched_set in matching_sets for f, ftype in matched_set if ftype == "Funscript"}
        matched_subtitles = {s for matched_set in matching_sets for s, ftype in matched_set if ftype == "Subtitle"}
        
        remaining_funscripts.extend([f for f_stem, f in funscript_map.items() 
                                   if f not in matched_funscripts and f.exists()])
        remaining_subtitles.extend([s for s_stem, s in subtitle_map.items() 
                                   if s not in matched_subtitles and s.exists()])

        return remaining_videos, remaining_funscripts, remaining_subtitles

def choose_better_name(name1, name2, prefer_funscript=False):
    """Choose the more descriptive and informative name."""
    name1_cleaned = clean_name(name1)
    name2_cleaned = clean_name(name2)

    name1_buzzwords = contains_buzzwords(name1)
    name2_buzzwords = contains_buzzwords(name2)

    comparison_details = []

    # Check if one name contains common identifiers like '[PMV]' or artist name
    is_name1_funscript = "[PMV]" in name1 or "funscript" in name1.lower()
    is_name2_funscript = "[PMV]" in name2 or "funscript" in name2.lower()

    if prefer_funscript:
        # Prefer the `.funscript` name when it has script-type identifiers or more buzzwords
        if is_name2_funscript and not is_name1_funscript:
            comparison_details.append("Funscript contains script type or artist information.")
            return name2, comparison_details
        elif is_name1_funscript and not is_name2_funscript:
            comparison_details.append("Funscript contains script type or artist information.")
            return name1, comparison_details

    # Prioritize the name with more buzzwords
    if name1_buzzwords > name2_buzzwords:
        comparison_details.append("Contains more buzzwords.")
        return name1, comparison_details
    elif name2_buzzwords > name1_buzzwords:
        comparison_details.append("Contains more buzzwords.")
        return name2, comparison_details

    # If buzzwords are equal, prioritize the longer name
    if len(name1) > len(name2):
        comparison_details.append("Is longer and more descriptive.")
        return name1, comparison_details
    else:
        comparison_details.append("Is longer and more descriptive.")
        return name2, comparison_details

# Assuming other necessary imports and helper functions are defined elsewhere
def rename_files(directory, reference_names, tag_with_resolution, recursive=False, dry_run=False, show_exact_matches=True):
    # Initialize these variables at the start
    new_funscript_names = []
    new_subtitle_names = []

    """Match and rename video and funscript files."""
    funforge_dir = directory / "FunForge"
    changed_dir = funforge_dir / "Changed"
    not_changed_dir = funforge_dir / "Not Changed"
    already_same_name_dir = funforge_dir / "Already Same Name"

    # Automatically create directories if they don't exist
    changed_dir.mkdir(parents=True, exist_ok=True)
    not_changed_dir.mkdir(parents=True, exist_ok=True)
    already_same_name_dir.mkdir(parents=True, exist_ok=True)

    spinner_animation("Scanning for video, funscript, and subtitle files...")
    video_files = collect_files_with_extension(directory, VIDEO_EXTENSIONS, recursive)

    # Collect main funscripts first
    funscript_files = collect_files_with_extension(directory, [".funscript"], recursive)
    multi_axis_files = []
    seen_base_names = {f.stem for f in funscript_files}

    # Collect multi-axis files, avoiding duplicates by checking base names
    for ext in MULTI_AXIS_EXTENSIONS:
        for f in collect_files_with_extension(directory, [ext], recursive):
            base_name = f.name[:-(len(ext))]  # Remove the extension to get base name
            if base_name not in seen_base_names:
                multi_axis_files.append(f)
                seen_base_names.add(base_name)

    # Combine all funscript files
    funscript_files.extend(multi_axis_files)

    subtitle_files = collect_files_with_extension(directory, SUBTITLE_EXTENSIONS, recursive)
    archive_files = collect_files_with_extension(directory, ARCHIVE_EXTENSIONS, recursive)

    console.print(f"[blue]Found {len(video_files)} video files, {len(funscript_files)} funscript files ({len(multi_axis_files)} multi-axis), {len(subtitle_files)} subtitle files, and {len(archive_files)} archive files.[/blue]\n")

    # Move 100% matching files to "Already Same Name" directory first
    video_files, funscript_files, subtitle_files = move_exact_matches(video_files, funscript_files, subtitle_files, already_same_name_dir, dry_run, show_exact_matches)

    # Create mappings of base names to full paths
    video_map = {f.stem: f for f in video_files}
    funscript_map = {f.stem: f for f in funscript_files}
    subtitle_map = {f.stem: f for f in subtitle_files}

    not_changed_files = []

    # Add a set to track moved files
    moved_files = set()

    # Improved multi-axis extension handling
    for video_base, video_path in video_map.items():
        # Reset lists for each video file
        new_funscript_names = []
        new_subtitle_names = []

        funscript_stems = []
        multi_axis_dict = {}  # Keep track of multi-axis files by their base name

        # First collect all funscript base names
        for f in funscript_files:
            is_multi_axis = False
            for ext in MULTI_AXIS_EXTENSIONS:
                if f.name.endswith(ext):
                    is_multi_axis = True
                    base_name = f.name[:-len(ext)]
                    axis_type = ext.split('.')[1]
                    if base_name not in multi_axis_dict:
                        multi_axis_dict[base_name] = []
                    multi_axis_dict[base_name].append((f, axis_type))
                    break

            if not is_multi_axis:
                funscript_stems.append(f.stem)

        # Add base names for multi-axis files
        funscript_stems.extend(multi_axis_dict.keys())

        subtitle_stems = [s.stem for s in subtitle_files]
        all_stems = funscript_stems + subtitle_stems

        best_matches = fuzzy_match(video_base, all_stems)
        console.print(f"Best matches for {video_base}: {best_matches}")  # Debugging information

        if best_matches:
            funscript_paths = []
            multi_axis_types = []
            normal_funscript_path = None
            seen_paths = set()  # Track which paths we've already added
            seen_subtitle_stems = set()  # Initialize the set for tracking subtitle stems
            seen_funscript_stems = set()  # Initialize the set for tracking funscript stems

            for match in best_matches:
                # Check for normal funscript
                if match in funscript_map and match not in seen_funscript_stems:
                    normal_funscript_path = funscript_map[match].with_suffix(".funscript")
                    seen_paths.add(normal_funscript_path)
                    seen_funscript_stems.add(match)

                # Check for multi-axis funscripts
                if match in multi_axis_dict:
                    for f, axis_type in multi_axis_dict[match]:
                        if f not in seen_paths:  # Only add if we haven't seen this path before
                            funscript_paths.append(f)
                            multi_axis_types.append(axis_type)
                            seen_paths.add(f)

            # Modified subtitle handling to prevent duplicates
            subtitle_paths = []
            for match in best_matches:
                if match in subtitle_map and match not in seen_subtitle_stems:
                    subtitle_path = subtitle_map[match]
                    if subtitle_path not in seen_paths:
                        subtitle_paths.append(subtitle_path)
                        seen_subtitle_stems.add(match)
                        seen_paths.add(subtitle_path)

            if normal_funscript_path or funscript_paths or subtitle_paths:
                clear_console()

                video_size = video_path.stat().st_size / (1024 * 1024)  # Size in MB

                console.print("------------------------------------------------------------")
                console.print(f"Pair Detected:", style="blink bold #48D1CC")
                console.print(f" ")
                console.print(f"  Video File: [red]{video_path.name}[/red] (Size: {video_size:.2f} MB)")

                if normal_funscript_path:
                    console.print(f"  Funscript File: [green]{normal_funscript_path.name}[/green]")
                for i, funscript_path in enumerate(funscript_paths):
                    axis_type = multi_axis_types[i]
                    console.print(f"  Multi-Axis Funscript File: [green]{funscript_path.name}[/green] ({axis_type})")

                for subtitle_path in subtitle_paths:
                    console.print(f"  Subtitle File: [blue]{subtitle_path.name}[/blue]")
                
                # Remove resolution tags from video and funscript names
                video_base_clean = remove_resolution_tags(video_base)
                normal_funscript_base_clean = remove_resolution_tags(normal_funscript_path.stem) if normal_funscript_path else None
                funscript_bases_clean = [remove_resolution_tags(f.stem) for f in funscript_paths]
                subtitle_bases_clean = [remove_resolution_tags(s.stem) for s in subtitle_paths]

                # Add the new resolution information
                if tag_with_resolution:
                    resolution = get_resolution(video_path)
                    video_base_clean = f"{video_base_clean}_{resolution}"
                    if normal_funscript_base_clean:
                        normal_funscript_base_clean = f"{normal_funscript_base_clean}_{resolution}"
                    funscript_bases_clean = [f"{base}_{resolution}" for base in funscript_bases_clean]
                    subtitle_bases_clean = [f"{base}_{resolution}" for base in subtitle_bases_clean]

                # Choose the better name based on criteria
                better_name = video_base_clean
                if normal_funscript_base_clean:
                    better_name, comparison_details = choose_better_name(video_base_clean, normal_funscript_base_clean, prefer_funscript=True)
                elif funscript_bases_clean:
                    better_name, comparison_details = choose_better_name(video_base_clean, funscript_bases_clean[0], prefer_funscript=True)
                elif subtitle_bases_clean:
                    better_name, comparison_details = choose_better_name(video_base_clean, subtitle_bases_clean[0], prefer_funscript=True)

                new_video_name = f"{better_name}{video_path.suffix}"
                if normal_funscript_path:
                    new_funscript_names.append((normal_funscript_path, Path(changed_dir / f"{better_name}.funscript")))
                new_funscript_names.extend(
                    (f, Path(changed_dir / f"{better_name}.{multi_axis_types[i]}.funscript")) for i, f in enumerate(funscript_paths)
                )
                new_subtitle_names = [(s, Path(changed_dir / f"{better_name}{s.suffix}")) for s in subtitle_paths]
                
                console.print(f" ")
                console.print(f"Better name chosen based on criteria: {', '.join(comparison_details)}\n")

                # Frame the current and proposed names
                old_name_panel = Panel(
                    f"Current: [red]{video_path.name}[/red]\n"
                    + (f"Current: [red]{normal_funscript_path.name}[/red]\n" if normal_funscript_path else "")
                    + "\n".join([f"Current: [red]{f.name}[/red]" for f in funscript_paths if f != normal_funscript_path])
                    + "\n".join([f"Current: [red]{s.name}[/red]" for s in subtitle_paths]),
                    title="Old Names"
                )
                new_name_panel = Panel(
                    f"New: [green]{new_video_name}[/green]\n"
                    + (f"New: [green]{Path(changed_dir / f'{better_name}.funscript').name}[/green]\n" if normal_funscript_path else "")
                    + "\n".join([f"New: [green]{new_name.name}[/green]" for _, new_name in new_funscript_names if not normal_funscript_path or not new_name.name.endswith('.funscript') or any(ext.split('.')[1] in new_name.name for ext in MULTI_AXIS_EXTENSIONS)])
                    + "\n".join([f"New: [green]{new_name.name}[/green]" for _, new_name in new_subtitle_names]),
                    title="Proposed Names"
                )

                console.print(old_name_panel)
                console.print(new_name_panel)

                console.print(create_styled_prompt("Approve this change?"))
                user_input = Confirm.ask("", default=True)

                if user_input:
                    if dry_run:
                        console.print(f"[yellow][DRY RUN] Would rename {video_path} to {new_video_name}[/yellow]")
                        for old_name, new_name in new_funscript_names:
                            console.print(f"[yellow][DRY RUN] Would rename {old_name} to {new_name}[/yellow]")
                        for old_name, new_name in new_subtitle_names:
                            console.print(f"[yellow][DRY RUN] Would rename {old_name} to {new_name}[/yellow]")
                    else:
                        try:
                            # Create all necessary directories first
                            changed_dir.mkdir(parents=True, exist_ok=True)

                            # Move all files in a single transaction-like block
                            files_to_move = [
                                (video_path, changed_dir / new_video_name)
                            ]
                            
                            # Add funscript files to the move list
                            files_to_move.extend(new_funscript_names)
                            
                            # Add subtitle files to the move list
                            files_to_move.extend(new_subtitle_names)

                            # Verify all files exist before moving any
                            all_files_exist = True
                            for old_path, _ in files_to_move:
                                if not old_path.exists():
                                    console.print(f"[red]Error: File {old_path} no longer exists[/red]")
                                    all_files_exist = False
                                    break

                            if all_files_exist:
                                # Move all files
                                for old_path, new_path in files_to_move:
                                    if old_path not in moved_files and old_path.exists():
                                        try:
                                            old_path.rename(new_path)
                                            moved_files.add(old_path)
                                            console.print(f"[green]Renamed {old_path} to {new_path}[/green]")
                                        except Exception as e:
                                            console.print(f"[red]Error moving {old_path}: {str(e)}[/red]")

                        except Exception as e:
                            console.print(f"[red]Error during file movement: {str(e)}[/red]")
                            continue

        else:
            console.print(f"No good match found for [red]{video_path.name}[/red]. Moving to 'Not Changed'.\n")
            not_changed_files.append(video_path)

    # Move all unmatched .funscript files, subtitle files, and archive files to 'Not Changed' folder
    matched_files = {f[0] for f in new_funscript_names} | {s[0] for s in new_subtitle_names}
    unused_files = set(funscript_files + subtitle_files + archive_files) - matched_files

    # Modify the handling of not_changed_files to check against moved_files
    for unused_file in unused_files:
        if unused_file not in moved_files:
            console.print(f"No match found for [red]{unused_file.name}[/red]. Moving to 'Not Changed'.\n")
            not_changed_files.append(unused_file)

    if not dry_run:
        for file_path in not_changed_files:
            if file_path not in moved_files and file_path.exists():
                try:
                    file_path.rename(not_changed_dir / file_path.name)
                    moved_files.add(file_path)
                    console.print(f"Moved {file_path} to 'Not Changed' directory.\n")
                except FileNotFoundError:
                    console.print(f"[yellow]Warning: Could not find file {file_path}[/yellow]")
                except Exception as e:
                    console.print(f"[red]Error moving file {file_path}: {str(e)}[/red]")

    # Add this section to handle the "Already Same Name" only scenario
    if not video_files and not funscript_files and not subtitle_files:
        console.print("[yellow]All files were exact matches and have been moved to 'Already Same Name' directory.[/yellow]")
        while True:
            console.print(create_styled_prompt("Press 'y' to exit"))
            exit_confirm = Confirm.ask("", default=True)
            if exit_confirm:
                break

    console.print("\nProcessing complete.")

def cleanup_empty_folders(directory, exclude_dir="FunForge"):
    """
    Recursively clean up empty folders after processing.
    
    Args:
        directory (Path): The root directory to start cleaning from
        exclude_dir (str): Directory name to exclude from cleanup (e.g., 'FunForge')
    """
    def is_empty_dir(path):
        """Check if directory is empty or contains only empty directories."""
        if exclude_dir in str(path):
            return False
        
        try:
            # List all items in directory
            contents = list(path.iterdir())
            
            # If no contents, directory is empty
            if not contents:
                return True
                
            # Check if all contents are directories and are empty
            return all(item.is_dir() and is_empty_dir(item) for item in contents)
        except PermissionError:
            console.print(f"[yellow]Permission denied accessing {path}[/yellow]")
            return False
        except Exception as e:
            console.print(f"[red]Error checking directory {path}: {str(e)}[/red]")
            return False

    def remove_empty_folders(path):
        """Remove empty folders recursively."""
        if not path.is_dir() or exclude_dir in str(path):
            return False
            
        try:
            # Process all subdirectories first
            for item in path.iterdir():
                if item.is_dir():
                    remove_empty_folders(item)
            
            # After processing subdirectories, check if current directory is empty
            if is_empty_dir(path) and path != directory and exclude_dir not in str(path):
                # Ask user before deleting
                console.print(f"\nFound empty folder: [yellow]{path}[/yellow]")
                if Confirm.ask("Delete this empty folder?", default=True):
                    path.rmdir()
                    console.print(f"[green]Deleted empty folder: {path}[/green]")
                    return True
                
        except PermissionError:
            console.print(f"[yellow]Permission denied accessing {path}[/yellow]")
        except Exception as e:
            console.print(f"[red]Error processing directory {path}: {str(e)}[/red]")
        
        return False

    console.print("\n[cyan]════════════════ Folder Cleanup ════════════════[/cyan]")
    console.print("[yellow]Scanning for empty folders...[/yellow]")
    
    # Start the cleanup process from the root directory
    remove_empty_folders(Path(directory))
    
    console.print("\n[green]Folder cleanup complete.[/green]")

def typewriter_effect(text, delay=0.05, color="rgb(48,209,204)"):
    """Display text with a typewriter effect and optional color."""
    for char in text:
        console.print(char, end='', style=color, highlight=False)
        time.sleep(delay)
    console.print()  # Move to the next line after finishing

def matrix_animation(text, delay=0.05):
    """Animate ASCII art line by line in a matrix style."""
    for line in text.split("\n"):
        console.print(line, style="rgb(48,209,204)", highlight=False)
        time.sleep(delay)

def main():
    def optimize_system():
        """Optimize system settings for better I/O performance."""
        optimization_status = []
        
        # Try to optimize process priority
        try:
            import psutil
            process = psutil.Process(os.getpid())
            
            if os.name == 'nt':  # Windows
                process.nice(psutil.HIGH_PRIORITY_CLASS)
                optimization_status.append("[green]Windows process priority optimization enabled[/green]")
            else:  # Unix-like systems
                process.nice(-10)  # Higher priority on Unix systems
                optimization_status.append("[green]Unix process priority optimization enabled[/green]")
            
            # Optimize I/O priority if possible
            if hasattr(psutil, 'IOPRIO_CLASS_HIGH'):
                process.ionice(psutil.IOPRIO_CLASS_HIGH)
                optimization_status.append("[green]I/O priority optimization enabled[/green]")
                
        except ImportError:
            optimization_status.append("[yellow]Process optimization not available (psutil not installed)[/yellow]")
        except Exception as e:
            optimization_status.append(f"[yellow]Process optimization failed: {str(e)}[/yellow]")

        # Optional: Set Python's internal buffer size
        try:
            import io
            io.DEFAULT_BUFFER_SIZE = 1024 * 1024  # 1MB buffer
            optimization_status.append("[green]Python I/O buffer optimization enabled[/green]")
        except Exception as e:
            optimization_status.append("[yellow]Buffer optimization failed[/yellow]")

        return optimization_status

    clear_console()
    
    # Apply system optimizations and get status
    optimization_status = optimize_system()
    
    # Get current date/time and user info
    current_datetime = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    try:
        current_user = os.getlogin()
    except Exception:
        try:
            import getpass
            current_user = getpass.getuser()
        except Exception:
            current_user = "Unknown"
    
    # Welcome animation
    typewriter_effect(f"Welcome to {APP_NAME} {APP_VERSION}!", color="rgb(48,209,204)")
    matrix_animation(ASCII_ART)  # Glowing neon effect applied here)

    print_header()
    
    # Print session info with better formatting
    console.print("\n[cyan]════════════════ Session Information ════════════════[/cyan]")
    console.print(f"[bold white]Date and Time (UTC):[/bold white] {current_datetime}")
    console.print(f"[bold white]User:[/bold white] {current_user}")
    console.print("\n[cyan]═══════════════ Optimization Status ═══════════════[/cyan]")
    for status in optimization_status:
        console.print(status)
    console.print("[cyan]══════════════════════════════════════════════════[/cyan]\n")

    # Update prompts in main function
    while True:
        directory_input = input("Enter the directory containing the files: ").strip()
        directory = Path(directory_input)
        if directory.is_dir():
            break
        console.print(f"[red]Error: {directory_input} is not a valid directory. Please try again.[/red]")

    # Get critical settings first
    console.print(create_styled_prompt("Scan subdirectories recursively?"))
    recursive = Confirm.ask("", default=True)
    
    console.print(create_styled_prompt("Should archives in the target directory be extracted?"))
    handle_archives_flag = Confirm.ask("", default=True)
    
    # Then get other preferences
    console.print(create_styled_prompt("Do you want to tag filenames with resolution information?"))
    tag_with_resolution = Confirm.ask("", default=False)
    
    console.print(create_styled_prompt("Do you want to perform a dry run?"))
    dry_run = Confirm.ask("", default=False)

    console.print(create_styled_prompt("Show detailed progress when moving exact matches?"))
    show_exact_matches = Confirm.ask("", default=True)

    # Load reference names and refine buzzwords
    reference_files = ['names_1.txt', 'names_2.txt', 'names_3.txt']
    try:
        reference_names = load_reference_names(reference_files)
        refine_buzzwords(reference_files)
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load reference files: {str(e)}[/yellow]")
        reference_names = set()

    # Handle archives first if requested
    extracted_dirs = []
    if handle_archives_flag:
        extracted_dirs = handle_archives(directory)
        if extracted_dirs:
            console.print("\n[yellow]Processing remaining unmatched files...[/yellow]")

    # Always process the main directory
    rename_files(directory, reference_names, tag_with_resolution, 
                recursive=recursive, 
                dry_run=dry_run,
                show_exact_matches=show_exact_matches)  # Make sure this parameter is being passed

    # Process each extracted directory
    for extracted_dir in extracted_dirs:
        console.print(f"\n[yellow]Processing files from archive: {extracted_dir.name}[/yellow]")
        rename_files(extracted_dir, 
                    reference_names, 
                    tag_with_resolution, 
                    recursive=True, 
                    dry_run=dry_run,
                    show_exact_matches=show_exact_matches)  # Make sure this parameter is being passed

    # Add cleanup process for recursive mode
    if recursive:
        console.print("\n[yellow]Checking for empty folders to clean up...[/yellow]")
        cleanup_empty_folders(directory)

    # Final user confirmation before closing
    while True:
        console.print(create_styled_prompt("Processing completed. Do you want to exit the script?"))
        exit_confirm = Confirm.ask("", default=True)
        if exit_confirm:
            break

    # Print session end information
    end_datetime = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    console.print(f"\n[cyan]════════════════ Session Ended ════════════════[/cyan]")
    console.print(f"[bold white]End Time (UTC):[/bold white] {end_datetime}")

if __name__ == "__main__":
    main()
