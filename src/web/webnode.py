from _utils._util import *

from rich.tree import Tree

class WebNode:
    def __init__(self, url, descriptor=None):
        util_logger.info(f"Initializing WebNode with URL: {url} and Descriptor: {descriptor}")
        self.url = url
        self.descriptor = descriptor
        self.scraped_items = {}
        self.menu_book = defaultdict(set)
        self.children = []  # List of WebNode objects (children of this node)
        util_logger.debug(f"WebNode initialized. Current children count: {len(self.children)}")

    def add_child(self, child_node):
        """Add a child node to the current node."""
        if not isinstance(child_node, WebNode):
            util_logger.error(f"Attempted to add a non-WebNode child: {child_node}")
            raise TypeError("child_node must be an instance of WebNode")
        
        self.children.append(child_node)
        util_logger.debug(f"Added child WebNode. URL: {child_node.url}. Total children now: {len(self.children)}")

    def __repr__(self):
        return f"WebNode(url={self.url}, children={len(self.children)})"

    def is_valid_url(self):
        """Validate the URL structure."""
        util_logger.debug(f"Validating URL: {self.url}")
        parsed = urlparse(self.url)
        is_valid = bool(parsed.scheme and parsed.netloc)
        if not is_valid:
            util_logger.warning(f"Invalid URL detected: {self.url}")
        else:
            util_logger.debug(f"URL is valid: {self.url}")
        return is_valid

    def get_domain(self):
        """Return the domain of the URL."""
        domain = urlparse(self.url).netloc
        util_logger.debug(f"Extracted domain: {domain} from URL: {self.url}")
        return domain

    def visualize(self, parent_tree=None):
        """Recursively visualize the web structure using the rich library."""
        if parent_tree is None:
            util_logger.info(f"Starting visualization for root URL: {self.url}")
            tree = Tree(f"[link={self.url}]{self.url}[/link] (root)")
        else:
            descriptor = self.descriptor or self.url
            util_logger.debug(f"Adding child to visualization: {descriptor}")
            tree = parent_tree.add(f"[link={self.url}]{descriptor}[/link]")

        for child in self.children:
            util_logger.debug(f"Visualizing child node: {child.url}")
            child.visualize(tree)

        if parent_tree is None:
            util_logger.info(f"Visualization completed for root URL: {self.url}")
        return tree if parent_tree is None else parent_tree

    def to_dict(self):
        """Convert the WebNode object into a dictionary for serialization."""
        util_logger.debug(f"Serializing WebNode with URL: {self.url}")
        serialized = {
            'url': self.url,
            'descriptor': self.descriptor,
            'scraped_items': list(set(self.scraped_items)),
            'menu_book': {k: list(set(v)) for k, v in dict(self.menu_book).items()},  # convert set to list for json serialization
            'children': [child.to_dict() for child in self.children]  # Recursively convert children
        }
        util_logger.debug(f"Serialized data for URL: {self.url}: {serialized.keys()}")
        return serialized

    @staticmethod
    def from_dict(data):
        """Load a WebNode object from a dictionary."""
        url = data.get('url')
        descriptor = data.get('descriptor')
        util_logger.debug(f"Deserializing WebNode from data with URL: {url}")
        
        if not url:
            util_logger.error("Missing 'url' in data during deserialization.")
            raise ValueError("URL is required to deserialize WebNode.")
        
        node = WebNode(url=url, descriptor=descriptor)
        node.scraped_items = set(data.get('scraped_items', []))
        node.menu_book = defaultdict(set, {k: set(v) for k, v in data.get('menu_book', {}).items()})
        children_data = data.get('children', [])
        util_logger.debug(f"Deserializing {len(children_data)} children for WebNode with URL: {url}")
        node.children = [WebNode.from_dict(child_data) for child_data in children_data]
        util_logger.debug(f"Deserialization complete for WebNode with URL: {url}")
        return node
