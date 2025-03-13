import os
import json
import subprocess
import shutil
from pathlib import Path
import tempfile
import traceback
from typing import Optional, Dict, Any, List
import requests
import bibtexparser
import pathspec

DEFAULT_CONFIG = {
    "storage_format": "bib",
    "attachment_mode": "cp",
    "attachment_watch_dir": "~/Downloads",
    "pramaana_path": "~/.pramaana_data",
    "translation_server": "http://localhost:1969",
    "verbose": True,
    "exports": {
        "everything": {
            "source": ["/.exports/*"],
            "destination": "~/.pramaana_data/.exports/all_refs.bib",
        }
    },
}

DEFAULT_TEMPLATES = {
    "article": r"""@article{key,
    title = {Enter title},
    author = {Author1 LastName and Author2 LastName and Author3 LastName},
    journal = {Journal Name},
    year = {2024},
    volume = {},
    number = {},
    pages = {start--end},
    month = {},
    doi = {10.xxxx/xxxxx},
    url = {},
    abstract = {},
    keywords = {keyword1, keyword2, keyword3},
    issn = {},
    publisher = {}
}""",

    "book": r"""@book{key,
    title = {Enter title},
    author = {Author LastName, FirstName and Author2 LastName, FirstName},
    year = {2024},
    publisher = {Publisher Name},
    address = {City, Country},
    isbn = {ISBN-13},
    edition = {Edition number or description},
    volume = {},
    series = {},
    doi = {},
    url = {},
    abstract = {},
    keywords = {keyword1, keyword2, keyword3},
    note = {},
    language = {english}
}""",

    "inproceedings": r"""@inproceedings{key,
    title = {Enter title},
    author = {Author1, FirstName and Author2, FirstName},
    booktitle = {Proceedings of the Conference Name},
    series = {Conference series, if applicable},
    year = {2024},
    month = {},
    pages = {start--end},
    publisher = {},
    address = {Conference Location},
    organization = {Organizing Body},
    doi = {10.xxxx/xxxxx},
    url = {},
    abstract = {},
    keywords = {keyword1, keyword2, keyword3},
    note = {}
}""",

    "techreport": r"""@techreport{key,
    title = {Enter title},
    author = {Author1, FirstName and Author2, FirstName},
    institution = {Institution Name},
    year = {2024},
    month = {},
    number = {Technical Report Number},
    type = {Technical Report},
    address = {Institution Location},
    url = {},
    abstract = {},
    keywords = {keyword1, keyword2, keyword3},
    note = {},
    doi = {}
}""",

    "thesis": r"""@thesis{key,
    title = {Enter title},
    author = {Author LastName, FirstName},
    school = {University Name},
    year = {2024},
    month = {},
    type = {PhD Thesis},  % or {Master's Thesis}, {Bachelor's Thesis}
    address = {University Location},
    url = {},
    doi = {},
    abstract = {},
    keywords = {keyword1, keyword2, keyword3},
    committee = {Advisor Name and Committee Member Names},
    department = {Department Name},
    note = {}
}""",

    "web": r"""@misc{key,
    title = {Page or Resource Title},
    author = {Author or Organization Name},
    year = {2024},
    howpublished = {\url{Enter URL}},
    note = {Accessed: \today},
    organization = {Website or Organization Name},
    url = {},
    abstract = {},
    keywords = {keyword1, keyword2, keyword3},
    language = {english},
    lastaccessed = {\today},
    archiveurl = {},  % Web archive URL if available
    archivedate = {}  % Date of archive snapshot
}""",

    "software": r"""@software{key,
    title = {Software Name},
    author = {Author1, FirstName and Author2, FirstName},
    year = {2024},
    month = {},
    version = {x.y.z},
    url = {},
    doi = {},
    publisher = {},
    organization = {Organization Name},
    repository = {Repository URL},
    programmingLanguage = {Language},
    license = {License Name},
    abstract = {},
    keywords = {keyword1, keyword2, keyword3},
    requirements = {},
    note = {}
}""",

    "dataset": r"""@misc{key,
    title = {Dataset Name},
    author = {Creator1, FirstName and Creator2, FirstName},
    year = {2024},
    month = {},
    note = {Dataset},
    doi = {},
    url = {},
    version = {},
    publisher = {Publishing Organization},
    organization = {Hosting Organization},
    size = {},  % Dataset size
    format = {},  % Data format(s)
    license = {},
    abstract = {},
    keywords = {keyword1, keyword2, keyword3},
    temporalCoverage = {},  % Time period covered
    spatialCoverage = {},   % Geographic coverage if applicable
    methodology = {}        % Brief description of data collection methodology
}""",

    "preprint": r"""@article{key,
    title = {Enter title},
    author = {Author1 LastName and Author2 LastName},
    year = {2024},
    month = {},
    eprint = {},      % e.g., arXiv identifier
    primaryClass = {}, % e.g., cs.AI, math.CO
    archivePrefix = {arXiv},  % or other preprint server
    url = {},
    abstract = {},
    keywords = {keyword1, keyword2, keyword3},
    note = {Preprint},
    version = {},     % Preprint version/revision
    institution = {}, % Author affiliation
    funding = {}      % Funding acknowledgment
}""",

    "patent": r"""@patent{key,
    title = {Patent Title},
    author = {Inventor1 Name and Inventor2 Name},
    year = {2024},
    month = {},
    number = {Patent Number},
    type = {Patent},
    nationality = {Country Code},
    yearfiled = {},
    monthfiled = {},
    assignee = {Organization Name},
    url = {},
    abstract = {},
    keywords = {keyword1, keyword2, keyword3},
    status = {},      % e.g., Applied, Granted, Expired
    filing_date = {}, % Full filing date
    issue_date = {},  % Full issue date if granted
    priority_date = {}
}""",

    "video": r"""@misc{key,
    title = {Video Title},
    author = {Creator Name or Organization},
    year = {2024},
    month = {},
    howpublished = {\url{Video URL}},
    note = {Video},
    duration = {},    % Duration in minutes
    platform = {},    % e.g., YouTube, Vimeo
    channel = {},     % Channel or creator name
    publisher = {},
    url = {},
    abstract = {},
    keywords = {keyword1, keyword2, keyword3},
    language = {english},
    lastaccessed = {\today},
    quality = {},     % e.g., 1080p, 4K
    series = {}       % If part of a series
}"""
}

class PramaanaError(Exception):
    pass


class Pramaana:
    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir or os.path.expanduser("~/.pramaana"))
        self.config_file = self.config_dir / "config.json"
        self.config = self._load_config()
        self.refs_dir = Path(os.path.expanduser(self.config["pramaana_path"]))
        self._load_templates()
        # Check translation server on init
        # self._check_translation_server()

    def _check_translation_server(self):
        """Check if translation server is running"""
        try:
            response = requests.get(
                f"{self.config['translation_server']}/web", timeout=5
            )
            if response.status_code not in (
                400,
                200,
            ):  # 400 is ok, means it wants input
                raise PramaanaError(
                    f"Translation server returned unexpected status: {response.status_code}"
                )
        except requests.exceptions.RequestException as e:
            raise PramaanaError(
                f"Cannot connect to translation server at {self.config['translation_server']}. "
                "Make sure it's running with: docker run -d -p 1969:1969 zotero/translation-server"
                f"{e}"
                f"\n{traceback.format_exc()}"
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
            loaded_config: Dict = json.load(f)
        
        return DEFAULT_CONFIG | loaded_config

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
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 pramaana/0.1.0 (https://github.com/yourusername/pramaana)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        }

        try:
            # First request to get metadata
            response = requests.post(
                f"{self.config['translation_server']}/web",
                data=url,
                headers={"Content-Type": "text/plain", **headers},
                timeout=30,  # Add timeout
            )

            if response.status_code == 500:
                # Try to get more detailed error from response
                try:
                    error_details = response.json()
                    raise PramaanaError(f"Translation server error: {error_details}")
                except Exception as e:
                    raise PramaanaError(
                        f"Translation server error (500) for URL: {url}, {str(e)}"
                        f"\n{traceback.format_exc()}"
                    )

            if response.status_code == 300:
                # Multiple choices, select first one
                data = response.json()
                first_key = list(data["items"].keys())[0]
                selected_items = {first_key: data["items"][first_key]}
                data["items"] = selected_items

                # Make second request with selection
                response = requests.post(
                    f"{self.config['translation_server']}/web",
                    json=data,
                    headers={"Content-Type": "application/json", **headers},
                    timeout=30,
                )

            if response.status_code != 200:
                raise PramaanaError(f"Translation server error: {response.status_code}")

            # Convert to BibTeX
            items = response.json()
            export_response = requests.post(
                f"{self.config['translation_server']}/export?format=bibtex",
                json=items,
                headers={"Content-Type": "application/json", **headers},
                timeout=30,
            )

            if export_response.status_code != 200:
                raise PramaanaError("Failed to convert to BibTeX")

            return {"bibtex": export_response.text, "raw": items}

        except requests.exceptions.Timeout:
            raise PramaanaError(f"Timeout while fetching metadata from {url}")
        except requests.exceptions.RequestException as e:
            raise PramaanaError(f"Network error: {str(e)}\n{traceback.format_exc()}")

    def _handle_attachment(self, ref_dir: Path, attachment_path: Optional[str]):
        """Handle attachment based on configuration

        Args:
            ref_dir: Directory to store the attachment in
            attachment_path: Path to attachment file, or empty string to use latest from watch dir,
                        or None to skip attachment
        """
        if attachment_path is None:
            return  # No attachment requested

        # Helper function to handle a single item (file or directory)
        def process_single_item(src_path: str, ref_dir: Path):
            src_path = Path(src_path)
            dest = ref_dir / src_path.name

            if not src_path.exists():
                raise PramaanaError(f"Path not found: {src_path}")

            if src_path.is_file():
                if self.config["attachment_mode"] == "cp":
                    shutil.copy2(src_path, dest)
                elif self.config["attachment_mode"] == "mv":
                    shutil.move(src_path, dest)
                elif self.config["attachment_mode"] == "ln":
                    os.link(src_path, dest)
                else:
                    raise PramaanaError(
                        f"Invalid attachment mode: {self.config['attachment_mode']}"
                    )
            elif src_path.is_dir():
                # Add safety checks
                total_size = sum(f.stat().st_size for f in src_path.rglob('*') if f.is_file())
                if total_size > 500 * 1024 * 1024:  # 500MB limit
                    response = input(f"Warning: Directory {src_path} is large ({total_size/1024/1024:.1f}MB). Proceed? [y/N] ")
                    if response.lower() != 'y':
                        print("Skipping directory...")
                        return

                if self.config["attachment_mode"] == "mv":
                    shutil.move(src_path, dest)
                else:
                    # For cp and ln, use copytree with appropriate settings
                    shutil.copytree(
                        src_path, 
                        dest,
                        symlinks=False,  # Don't follow symlinks
                        dirs_exist_ok=True,  # Allow merging with existing dirs
                        copy_function=os.link if self.config["attachment_mode"] == "ln" else shutil.copy2
                    )
                print(f"Attached directory: {src_path}")

        # Handle empty string or number
        if attachment_path == "" or attachment_path.isdigit():
            watch_dir = Path(os.path.expanduser(self.config["attachment_watch_dir"]))
            if not watch_dir.exists():
                raise PramaanaError(f"Watch directory not found: {watch_dir}")

            # Get both files and directories
            items = sorted(
                watch_dir.iterdir(),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            if not items:
                raise PramaanaError(f"No items found in watch directory: {watch_dir}")

            # Determine how many items to attach
            n_items = 1 if attachment_path == "" else int(attachment_path)
            if n_items > len(items):
                print(f"Warning: Only {len(items)} items available, using all of them")
                n_items = len(items)

            # Process the items
            for i in range(n_items):
                item_path = str(items[i])
                print(f"Attaching item {i+1}/{n_items}: {item_path}")
                process_single_item(item_path, ref_dir)
            return

        # Handle specific path
        process_single_item(attachment_path, ref_dir)

    def _load_templates(self) -> Dict[str, str]:
        """Load BibTeX templates from config directory"""
        templates = DEFAULT_TEMPLATES.copy()
        template_dir = self.config_dir / "templates"
        
        if not template_dir.exists():
            # Create template directory and save default templates
            template_dir.mkdir(exist_ok=True)
            for name, content in DEFAULT_TEMPLATES.items():
                with open(template_dir / f"{name}.bib", "w") as f:
                    f.write(content)
        else:
            # Load any custom templates
            for template_file in template_dir.glob("*.bib"):
                name = template_file.stem
                with open(template_file) as f:
                    templates[name] = f.read()
        
        return templates

    def _get_template(self, template_name: Optional[str] = None) -> str:
        """Get a BibTeX template by name"""
        templates = self._load_templates()
        
        if template_name is None:
            return templates["article"]  # Default template
            
        if template_name not in templates:
            raise PramaanaError(
                f"Template '{template_name}' not found. Available templates: "
                f"{', '.join(sorted(templates.keys()))}"
            )
        
        return templates[template_name]


    def new(
        self,
        ref_path: str,
        source_url: Optional[str] = None,
        attachment: Optional[str] = None,
        bibtex: Optional[str] = None,
        template: Optional[str] = None,
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
            # Open editor with template
            with tempfile.NamedTemporaryFile(suffix=".bib", mode="w+") as tf:
                tf.write(self._get_template(template))
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
        dest_path = os.path.expanduser(export["destination"])
        print(f"Writing to: {dest_path}")

        # Create pathspec from gitignore-style patterns
        spec = pathspec.PathSpec.from_lines(
            pathspec.patterns.GitWildMatchPattern, export["source"]
        )

        # Collect all references that match the patterns
        all_refs = []
        for bib_file in self.refs_dir.rglob(f"*.{self.config['storage_format']}"):
            rel_path = str(bib_file.relative_to(self.refs_dir))
            if not spec.match_file(rel_path):
                if self.config["verbose"]:
                    print(f"Including file: {bib_file}")
                with open(bib_file) as f:
                    content = f.read().strip()
                    if content:
                        all_refs.append(content)
            else:
                if self.config["verbose"]:
                    print(f"Excluding file: {bib_file}")

        print(f"Writing {len(all_refs)} references to {dest_path}")
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "w", encoding="utf-8") as f:
            content = "\n\n".join(all_refs)
            if content:
                content += "\n"
            f.write(content)

    def export(self, export_names: Optional[List[str]] = None):
        """Run export processing manually

        Args:
            export_names: Optional list of export names to run. If None, runs all exports.
        """
        if not self.config["exports"]:
            raise PramaanaError("No exports configured in config file")

        # If no names provided, run all exports
        if export_names is None:
            export_names = list(self.config["exports"].keys())

        # Validate export names
        invalid_names = [
            name for name in export_names if name not in self.config["exports"]
        ]
        if invalid_names:
            raise PramaanaError(f"Unknown export(s): {', '.join(invalid_names)}")

        # Run selected exports
        for name in export_names:
            print(f"Processing export '{name}'...")
            export = self.config["exports"][name]
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
        # Build grep command with default options for color and filename output
        cmd = ['grep', '--color=auto', '-H']  # -H forces filename output even with single file
        
        # Check if --include is specified in grep_args
        grep_args = grep_args or []
        has_include = any(arg.startswith('--include=') for arg in grep_args)
        
        # If no include pattern specified, add our default
        if not has_include:
            cmd.append(f'--include=*.{self.config["storage_format"]}')
        
        cmd.extend(grep_args)
        cmd.append(pattern)
        
        # Handle search paths
        if paths:
            search_paths = []
            for path in paths:
                search_dir = self.refs_dir / path
                if not search_dir.exists():
                    raise PramaanaError(f"Path not found: {path}")
                # Use rglob with * to get all files, let grep handle filtering
                search_paths.extend(search_dir.rglob("*"))
        else:
            # Use rglob with * to get all files, let grep handle filtering
            search_paths = self.refs_dir.rglob("*")
        
        # Add files to search
        file_list = [str(f) for f in search_paths if f.is_file()]
        if not file_list:
            print("No files to search")
            return
        
        cmd.extend(file_list)
        
        try:
            # Use env to ensure color output even when piped
            env = os.environ.copy()
            env['GREP_COLORS'] = 'mt=01;31:fn=35:ln=32:se=36'  # Standard grep colors
            subprocess.run(cmd, check=False, env=env)
        except subprocess.CalledProcessError as e:
            if e.returncode != 1:  # 1 means no matches, which is fine
                raise PramaanaError(f"grep command failed: {e}")

    def import_zotero(self, bib_file: str, via: str = 'ln'):
        """Import references from BetterBibTeX export
        
        Args:
            bib_file: Path to the BetterBibTeX export file
            via: How to handle attachments - 'ln' (hardlink), 'cp' (copy), or 'mv' (move)
        """
        import re
        if via not in ['ln', 'cp', 'mv']:
            raise PramaanaError(f"Invalid --via option: {via}")
            
        bib_file = os.path.expanduser(bib_file)
        if not os.path.exists(bib_file):
            raise PramaanaError(f"BibTeX file not found: {bib_file}")
        
        # Parse BibTeX file
        with open(bib_file) as f:
            bib_data = bibtexparser.loads(f.read())
        
        for entry in bib_data.entries:
            try:
                # Get collection path and citation key
                collection = entry.get('collection', '').strip('/')  # Remove leading/trailing slashes
                # Remove any BibTeX escaping (backslash followed by any character)
                collection = re.sub(r'\\(.)', r'\1', collection)
                if not collection:
                    collection = 'uncategorized'
                citation_key = entry.get('ID')
                if not citation_key:
                    print(f"Warning: Entry has no citation key, skipping: {entry.get('title', 'Unknown')}")
                    continue
                    
                # Create directory for this reference
                ref_dir = self.refs_dir / collection / citation_key
                ref_dir.mkdir(parents=True, exist_ok=True)
                
                # Save BibTeX
                with open(ref_dir / f"reference.{self.config['storage_format']}", 'w') as f:
                    # Create a new database with just this entry
                    db = bibtexparser.bibdatabase.BibDatabase()
                    db.entries = [entry]
                    f.write(bibtexparser.dumps(db))
                
                # Handle attachments
                files = entry.get('file', '').split(';')
                for file_path in files:
                    if not file_path:
                        continue
                        
                    file_path = os.path.expanduser(file_path)
                    if not os.path.exists(file_path):
                        print(f"Warning: Attachment not found: {file_path}")
                        continue
                    
                    dest = ref_dir / os.path.basename(file_path)
                    if via == 'ln':
                        try:
                            os.link(file_path, dest)
                        except OSError as e:
                            print(f"Warning: Could not create hardlink for {file_path}: {e}")
                            print("Falling back to copy...")
                            shutil.copy2(file_path, dest)
                    elif via == 'cp':
                        shutil.copy2(file_path, dest)
                    else:  # mv
                        shutil.move(file_path, dest)
                        
                print(f"Imported: {collection}/{citation_key}")
                
            except Exception as e:
                print(f"Warning: Failed to import entry {entry.get('ID', 'Unknown')}: {str(e)}")

    def list_refs(self, subdir: Optional[str] = None, ls_args: List[str] = None):
        """List references in tree structure"""
        base_dir = self.refs_dir
        if subdir:
            base_dir = self.refs_dir / subdir
            if not base_dir.exists():
                raise PramaanaError(f"Directory not found: {subdir}")

        # If ls_args provided, use ls directly
        if ls_args:
            cmd = ["ls"] + ls_args + [str(base_dir)]
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e:
                raise PramaanaError(f"ls command failed: {e}\n{traceback.format_exc()}")
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
                        new_prefix = prefix + (
                            prefix_indent_last if is_last else prefix_indent
                        )
                        add_to_tree(item, new_prefix)

            add_to_tree(base_dir)
            return tree_lines

    def remove(self, path: str, rm_args: List[str] = None):
        """Remove a file or directory"""
        full_path = self.refs_dir / path
        if not full_path.exists():
            raise PramaanaError(f"Path not found: {path}")

        if rm_args:
            cmd = ["rm"] + rm_args + [str(full_path)]
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e:
                raise PramaanaError(f"rm command failed: {e}\n{traceback.format_exc()}")
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
            subprocess.run(["trash", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise PramaanaError(
                "trash-cli not found. Please install it with: sudo apt-get install trash-cli"
            )

        cmd = ["trash"] + (trash_args or []) + [str(full_path)]
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
            cmd = ["cat"] + show_args + [str(target)]
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e:
                raise PramaanaError(
                    f"cat command failed: {e}\n{traceback.format_exc()}"
                )
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

        cmd = ["xdg-open"] + (open_args or []) + [str(full_path)]
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            raise PramaanaError(
                f"Failed to open {full_path}: {e}\n{traceback.format_exc()}"
            )

    def move(self, source: str, dest: str, mv_args: List[str] = None):
        """Move a file or directory with optional mv arguments"""
        src_path = self.refs_dir / source
        dest_path = self.refs_dir / dest

        if not src_path.exists():
            raise PramaanaError(f"Source not found: {source}")

        if mv_args:
            cmd = ["mv"] + mv_args + [str(src_path), str(dest_path)]
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e:
                raise PramaanaError(f"mv command failed: {e}\n{traceback.format_exc()}")
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
            cmd = ["cp"] + cp_args + [str(src_path), str(dest_path)]
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e:
                raise PramaanaError(f"cp command failed: {e}\n{traceback.format_exc()}")
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
            cmd = ["ln"] + ln_args + [str(src_path), str(dest_path)]
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e:
                raise PramaanaError(f"ln command failed: {e}")
        else:
            os.makedirs(dest_path.parent, exist_ok=True)
            os.link(str(src_path), str(dest_path))

        # Process exports after linking
        self.export()
