#!/usr/bin/env python3
"""
Markdown Todo Manager - A TUI application for managing todo items from markdown files
with Vim-like keybindings and customizable keymaps.
"""

import os
import re
import sys
import glob
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import urwid

# Configuration
CONFIG_DIR = os.path.expanduser("~/.config/mdtodo")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
DEFAULT_KEYMAP = {
    "quit": "q",
    "add": "a",
    "edit": "e",
    "delete": "d",
    "toggle": "space",
    "save": "w",
    "move_up": "k",
    "move_down": "j",
    "category_prev": "h",
    "category_next": "l",
    "help": "?",
    "reload": "r",
}

# Todo item regex pattern
TODO_PATTERN = r"- \[([ xX])\] (.+?)(?:\s+#(\w+))?\s*$"

class TodoItem:
    """Represents a single todo item with text, status, and category."""
    def __init__(self, text: str, done: bool = False, category: str = ""):
        self.text = text
        self.done = done
        self.category = category or "uncategorized"
    
    def toggle(self):
        """Toggle the done status of the todo item."""
        self.done = not self.done
    
    def to_markdown(self) -> str:
        """Convert the todo item to markdown format."""
        mark = "x" if self.done else " "
        category_text = f" #{self.category}" if self.category and self.category != "uncategorized" else ""
        return f"- [{mark}] {self.text}{category_text}"


class TodoList:
    """Manages a collection of todo items from markdown files."""
    def __init__(self, directory: str):
        self.directory = os.path.expanduser(directory)
        self.todo_files = {}
        self.todos = []
        self.categories = set(["uncategorized"])
        self.load_todos()
    
    def load_todos(self):
        """Load todo items from markdown files in the directory."""
        self.todos = []
        self.todo_files = {}
        
        # Create the directory if it doesn't exist
        todo_dir = os.path.join(self.directory, "todo")
        os.makedirs(todo_dir, exist_ok=True)
        
        # Find all markdown files in the todo directory
        md_files = glob.glob(os.path.join(todo_dir, "*.md"))
        
        for file_path in md_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Extract todo items using regex
            for line in content.splitlines():
                match = re.match(TODO_PATTERN, line)
                if match:
                    mark, text, category = match.groups()
                    done = mark.lower() == "x"
                    category = category or "uncategorized"
                    self.categories.add(category)
                    todo = TodoItem(text, done, category)
                    self.todos.append(todo)
                    
                    # Track which file this todo came from
                    file_name = os.path.basename(file_path)
                    self.todo_files[todo] = file_name
    
    def save_todos(self):
        """Save todo items back to markdown files by category."""
        # Group todos by file
        todos_by_file = {}
        for todo in self.todos:
            file_name = self.todo_files.get(todo)
            if not file_name:
                # If this is a new todo, assign it to a category file
                file_name = f"{todo.category}.md"
                self.todo_files[todo] = file_name
            
            if file_name not in todos_by_file:
                todos_by_file[file_name] = []
            todos_by_file[file_name].append(todo)
        
        # Write todos to files
        todo_dir = os.path.join(self.directory, "todo")
        for file_name, todos in todos_by_file.items():
            file_path = os.path.join(todo_dir, file_name)
            
            # Group todos by done status
            done_todos = [todo for todo in todos if todo.done]
            not_done_todos = [todo for todo in todos if not todo.done]
            
            with open(file_path, 'w', encoding='utf-8') as f:
                # Write header
                category_name = file_name.replace('.md', '')
                f.write(f"# {category_name.capitalize()} Tasks\n\n")
                
                # Write not done todos first
                if not_done_todos:
                    f.write("## Active\n\n")
                    for todo in not_done_todos:
                        f.write(f"{todo.to_markdown()}\n")
                    f.write("\n")
                
                # Write done todos
                if done_todos:
                    f.write("## Completed\n\n")
                    for todo in done_todos:
                        f.write(f"{todo.to_markdown()}\n")
            
    def add_todo(self, text: str, category: str = ""):
        """Add a new todo item."""
        category = category or "uncategorized"
        self.categories.add(category)
        todo = TodoItem(text, False, category)
        self.todos.append(todo)
        return todo
    
    def delete_todo(self, todo):
        """Delete a todo item."""
        if todo in self.todos:
            self.todos.remove(todo)
            if todo in self.todo_files:
                del self.todo_files[todo]
    
    def get_todos_by_category(self, category: str) -> List[TodoItem]:
        """Get a list of todos filtered by category."""
        return [todo for todo in self.todos if todo.category == category]
    
    def get_categories(self) -> List[str]:
        """Get a sorted list of all categories."""
        return sorted(list(self.categories))


class TodoApp:
    """TUI application for managing todos with vim-like keybindings."""
    def __init__(self, directory: str):
        self.todo_list = TodoList(directory)
        self.keymap = self.load_keymap()
        self.current_category_idx = 0
        self.selected_idx = 0
        self.footer_text = ""
        self.init_ui()
    
    def load_keymap(self) -> Dict[str, str]:
        """Load custom keymap from config file or use default."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    custom_keymap = json.load(f)
                    # Merge with defaults for any missing keys
                    return {**DEFAULT_KEYMAP, **custom_keymap}
            except Exception as e:
                self.footer_text = f"Error loading keymap: {e}"
        
        # Ensure config directory exists
        os.makedirs(CONFIG_DIR, exist_ok=True)
        
        # Save default keymap if no config exists
        if not os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'w') as f:
                json.dump(DEFAULT_KEYMAP, f, indent=2)
        
        return DEFAULT_KEYMAP
    
    def init_ui(self):
        """Initialize the UI components."""
        # Color palette
        self.palette = [
            ('header', 'white,bold', 'dark blue'),
            ('footer', 'white', 'dark red'),
            ('selected', 'black', 'light gray'),
            ('todo', 'light gray', 'black'),
            ('done', 'dark gray', 'black'),
            ('category', 'yellow', 'black'),
            ('selected_category', 'yellow,bold', 'dark blue'),
            ('help', 'light green', 'black'),
        ]
        
        # Header
        self.header_text = urwid.Text(('header', " Markdown Todo Manager "), align='center')
        self.header = urwid.AttrMap(self.header_text, 'header')
        
        # Footer for status messages and help
        self.footer_text = urwid.Text(('footer', " Press ? for help "))
        self.footer = urwid.AttrMap(self.footer_text, 'footer')
        
        # Todo list
        self.todo_walker = urwid.SimpleFocusListWalker([])
        self.todo_listbox = urwid.ListBox(self.todo_walker)
        
        # Category tabs
        self.category_tabs = urwid.Text('')
        self.update_category_tabs()
        
        # Main layout
        self.layout = urwid.Frame(
            body=self.todo_listbox,
            header=urwid.Pile([self.header, self.category_tabs]),
            footer=self.footer
        )
        
        # Main loop
        self.loop = urwid.MainLoop(
            self.layout,
            self.palette,
            unhandled_input=self.handle_input
        )
        
        # Initial UI update
        self.update_todo_list()
    
    def update_category_tabs(self):
        """Update the category tabs display."""
        categories = self.todo_list.get_categories()
        if self.current_category_idx >= len(categories):
            self.current_category_idx = 0
        
        tabs = []
        for i, category in enumerate(categories):
            if i == self.current_category_idx:
                tabs.append(('selected_category', f" {category} "))
            else:
                tabs.append(('category', f" {category} "))
        
        self.category_tabs.set_text(tabs)
    
    def update_todo_list(self):
        """Update the todo list display based on the current category."""
        categories = self.todo_list.get_categories()
        if not categories:
            self.todo_walker[:] = [urwid.Text("No categories found")]
            return
        
        current_category = categories[self.current_category_idx]
        todos = self.todo_list.get_todos_by_category(current_category)
        
        # If selection is out of bounds, reset it
        if self.selected_idx >= len(todos):
            self.selected_idx = max(0, len(todos) - 1)
        
        widgets = []
        for i, todo in enumerate(todos):
            text = todo.text
            if todo.done:
                checkbox = "☒"  # Checked box
                style = 'done'
            else:
                checkbox = "☐"  # Unchecked box
                style = 'todo'
            
            text_widget = urwid.Text([('', f" {checkbox} "), (style, text)])
            if i == self.selected_idx:
                widgets.append(urwid.AttrMap(text_widget, 'selected'))
            else:
                widgets.append(urwid.AttrMap(text_widget, style))
        
        if not widgets:
            widgets = [urwid.Text(f"No todos in category '{current_category}'. Press '{self.keymap['add']}' to add one.")]
        
        self.todo_walker[:] = widgets
    
    def handle_input(self, key):
        """Handle keyboard input based on the keymap."""
        # Convert key to string if it's not already
        if isinstance(key, tuple):
            return
        
        key = str(key)
        
        # Handle input based on keymap
        if key == self.keymap['quit']:
            raise urwid.ExitMainLoop()
            
        elif key == self.keymap['save']:
            self.todo_list.save_todos()
            self.set_footer_text("Todos saved successfully!")
            
        elif key == self.keymap['reload']:
            self.todo_list.load_todos()
            self.update_category_tabs()
            self.update_todo_list()
            self.set_footer_text("Reloaded todos from files")
            
        elif key == self.keymap['add']:
            self.show_add_dialog()
            
        elif key == self.keymap['category_prev']:
            categories = self.todo_list.get_categories()
            if categories:
                self.current_category_idx = (self.current_category_idx - 1) % len(categories)
                self.selected_idx = 0
                self.update_category_tabs()
                self.update_todo_list()
                
        elif key == self.keymap['category_next']:
            categories = self.todo_list.get_categories()
            if categories:
                self.current_category_idx = (self.current_category_idx + 1) % len(categories)
                self.selected_idx = 0
                self.update_category_tabs()
                self.update_todo_list()
                
        elif key == self.keymap['move_up']:
            if self.selected_idx > 0:
                self.selected_idx -= 1
                self.update_todo_list()
                
        elif key == self.keymap['move_down']:
            categories = self.todo_list.get_categories()
            if categories:
                current_category = categories[self.current_category_idx]
                todos = self.todo_list.get_todos_by_category(current_category)
                if self.selected_idx < len(todos) - 1:
                    self.selected_idx += 1
                    self.update_todo_list()
                    
        elif key == self.keymap['toggle']:
            categories = self.todo_list.get_categories()
            if categories:
                current_category = categories[self.current_category_idx]
                todos = self.todo_list.get_todos_by_category(current_category)
                if todos and 0 <= self.selected_idx < len(todos):
                    todos[self.selected_idx].toggle()
                    self.update_todo_list()
                    self.set_footer_text(f"Toggled: {todos[self.selected_idx].text}")
                    
        elif key == self.keymap['delete']:
            categories = self.todo_list.get_categories()
            if categories:
                current_category = categories[self.current_category_idx]
                todos = self.todo_list.get_todos_by_category(current_category)
                if todos and 0 <= self.selected_idx < len(todos):
                    todo = todos[self.selected_idx]
                    self.show_delete_dialog(todo)
                    
        elif key == self.keymap['edit']:
            categories = self.todo_list.get_categories()
            if categories:
                current_category = categories[self.current_category_idx]
                todos = self.todo_list.get_todos_by_category(current_category)
                if todos and 0 <= self.selected_idx < len(todos):
                    self.show_edit_dialog(todos[self.selected_idx])
                    
        elif key == self.keymap['help']:
            self.show_help_dialog()
    
    def set_footer_text(self, text):
        """Set footer text with a timeout to clear after a few seconds."""
        self.footer_text.set_text(('footer', f" {text} "))
        self.loop.set_alarm_in(3, lambda loop, data: self.footer_text.set_text(('footer', " Press ? for help ")))
    
    def show_dialog(self, widget, width=60, height=10):
        """Show a dialog box in the center of the screen."""
        overlay = urwid.Overlay(
            widget,
            self.layout,
            'center', width,
            'middle', height
        )
        self.loop.widget = overlay
        
    def show_help_dialog(self):
        """Show help dialog with keybindings."""
        text = [
            ('header', " Keybindings "),
            "\n\n"
        ]
        
        for action, key in self.keymap.items():
            text.extend([('help', f" {key} "), f": {action.replace('_', ' ')}\n"])
            
        text.extend([
            "\n",
            ('help', " Configuration: "), f"{CONFIG_FILE}\n",
            "\n",
            ('header', " Press any key to close ")
        ])
        
        content = urwid.Padding(urwid.Text(text), left=1, right=1)
        frame = urwid.Frame(
            urwid.LineBox(content),
            header=urwid.AttrMap(urwid.Text(" Help ", align='center'), 'header')
        )
        
        def close_help(key):
            self.loop.widget = self.layout
            
        help_dialog = urwid.Filler(frame)
        urwid.connect_signal(help_dialog, 'key_press', close_help)
        
        self.show_dialog(help_dialog, width=50, height=20)
        
    def show_add_dialog(self):
        """Show dialog to add a new todo."""
        categories = self.todo_list.get_categories()
        current_category = categories[self.current_category_idx]
        
        text_edit = urwid.Edit("Task: ")
        category_edit = urwid.Edit("Category: ", edit_text=current_category)
        
        save_button = urwid.Button("Save")
        cancel_button = urwid.Button("Cancel")
        
        pile = urwid.Pile([
            text_edit,
            urwid.Divider(),
            category_edit,
            urwid.Divider(),
            urwid.Columns([
                urwid.Padding(save_button, width=10, align='left'),
                urwid.Padding(cancel_button, width=10, align='right')
            ])
        ])
        
        box = urwid.LineBox(urwid.Padding(pile, left=1, right=1))
        frame = urwid.Frame(
            box,
            header=urwid.AttrMap(urwid.Text(" Add New Todo ", align='center'), 'header')
        )
        
        def on_save(button):
            text = text_edit.edit_text.strip()
            category = category_edit.edit_text.strip() or "uncategorized"
            
            if text:
                todo = self.todo_list.add_todo(text, category)
                
                # Update category index if a new category was added
                categories = self.todo_list.get_categories()
                if category in categories:
                    self.current_category_idx = categories.index(category)
                
                self.update_category_tabs()
                self.update_todo_list()
                self.set_footer_text(f"Added: {text}")
            
            self.loop.widget = self.layout
            
        def on_cancel(button):
            self.loop.widget = self.layout
            
        urwid.connect_signal(save_button, 'click', on_save)
        urwid.connect_signal(cancel_button, 'click', on_cancel)
        
        self.show_dialog(frame)
        
    def show_edit_dialog(self, todo):
        """Show dialog to edit an existing todo."""
        text_edit = urwid.Edit("Task: ", edit_text=todo.text)
        category_edit = urwid.Edit("Category: ", edit_text=todo.category)
        
        save_button = urwid.Button("Save")
        cancel_button = urwid.Button("Cancel")
        
        pile = urwid.Pile([
            text_edit,
            urwid.Divider(),
            category_edit,
            urwid.Divider(),
            urwid.Columns([
                urwid.Padding(save_button, width=10, align='left'),
                urwid.Padding(cancel_button, width=10, align='right')
            ])
        ])
        
        box = urwid.LineBox(urwid.Padding(pile, left=1, right=1))
        frame = urwid.Frame(
            box,
            header=urwid.AttrMap(urwid.Text(" Edit Todo ", align='center'), 'header')
        )
        
        def on_save(button):
            old_category = todo.category
            
            # Update the todo
            todo.text = text_edit.edit_text.strip()
            todo.category = category_edit.edit_text.strip() or "uncategorized"
            
            # Update category and selection
            categories = self.todo_list.get_categories()
            if todo.category in categories:
                self.current_category_idx = categories.index(todo.category)
            
            self.update_category_tabs()
            self.update_todo_list()
            self.set_footer_text(f"Updated: {todo.text}")
            
            self.loop.widget = self.layout
            
        def on_cancel(button):
            self.loop.widget = self.layout
            
        urwid.connect_signal(save_button, 'click', on_save)
        urwid.connect_signal(cancel_button, 'click', on_cancel)
        
        self.show_dialog(frame)
        
    def show_delete_dialog(self, todo):
        """Show confirmation dialog for deleting a todo."""
        text = urwid.Text(f"Delete todo: {todo.text}?")
        
        yes_button = urwid.Button("Yes")
        no_button = urwid.Button("No")
        
        pile = urwid.Pile([
            text,
            urwid.Divider(),
            urwid.Columns([
                urwid.Padding(yes_button, width=10, align='left'),
                urwid.Padding(no_button, width=10, align='right')
            ])
        ])
        
        box = urwid.LineBox(urwid.Padding(pile, left=1, right=1))
        frame = urwid.Frame(
            box,
            header=urwid.AttrMap(urwid.Text(" Confirm Delete ", align='center'), 'header')
        )
        
        def on_yes(button):
            self.todo_list.delete_todo(todo)
            self.update_todo_list()
            self.set_footer_text(f"Deleted todo")
            self.loop.widget = self.layout
            
        def on_no(button):
            self.loop.widget = self.layout
            
        urwid.connect_signal(yes_button, 'click', on_yes)
        urwid.connect_signal(no_button, 'click', on_no)
        
        self.show_dialog(frame, width=50, height=10)
    
    def run(self):
        """Run the application main loop."""
        self.loop.run()


def main():
    """Main entry point for the application."""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Markdown Todo Manager with Vim-like keybindings")
    parser.add_argument("--dir", "-d", type=str, default="~/mdtodo",
                      help="Directory to store todo files (default: ~/mdtodo)")
    args = parser.parse_args()
    
    # Run the application
    app = TodoApp(args.dir)
    try:
        app.run()
    except KeyboardInterrupt:
        # Save on exit
        app.todo_list.save_todos()
        print("Todos saved. Goodbye!")


if __name__ == "__main__":
    main()
