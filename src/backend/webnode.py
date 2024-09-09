# webnode.py
from urllib.parse import urlparse
from rich.tree import Tree
from collections import defaultdict

class WebNode:
    def __init__(self, url, descriptor=None):
        self.url = url
        self.descriptor = descriptor
        self.menu_items = {}
        self.menu_book = defaultdict(list)
        self.children = []  # List of WebNode objects (children of this node)

    def add_child(self, child_node):
        """Add a child node to the current node."""
        self.children.append(child_node)

    def __repr__(self):
        return f"WebNode(url={self.url}, children={len(self.children)})"

    def is_valid_url(self):
        """Validate the URL structure."""
        parsed = urlparse(self.url)
        return bool(parsed.scheme and parsed.netloc)

    def get_domain(self):
        """Return the domain of the URL."""
        return urlparse(self.url).netloc

    def visualize(self, parent_tree=None):
        """Recursively visualize the web structure using the rich library."""
        if not parent_tree:
            tree = Tree(f"[link={self.url}]{self.url}[/link] (root)")
        else:
            tree = parent_tree.add(f"[link={self.url}]{self.descriptor or self.url}[/link]")

        for child in self.children:
            child.visualize(tree)

        return tree if parent_tree is None else parent_tree
