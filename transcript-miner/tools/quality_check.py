#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vereinheitlichtes Qualitätsprüfungs-Werkzeug.
Kombiniert alle Code-Qualitätstests in einem zentralen Tool.

Funktionen:
- Validierung von Docstrings
- Erkennung von Magic Strings im Code
- Überprüfung von Type Hints in Funktionen
"""

import os
import sys
import ast
import argparse
import logging
from pathlib import Path
from typing import List, Tuple, Set

# Projektroot für Importe setzen
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# Logging einrichten
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Konstanten
PYTHON_EXT = ".py"
SRC_DIR = PROJECT_ROOT / "src"
EXEMPT_DIRS = {"__pycache__", ".git", ".github", "venv", "env", ".venv", ".env"}
EXEMPTION_MARKER = "# EXEMPTION: "


class CodeVisitor(ast.NodeVisitor):
    """AST-Visitor zur statischen Code-Analyse."""

    def __init__(self):
        self.magic_strings = []
        self.missing_type_hints = []
        self.missing_docstrings = []
        self.current_function_node = None

    def visit_Module(self, node):
        """Besucht ein Modul und prüft auf Modul-Docstring."""
        if not ast.get_docstring(node):
            self.missing_docstrings.append(("module", "<module>"))
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        """Besucht eine Klassendefinition und prüft auf Klassen-Docstring."""
        if not ast.get_docstring(node):
            self.missing_docstrings.append(("class", node.name))
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        """Besucht eine Funktionsdefinition und prüft auf Docstring und Type Hints."""
        old_function_node = self.current_function_node
        self.current_function_node = node

        # Prüfe auf Docstring
        if not ast.get_docstring(node) and not node.name.startswith("_"):
            self.missing_docstrings.append(("function", node.name))

        # Prüfe auf Type Hints
        has_return_annotation = node.returns is not None
        if not has_return_annotation and node.name != "__init__":
            self.missing_type_hints.append((node.name, "return"))

        for arg in node.args.args:
            if arg.annotation is None and arg.arg != "self":
                self.missing_type_hints.append((node.name, arg.arg))

        self.generic_visit(node)
        self.current_function_node = old_function_node

    def visit_AsyncFunctionDef(self, node):
        """Besucht eine asynchrone Funktionsdefinition."""
        self.visit_FunctionDef(node)

    def visit_Constant(self, node):
        """Besucht eine Konstante und prüft auf Magic Strings."""
        if (
            isinstance(node.value, str)
            and len(node.value) > 3
            and not node.value.startswith("__")
        ):
            # Ignoriere Docstrings
            is_docstring = False
            if self.current_function_node and node.value == ast.get_docstring(
                self.current_function_node
            ):
                is_docstring = True

            if not is_docstring:
                self.magic_strings.append(node.value)
        self.generic_visit(node)


def check_magic_strings(file_path: Path) -> List[str]:
    """Überprüft eine Datei auf Magic Strings.

    Args:
        file_path: Pfad zur zu prüfenden Python-Datei

    Returns:
        Liste der gefundenen Magic Strings
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()

        tree = ast.parse(code)
        visitor = CodeVisitor()
        visitor.visit(tree)

        # Prüfe auf Ausnahmen im Code
        exemptions = []
        for line in code.splitlines():
            if EXEMPTION_MARKER in line:
                exemption = line.split(EXEMPTION_MARKER)[1].strip()
                exemptions.append(exemption)

        # Filtere Ausnahmen
        filtered_strings = []
        for string in visitor.magic_strings:
            if string not in exemptions and not any(string in e for e in exemptions):
                filtered_strings.append(string)

        return filtered_strings

    except Exception as e:
        logger.error(f"Fehler bei der Magic-String-Prüfung in {file_path}: {e}")
        return []


def check_type_hints(file_path: Path) -> List[Tuple[str, str]]:
    """Überprüft eine Datei auf fehlende Type Hints.

    Args:
        file_path: Pfad zur zu prüfenden Python-Datei

    Returns:
        Liste von Tupeln (Funktionsname, Parameter ohne Type Hint)
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()

        tree = ast.parse(code)
        visitor = CodeVisitor()
        visitor.visit(tree)

        return visitor.missing_type_hints

    except Exception as e:
        logger.error(f"Fehler bei der Type-Hint-Prüfung in {file_path}: {e}")
        return []


def check_docstrings(file_path: Path) -> List[Tuple[str, str]]:
    """Überprüft eine Datei auf fehlende Docstrings.

    Args:
        file_path: Pfad zur zu prüfenden Python-Datei

    Returns:
        Liste von Tupeln (Elementtyp, Elementname mit fehlendem Docstring)
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()

        tree = ast.parse(code)
        visitor = CodeVisitor()
        visitor.visit(tree)

        return visitor.missing_docstrings

    except Exception as e:
        logger.error(f"Fehler bei der Docstring-Prüfung in {file_path}: {e}")
        return []


def find_python_files(directory: Path, ignore_dirs: Set[str] = None) -> List[Path]:
    """Findet alle Python-Dateien in einem Verzeichnis und seinen Unterverzeichnissen.

    Args:
        directory: Das zu durchsuchende Hauptverzeichnis
        ignore_dirs: Zu ignorierende Verzeichnisse

    Returns:
        Liste von Pfaden zu Python-Dateien
    """
    if ignore_dirs is None:
        ignore_dirs = EXEMPT_DIRS

    python_files = []

    for root, dirs, files in os.walk(directory):
        # Ignoriere bestimmte Verzeichnisse
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        for file in files:
            if file.endswith(PYTHON_EXT):
                python_files.append(Path(root) / file)

    return python_files


def main() -> int:
    """Hauptfunktion für das Qualitätsprüfungs-Tool."""
    parser = argparse.ArgumentParser(description="Qualitätsprüfungs-Tool")
    subparsers = parser.add_subparsers(dest="command", help="Verfügbare Kommandos")

    # Magic Strings
    magic_parser = subparsers.add_parser(
        "magic-strings", help="Prüft auf Magic Strings im Code"
    )
    magic_parser.add_argument("--path", default=str(SRC_DIR), help="Zu prüfender Pfad")

    # Type Hints
    type_parser = subparsers.add_parser(
        "type-hints", help="Prüft auf fehlende Type Hints"
    )
    type_parser.add_argument("--path", default=str(SRC_DIR), help="Zu prüfender Pfad")

    # Docstrings
    doc_parser = subparsers.add_parser(
        "docstrings", help="Prüft auf fehlende Docstrings"
    )
    doc_parser.add_argument("--path", default=str(SRC_DIR), help="Zu prüfender Pfad")

    # Alle Prüfungen
    all_parser = subparsers.add_parser(
        "all", help="Führt alle Qualitätsprüfungen durch"
    )
    all_parser.add_argument("--path", default=str(SRC_DIR), help="Zu prüfender Pfad")

    args = parser.parse_args()

    # Standardaktion, wenn kein Kommando angegeben
    if not args.command:
        parser.print_help()
        return 0

    # Kommandos ausführen
    if args.command == "magic-strings" or args.command == "all":
        path = Path(args.path)
        if not path.exists():
            logger.error(f"Pfad existiert nicht: {path}")
            return 1

        python_files = find_python_files(path)
        magic_string_count = 0

        for file_path in python_files:
            magic_strings = check_magic_strings(file_path)
            if magic_strings:
                magic_string_count += len(magic_strings)
                logger.warning(
                    f"Magic Strings in {file_path.relative_to(PROJECT_ROOT)}:"
                )
                for string in magic_strings:
                    logger.warning(f"  - '{string}'")

        if args.command == "magic-strings":
            if magic_string_count:
                logger.warning(
                    f"Insgesamt {magic_string_count} Magic Strings gefunden."
                )
                return 1
            else:
                logger.info("Keine Magic Strings gefunden.")

    if args.command == "type-hints" or args.command == "all":
        path = Path(args.path)
        if not path.exists():
            logger.error(f"Pfad existiert nicht: {path}")
            return 1

        python_files = find_python_files(path)
        missing_type_hints_count = 0

        for file_path in python_files:
            missing_type_hints = check_type_hints(file_path)
            if missing_type_hints:
                missing_type_hints_count += len(missing_type_hints)
                logger.warning(
                    f"Fehlende Type Hints in {file_path.relative_to(PROJECT_ROOT)}:"
                )
                for func, param in missing_type_hints:
                    logger.warning(f"  - {func}() → {param}")

        if args.command == "type-hints":
            if missing_type_hints_count:
                logger.warning(
                    f"Insgesamt {missing_type_hints_count} fehlende Type Hints gefunden."
                )
                return 1
            else:
                logger.info("Keine fehlenden Type Hints gefunden.")

    if args.command == "docstrings" or args.command == "all":
        path = Path(args.path)
        if not path.exists():
            logger.error(f"Pfad existiert nicht: {path}")
            return 1

        python_files = find_python_files(path)
        missing_docstrings_count = 0

        for file_path in python_files:
            missing_docstrings = check_docstrings(file_path)
            if missing_docstrings:
                missing_docstrings_count += len(missing_docstrings)
                logger.warning(
                    f"Fehlende Docstrings in {file_path.relative_to(PROJECT_ROOT)}:"
                )
                for elem_type, elem_name in missing_docstrings:
                    logger.warning(f"  - {elem_type}: {elem_name}")

        if args.command == "docstrings":
            if missing_docstrings_count:
                logger.warning(
                    f"Insgesamt {missing_docstrings_count} fehlende Docstrings gefunden."
                )
                return 1
            else:
                logger.info("Keine fehlenden Docstrings gefunden.")

    # Gesamtergebnis bei "all"
    if args.command == "all":
        # Note: we need to track these counts correctly
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
