import os
import json
import subprocess
import shutil
from pathlib import Path
import tempfile
import requests
from typing import Optional, Dict, Any, List
import bibtexparser
from datetime import datetime

TRANSLATION_SERVER = "http://localhost:1969"
DEFAULT_CONFIG = {
    "storage_format": "bib",  # or "csl"
    "attachment_mode": "cp",  # cp, mv, or ln
    "attachment_watch_dir": "~/Downloads",
    "exports": []
}

class PramaanaError(Exception):
    pass

class Pramaana:
    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir or os.path.expanduser("~/.pramaana"))
        self.config_file = self.config_dir / "config.json"
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default if it doesn't exist"""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True)
            
        if not self.config_file.exists():
            with open(self.config_file, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            return DEFAULT_CONFIG
            
        with open(self.config_file) as f:
            return json.load(f)
    
    def _save_config(self):
        """Save current configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

    def _get_reference_dir(self, ref_path: str) -> Path:
        """Get the full path to a reference directory"""
        return self.config_dir / ref_path

    def _fetch_from_url(self, url: str) -> Dict[str, Any]:
        """Fetch metadata from URL using Zotero translation server"""
        try:
            # First request to get metadata
            response = requests.post(
                f"{TRANSLATION_SERVER}/web",
                data=url,
                headers={'Content-Type': 'text/plain'}
            )
            
            if response.status_code == 300:
                # Multiple choices, select first one
                data = response.json()
                first_key = list(data['items'].keys())[0]
                selected_items = {first_key: data['items'][first_key]}
                data['items'] = selected_items
                
                # Make second request with selection
                response = requests.post(
                    f"{TRANSLATION_SERVER}/web",
                    json=data,
                    headers={'Content-Type': 'application/json'}
                )
            
            if response.status_code != 200:
                raise PramaanaError(f"Translation server error: {response.status_code}")
                
            # Convert to BibTeX
            items = response.json()
            export_response = requests.post(
                f"{TRANSLATION_SERVER}/export?format=bibtex",
                json=items,
                headers={'Content-Type': 'application/json'}
            )
            
            if export_response.status_code != 200:
                raise PramaanaError("Failed to convert to BibTeX")
                
            return {'bibtex': export_response.text, 'raw': items}
            
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
        if attachment_path == '':  # Empty string means use latest from watch dir
            watch_dir = Path(os.path.expanduser(self.config['attachment_watch_dir']))
            if not watch_dir.exists():
                raise PramaanaError(f"Watch directory not found: {watch_dir}")
                
            files = sorted(watch_dir.glob('*'), key=lambda x: x.stat().st_mtime, reverse=True)
            if not files:
                raise PramaanaError(f"No files found in watch directory: {watch_dir}")
                
            final_path = str(files[0])
            print(f"Using latest file for attachment: {final_path}")
            
        final_path = os.path.expanduser(final_path)
        if not os.path.exists(final_path):
            raise PramaanaError(f"Attachment not found: {final_path}")
            
        dest = ref_dir / os.path.basename(final_path)
        
        if self.config['attachment_mode'] == 'cp':
            shutil.copy2(final_path, dest)
        elif self.config['attachment_mode'] == 'mv':
            shutil.move(final_path, dest)
        elif self.config['attachment_mode'] == 'ln':
            os.link(final_path, dest)
        else:
            raise PramaanaError(f"Invalid attachment mode: {self.config['attachment_mode']}")

    def new(self, ref_path: str, source_url: Optional[str] = None, 
            attachment: Optional[str] = None, bibtex: Optional[str] = None):
        """Create a new reference"""
        ref_dir = self._get_reference_dir(ref_path)
        
        if ref_dir.exists():
            raise PramaanaError(f"Reference already exists: {ref_path}")
            
        ref_dir.mkdir(parents=True)
        
        # Get reference data
        if source_url:
            data = self._fetch_from_url(source_url)
            bibtex_content = data['bibtex']
        elif bibtex:
            bibtex_content = bibtex
        else:
            # Open editor for manual entry
            with tempfile.NamedTemporaryFile(suffix='.bib', mode='w+') as tf:
                tf.write("@article{key,\n  title = {Enter title},\n  author = {Author Name},\n  year = {2024}\n}")
                tf.flush()
                subprocess.call([os.environ.get('EDITOR', 'vim'), tf.name])
                tf.seek(0)
                bibtex_content = tf.read()
        
        # Save reference
        bib_file = ref_dir / f"reference.{self.config['storage_format']}"
        with open(bib_file, 'w') as f:
            f.write(bibtex_content)
            
        # Handle attachment if provided
        if attachment is not None:
            self._handle_attachment(ref_dir, attachment)
            
        # Process exports
        self._process_exports()
        
    def _process_exports(self):
        """Process configured exports"""
        for export in self.config['exports']:
            sources = export['source']
            dest_path = os.path.expanduser(export['destination'])
            
            # Collect all references from source paths
            all_refs = []
            for source in sources:
                source_dir = self.config_dir / source
                if source_dir.exists():
                    for bib_file in source_dir.rglob(f"*.{self.config['storage_format']}"):
                        with open(bib_file) as f:
                            all_refs.append(f.read())
            
            # Write combined references to destination
            if all_refs:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with open(dest_path, 'w') as f:
                    f.write('\n'.join(all_refs))


    def edit(self, ref_path: str, source_url: Optional[str] = None, 
             attachment: Optional[str] = None, bibtex: Optional[str] = None):
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
            bibtex_content = data['bibtex']
        elif bibtex:
            bibtex_content = bibtex
        else:
            # Open editor with existing content
            with tempfile.NamedTemporaryFile(suffix='.bib', mode='w+') as tf:
                tf.write(existing_bibtex)
                tf.flush()
                subprocess.call([os.environ.get('EDITOR', 'vim'), tf.name])
                tf.seek(0)
                bibtex_content = tf.read()
        
        # Save reference
        with open(bib_file, 'w') as f:
            f.write(bibtex_content)
            
        # Handle attachment if provided
        if attachment:
            self._handle_attachment(ref_dir, attachment)
            
        # Process exports
        self._process_exports()
    
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
                results.append({
                    'path': str(rel_path),
                    'content': content,
                    'file': str(bib_file)
                })
                
        return results
    
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
                    if 'author' in entry and 'year' in entry:
                        first_author = entry['author'].split(' and ')[0].split(',')[0]
                        dir_name = f"imported/{first_author.lower()}_{entry['year']}"
                    else:
                        dir_name = f"imported/{entry.get('ID', 'unknown')}"
                    
                    # Create reference
                    try:
                        self.new(dir_name, bibtex=bibtex)
                        
                        # Look for attachments
                        if 'file' in entry:
                            files = entry['file'].split(';')
                            for file_path in files:
                                if file_path:
                                    full_path = storage_dir / file_path
                                    if full_path.exists():
                                        self._handle_attachment(self._get_reference_dir(dir_name), str(full_path))
                                        
                    except PramaanaError as e:
                        print(f"Warning: Skipping {dir_name}: {str(e)}")
                        
            except Exception as e:
                print(f"Warning: Failed to parse {bib_file}: {str(e)}")
                continue