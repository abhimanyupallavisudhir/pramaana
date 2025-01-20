import os
import json
import subprocess
import shutil
import shlex
from pathlib import Path
import tempfile
import requests
from typing import Optional, Dict, Any, List
import bibtexparser
from datetime import datetime
import pathspec

DEFAULT_CONFIG = {
    "storage_format": "bib",
    "attachment_mode": "cp",
    "attachment_watch_dir": "~/Downloads",
    "pramaana_path": "~/.pramaana_data",
    "translation_server": "http://localhost:1969",  
    "exports": {
        "everything": {
            "source": ["/.exports/*"],
            "destination": "~/.pramaana_data/.exports/all_refs.bib",
        }
    },
}

class PramaanaError(Exception):
    pass


class Pramaana:
    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir or os.path.expanduser("~/.pramaana"))
        self.config_file = self.config_dir / "config.json"
        self.config = self._load_config()
        self.refs_dir = Path(os.path.expanduser(self.config["pramaana_path"]))

        # Check translation server on init
        # self._check_translation_server()

    def _check_translation_server(self):
        """Check if translation server is running"""
        try:
            response = requests.get(
                f"{self.config['translation_server']}/web",
                timeout=5
            )
            if response.status_code not in (400, 200):  # 400 is ok, means it wants input
                raise PramaanaError(f"Translation server returned unexpected status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            raise PramaanaError(
                f"Cannot connect to translation server at {self.config['translation_server']}. "
                "Make sure it's running with: docker run -d -p 1969:1969 zotero/translation-server"
            )

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default if it doesn't exist"""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True)

        if not self.config_file.exists():
            with open(self.config_file, "w") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            return DEFAULT_CONFIG

        with open(self.config_file) as f:
            return json.load(f)

    def _save_config(self):
        """Save current configuration to file"""
        with open(self.config_file, "w") as f:
            json.dump(self.config, f, indent=2)

    def _get_reference_dir(self, ref_path: str) -> Path:
        """Get the full path to a reference directory"""
        return self.refs_dir / ref_path

    def _fetch_from_url(self, url: str) -> Dict[str, Any]:
            """Fetch metadata from URL using Zotero translation server"""
            # Define headers that mimic a real browser + identify our tool
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 pramaana/0.1.0 (https://github.com/yourusername/pramaana)',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
            }

            try:
                # First request to get metadata
                response = requests.post(
                    f"{self.config["translation_server"]}/web",
                    data=url,
                    headers={'Content-Type': 'text/plain', **headers},
                    timeout=30  # Add timeout
                )
                
                if response.status_code == 500:
                    # Try to get more detailed error from response
                    try:
                        error_details = response.json()
                        raise PramaanaError(f"Translation server error: {error_details}")
                    except:
                        raise PramaanaError(f"Translation server error (500) for URL: {url}")
                
                if response.status_code == 300:
                    # Multiple choices, select first one
                    data = response.json()
                    first_key = list(data["items"].keys())[0]
                    selected_items = {first_key: data["items"][first_key]}
                    data["items"] = selected_items
                    
                    # Make second request with selection
                    response = requests.post(
                        f"{self.config["translation_server"]}/web",
                        json=data,
                        headers={'Content-Type': 'application/json', **headers},
                        timeout=30
                    )
                
                if response.status_code != 200:
                    raise PramaanaError(f"Translation server error: {response.status_code}")
                    
                # Convert to BibTeX
                items = response.json()
                export_response = requests.post(
                    f"{self.config["translation_server"]}/export?format=bibtex",
                    json=items,
                    headers={'Content-Type': 'application/json', **headers},
                    timeout=30
                )
                
                if export_response.status_code != 200:
                    raise PramaanaError("Failed to convert to BibTeX")
                    
                return {"bibtex": export_response.text, "raw": items}
                
            except requests.exceptions.Timeout:
                raise PramaanaError(f"Timeout while fetching metadata from {url}")
            except requests.exceptions.RequestException as e:
                raise PramaanaError(f"Network error: {str(e)}")

    def _handle_attachment(self, ref_dir: Path, attachment_path: Optional[str]):
        """Handle attachment based on configuration

        Args:
            ref_dir: Directory to store the attachment in
            attachment_path: Path to attachment file, or empty string to use latest from watch dir,
                        or None to skip attachment
        """
        if attachment_path is None:
            return  # No attachment requested

        final_path = attachment_path
        if attachment_path == "":  # Empty string means use latest from watch dir
            watch_dir = Path(os.path.expanduser(self.config["attachment_watch_dir"]))
            if not watch_dir.exists():
                raise PramaanaError(f"Watch directory not found: {watch_dir}")

            files = sorted(
                watch_dir.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True
            )
            if not files:
                raise PramaanaError(f"No files found in watch directory: {watch_dir}")

            final_path = str(files[0])
            print(f"Using latest file for attachment: {final_path}")

        final_path = os.path.expanduser(final_path)
        if not os.path.exists(final_path):
            raise PramaanaError(f"Attachment not found: {final_path}")

        dest = ref_dir / os.path.basename(final_path)

        if self.config["attachment_mode"] == "cp":
            shutil.copy2(final_path, dest)
        elif self.config["attachment_mode"] == "mv":
            shutil.move(final_path, dest)
        elif self.config["attachment_mode"] == "ln":
            os.link(final_path, dest)
        else:
            raise PramaanaError(
                f"Invalid attachment mode: {self.config['attachment_mode']}"
            )

    def new(
        self,
        ref_path: str,
        source_url: Optional[str] = None,
        attachment: Optional[str] = None,
        bibtex: Optional[str] = None,
    ):
        """Create a new reference"""
        ref_dir = self._get_reference_dir(ref_path)

        if ref_dir.exists():
            raise PramaanaError(f"Reference already exists: {ref_path}")

        ref_dir.mkdir(parents=True)

        # Get reference data
        if source_url:
            data = self._fetch_from_url(source_url)
            bibtex_content = data["bibtex"]
        elif bibtex:
            bibtex_content = bibtex
        else:
            # Open editor for manual entry
            with tempfile.NamedTemporaryFile(suffix=".bib", mode="w+") as tf:
                tf.write(
                    "@article{key,\n  title = {Enter title},\n  author = {Author Name},\n  year = {2024}\n}"
                )
                tf.flush()
                subprocess.call([os.environ.get("EDITOR", "vim"), tf.name])
                tf.seek(0)
                bibtex_content = tf.read()

        # Save reference
        bib_file = ref_dir / f"reference.{self.config['storage_format']}"
        with open(bib_file, "w") as f:
            f.write(bibtex_content)

        # Handle attachment if provided
        if attachment is not None:
            self._handle_attachment(ref_dir, attachment)

        # Process exports
        self.export()


    def _process_export(self, name: str, export: dict):
        """Process a single export configuration"""
        dest_path = os.path.expanduser(export['destination'])
        print(f"Writing to: {dest_path}")
        
        # Create pathspec from gitignore-style patterns
        spec = pathspec.PathSpec.from_lines(
            pathspec.patterns.GitWildMatchPattern,
            export['source']
        )
        
        # Collect all references that match the patterns
        all_refs = []
        for bib_file in self.refs_dir.rglob(f"*.{self.config['storage_format']}"):
            rel_path = str(bib_file.relative_to(self.refs_dir))
            if not spec.match_file(rel_path):
                print(f"Including file: {bib_file}")
                with open(bib_file) as f:
                    content = f.read().strip()
                    if content:
                        all_refs.append(content)
            else:
                print(f"Excluding file: {bib_file}")
        
        print(f"Writing {len(all_refs)} references to {dest_path}")
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, 'w', encoding='utf-8') as f:
            content = '\n\n'.join(all_refs)
            if content:
                content += '\n'
            f.write(content)

    def export(self, export_names: Optional[List[str]] = None):
        """Run export processing manually
        
        Args:
            export_names: Optional list of export names to run. If None, runs all exports.
        """
        if not self.config['exports']:
            raise PramaanaError("No exports configured in config file")
            
        # If no names provided, run all exports
        if export_names is None:
            export_names = list(self.config['exports'].keys())
            
        # Validate export names
        invalid_names = [name for name in export_names if name not in self.config['exports']]
        if invalid_names:
            raise PramaanaError(f"Unknown export(s): {', '.join(invalid_names)}")
            
        # Run selected exports
        for name in export_names:
            print(f"Processing export '{name}'...")
            export = self.config['exports'][name]
            self._process_export(name, export)

    def edit(
        self,
        ref_path: str,
        source_url: Optional[str] = None,
        attachment: Optional[str] = None,
        bibtex: Optional[str] = None,
    ):
        """Edit an existing reference"""
        ref_dir = self._get_reference_dir(ref_path)

        if not ref_dir.exists():
            raise PramaanaError(f"Reference not found: {ref_path}")

        # Get existing BibTeX content
        bib_file = ref_dir / f"reference.{self.config['storage_format']}"
        existing_bibtex = ""
        if bib_file.exists():
            with open(bib_file) as f:
                existing_bibtex = f.read()

        # Get new reference data
        if source_url:
            data = self._fetch_from_url(source_url)
            bibtex_content = data["bibtex"]
        elif bibtex:
            bibtex_content = bibtex
        else:
            # Open editor with existing content
            with tempfile.NamedTemporaryFile(suffix=".bib", mode="w+") as tf:
                tf.write(existing_bibtex)
                tf.flush()
                subprocess.call([os.environ.get("EDITOR", "vim"), tf.name])
                tf.seek(0)
                bibtex_content = tf.read()

        # Save reference
        with open(bib_file, "w") as f:
            f.write(bibtex_content)

        # Handle attachment if provided
        if attachment is not None:
            self._handle_attachment(ref_dir, attachment)

        # Process exports
        self.export()

    def find(self, query: str) -> List[Dict[str, Any]]:
        """Search for references matching query"""
        results = []
        query = query.lower()

        for bib_file in self.config_dir.rglob(f"*.{self.config['storage_format']}"):
            with open(bib_file) as f:
                content = f.read()

            # Simple text search for now - could be enhanced with proper BibTeX parsing
            if query in content.lower():
                rel_path = bib_file.parent.relative_to(self.config_dir)
                results.append(
                    {"path": str(rel_path), "content": content, "file": str(bib_file)}
                )

        return results

    def grep(self, pattern: str, paths: Optional[List[str]] = None, grep_args: List[str] = None):
        """Search references using grep
        
        Args:
            pattern: Search pattern
            paths: Optional list of paths to search in (relative to refs_dir)
            grep_args: Additional arguments to pass to grep
        """
        # Build grep command
        cmd = ['grep'] + (grep_args or [])
        # Add pattern
        cmd.append(pattern)
        
        # Handle search paths
        if paths:
            search_paths = []
            for path in paths:
                search_dir = self.refs_dir / path
                if not search_dir.exists():
                    raise PramaanaError(f"Path not found: {path}")
                search_paths.extend(search_dir.rglob(f"*.{self.config['storage_format']}"))
        else:
            search_paths = self.refs_dir.rglob(f"*.{self.config['storage_format']}")
        
        # Add files to search
        file_list = [str(f) for f in search_paths]
        if not file_list:
            print("No files to search")
            return
        
        cmd.extend(file_list)
        
        try:
            subprocess.run(cmd, check=False)  # Don't check=True as grep returns 1 if no matches
        except subprocess.CalledProcessError as e:
            if e.returncode != 1:  # 1 means no matches, which is fine
                raise PramaanaError(f"grep command failed: {e}")

    def import_zotero(self, zotero_dir: str):
        """Import references from Zotero data directory"""
        zotero_path = Path(os.path.expanduser(zotero_dir))
        if not zotero_path.exists():
            raise PramaanaError(f"Zotero directory not found: {zotero_dir}")

        storage_dir = zotero_path / "storage"
        if not storage_dir.exists():
            raise PramaanaError("Storage directory not found in Zotero directory")

        # Find all .bib files in the Zotero directory
        for bib_file in zotero_path.rglob("*.bib"):
            with open(bib_file) as f:
                bibtex = f.read()

            # Parse BibTeX to get a reasonable directory name
            try:
                bib_data = bibtexparser.loads(bibtex)
                for entry in bib_data.entries:
                    # Create directory name from author/year or title
                    if "author" in entry and "year" in entry:
                        first_author = entry["author"].split(" and ")[0].split(",")[0]
                        dir_name = f"imported/{first_author.lower()}_{entry['year']}"
                    else:
                        dir_name = f"imported/{entry.get('ID', 'unknown')}"

                    # Create reference
                    try:
                        self.new(dir_name, bibtex=bibtex)

                        # Look for attachments
                        if "file" in entry:
                            files = entry["file"].split(";")
                            for file_path in files:
                                if file_path:
                                    full_path = storage_dir / file_path
                                    if full_path.exists():
                                        self._handle_attachment(
                                            self._get_reference_dir(dir_name),
                                            str(full_path),
                                        )

                    except PramaanaError as e:
                        print(f"Warning: Skipping {dir_name}: {str(e)}")

            except Exception as e:
                print(f"Warning: Failed to parse {bib_file}: {str(e)}")
                continue

    def list_refs(self, subdir: Optional[str] = None, ls_args: List[str] = None):
        """List references in tree structure"""
        base_dir = self.refs_dir
        if subdir:
            base_dir = self.refs_dir / subdir
            if not base_dir.exists():
                raise PramaanaError(f"Directory not found: {subdir}")

    
        # If ls_args provided, use ls directly
        if ls_args:
            cmd = ['ls'] + ls_args + [str(base_dir)]
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e:
                raise PramaanaError(f"ls command failed: {e}")
        else:
            # Generate tree structure
            tree_lines = []
            prefix_base = "├── "
            prefix_last = "└── "
            prefix_indent = "│   "
            prefix_indent_last = "    "
            
            def add_to_tree(path: Path, prefix: str = ""):
                items = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
                for i, item in enumerate(items):
                    is_last = i == len(items) - 1
                    curr_prefix = prefix_last if is_last else prefix_base
                    tree_lines.append(f"{prefix}{curr_prefix}{item.name}")
                    if item.is_dir():
                        new_prefix = prefix + (prefix_indent_last if is_last else prefix_indent)
                        add_to_tree(item, new_prefix)
            
            add_to_tree(base_dir)
            return tree_lines

    def remove(self, path: str,  rm_args: List[str] = None):
        """Remove a file or directory"""
        full_path = self.refs_dir / path
        if not full_path.exists():
            raise PramaanaError(f"Path not found: {path}")

        if rm_args:
            cmd = ['rm'] + rm_args + [str(full_path)]
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e:
                raise PramaanaError(f"rm command failed: {e}")
        else:        
            if full_path.is_file():
                full_path.unlink()
            else:
                shutil.rmtree(full_path)
        
        self.export()

    def trash(self, path: str, trash_args: List[str] = None):
        """Move to trash with optional trash-cli arguments"""
        full_path = self.refs_dir / path
        if not full_path.exists():
            raise PramaanaError(f"Path not found: {path}")
        
        # Check if trash-cli is installed
        try:
            subprocess.run(['trash', '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise PramaanaError("trash-cli not found. Please install it with: sudo apt-get install trash-cli")
        
        cmd = ['trash'] + (trash_args or []) + [str(full_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise PramaanaError(f"Failed to trash {path}: {result.stderr}")
        
        self.export()

    def show(self, path: str, show_args: List[str] = None):
        """Show contents with optional cat arguments"""
        full_path = self.refs_dir / path
        if not full_path.exists():
            raise PramaanaError(f"Path not found: {path}")
        
        if full_path.is_file():
            target = full_path
        else:
            # Find bibliography file
            bib_files = list(full_path.glob(f"*.{self.config['storage_format']}"))
            if not bib_files:
                raise PramaanaError(f"No bibliography file found in {path}")
            target = bib_files[0]
        
        if show_args:
            cmd = ['cat'] + show_args + [str(target)]
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e:
                raise PramaanaError(f"cat command failed: {e}")
        else:
            with open(target) as f:
                return f.read()

    def open(self, path: Optional[str] = None, open_args: List[str] = None):
        """Open with optional xdg-open arguments
        
        Args:
            path: Optional path to open. If None, opens the root references directory.
            open_args: Additional arguments for xdg-open
        """
        if path:
            full_path = self.refs_dir / path
            if not full_path.exists():
                raise PramaanaError(f"Path not found: {path}")
        else:
            full_path = self.refs_dir
            
        cmd = ['xdg-open'] + (open_args or []) + [str(full_path)]
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            raise PramaanaError(f"Failed to open {full_path}: {e}")

    def move(self, source: str, dest: str, mv_args: List[str] = None):
        """Move a file or directory with optional mv arguments"""
        src_path = self.refs_dir / source
        dest_path = self.refs_dir / dest
        
        if not src_path.exists():
            raise PramaanaError(f"Source not found: {source}")
            
        if mv_args:
            cmd = ['mv'] + mv_args + [str(src_path), str(dest_path)]
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e:
                raise PramaanaError(f"mv command failed: {e}")
        else:
            os.makedirs(dest_path.parent, exist_ok=True)
            shutil.move(str(src_path), str(dest_path))
        
        # Process exports after moving
        self.export()

    def copy(self, source: str, dest: str, cp_args: List[str] = None):
        """Copy a file or directory with optional cp arguments"""
        src_path = self.refs_dir / source
        dest_path = self.refs_dir / dest
        
        if not src_path.exists():
            raise PramaanaError(f"Source not found: {source}")
            
        if cp_args:
            cmd = ['cp'] + cp_args + [str(src_path), str(dest_path)]
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e:
                raise PramaanaError(f"cp command failed: {e}")
        else:
            os.makedirs(dest_path.parent, exist_ok=True)
            if src_path.is_dir():
                shutil.copytree(str(src_path), str(dest_path))
            else:
                shutil.copy2(str(src_path), str(dest_path))
        
        # Process exports after copying
        self.export()

    def link(self, source: str, dest: str, ln_args: List[str] = None):
        """Create a link with optional ln arguments"""
        src_path = self.refs_dir / source
        dest_path = self.refs_dir / dest
        
        if not src_path.exists():
            raise PramaanaError(f"Source not found: {source}")
            
        if ln_args:
            cmd = ['ln'] + ln_args + [str(src_path), str(dest_path)]
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e:
                raise PramaanaError(f"ln command failed: {e}")
        else:
            os.makedirs(dest_path.parent, exist_ok=True)
            os.link(str(src_path), str(dest_path))
        
        # Process exports after linking
        self.export()