# Pramaana

A minimalist command-line reference manager that works with BibTeX files and the Zotero translation server.

Basically works like Zotero with BetterBibTeX plus Zotmoov (or the earlier Zotfile).

(basically everything was written by Claude -- under construction, nothing to install yet)

## Installation

The recommended way to install Pramaana is using pipx:

```bash
pipx install pramaana
```

This will install Pramaana in an isolated environment while making the `pramaana` command available globally.

## Prerequisites

Pramaana requires the Zotero translation server to be running for URL-based reference imports. You can start it using Docker:

```bash
docker pull zotero/translation-server
docker run -d -p 1969:1969 --rm --name translation-server zotero/translation-server
```

## Usage

Create a new reference:
```bash
pramaana new cs/ai_books/sutton_barto --from https://books.google.com/books?id=GDvW4MNMQ2wC --attach paper.pdf
```

Omit `--from` to write in a bib file manually in your default text editor. Use `--attach` without any arguments (i.e. omit `paper.pdf`) to attach the latest item in `~/Downloads` (can be configured, see later).

Update a reference:

```bash
pramaana edit cs/ai_books/sutton_barto --from https://books.google.com/books?id=GDvW4MNMQ2wC --attach paper.pdf
```

Run all configured exports (see later):

```bash
pramaana export
```

Find in all bibliographic information:

```bash
pramaana find
```

Import from Zotero:

```bash
pramaana import /path/to/zotero_dir
```

## Configuration

Pramaana stores its configuration in `~/.pramaana/config.json`. The default configuration can be customized:

```json
{
  "storage_format": "bib",
  "attachment_mode": "cp",
  "attachment_watch_dir": "~/Downloads",
  "exports": [
      {
          "source": ["/.exports/"],
          "destination": "~/.pramaana/.exports/all_refs.bib"
      }
  ]
}
```

`source` for exports takes gitignore style patterns to exclude and include folders 

## Development

To set up a development environment:

```bash
git clone https://github.com/abhimanyupallavisudhir/pramaana.git
cd pramaana
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -e ".[dev]"
```

## TODO

- [x] make the `.pramaana` references folder configurable
- [x] make sure `pramaana edit` works as intended
- [ ] `pramaana export id` to run only some exports
- [ ] `pramaana ls`, `pramaana rm`, `pramaana trash`, `pramaana cat`
- [ ] Make find command work within folders
- [ ] Make sure importing from Zotero works
- [ ] Package it to automatically 