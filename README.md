# Pramaana

A minimalist command-line reference manager that works with BibTeX files and the Zotero translation server.

(basically everything was written by Claude)

## Installation

The recommended way to install Pramaana is using pipx:

```bash
pipx install pramaana
```

This will install Pramaana in an isolated environment while making the `pramaana` command available globally.

Alternatively, you can install using pip (preferably in a virtual environment):

```bash
pip install pramaana
```

## Prerequisites

Pramaana requires the Zotero translation server to be running for URL-based reference imports. You can start it using Docker:

```bash
docker pull zotero/translation-server
docker run -d -p 1969:1969 --rm --name translation-server zotero/translation-server
```

## Usage

Create a new reference:
```bash
pramaana new cs/ai_books/sutton_barto --from https://books.google.com/books?id=GDvW4MNMQ2wC
```

Add an attachment:
```bash
pramaana new cs/papers/attention --from paper.bib --attach paper.pdf
```

## Configuration

Pramaana stores its configuration in `~/.pramaana/config.json`. The default configuration can be customized:

```json
{
    "storage_format": "bib",
    "attachment_mode": "cp",
    "attachment_watch_dir": "~/Downloads",
    "exports": []
}
```

## Development

To set up a development environment:

```bash
git clone https://github.com/abhimanyupallavisudhir/pramaana.git
cd pramaana
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -e ".[dev]"
```