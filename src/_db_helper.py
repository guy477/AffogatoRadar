from backend import local_storage

from bs4 import BeautifulSoup, Comment


def __DELETER_(db_name, base_url_or_like):
    # def remove_entries(local_storage):
    storage = local_storage.LocalStorage(storage_dir="../data", db_name=db_name)
    
    try:
        # Fetch all hash_key and idx pairs
        storage.cursor.execute("SELECT hash_key, idx FROM place_id_map")
        all_records = storage.cursor.fetchall()
        
        # Iterate over each record and remove the ones containing 'whataburger'
        for hash_key, idx in all_records:
            if base_url_or_like in hash_key.lower():  # Case-insensitive check
                print(f"Removing entry for: {hash_key}")
                
                # Delete from place_id_map
                storage.cursor.execute("DELETE FROM place_id_map WHERE hash_key = ?", (hash_key,))
                
                # Delete corresponding data in data_dump
                storage.cursor.execute("DELETE FROM data_dump WHERE id = ?", (idx,))
                
                # Commit changes
                storage.conn.commit()
    except Exception as e:
        print(f"Error: {e}")

    storage.close()
    print("Finished removing entries.")


def __DUMPER_(db_name):
    # def remove_entries(local_storage):
    storage = local_storage.LocalStorage(storage_dir="../data", db_name=db_name)
    
    try:
        # dump all contents of storage to txt file:
        storage.cursor.execute("SELECT * FROM data_dump")
        all_keys = storage.cursor.fetchall()
        
        
        if all_keys:
            with open(f"../data/_db_dumps/{db_name}.txt", "w") as f:
                for record in all_keys:
                    f.write(f"{record}\n\n")

    except Exception as e:
        print(f"Error: {e}")

    storage.close()
    print("Finished dumping entries.")


def filter_html_for_menu():
        storage = local_storage.LocalStorage(storage_dir="../data", db_name='url_to_html.db')
        
        url = "https://www.mcdonalds.com/us/en-us/full-menu/mcnuggets-meals.html"
        # select nth element from storage in data_dump
        storage.cursor.execute(f"SELECT data FROM data_dump WHERE hash_key = \"{url}\"")
        html = storage.cursor.fetchone()[0]
        
        storage.close()

        """Aggressively remove HTML elements that are unlikely to contain menu items but preserve potential menu-related tags and structure."""
        soup = BeautifulSoup(html, 'html.parser')

        # Define tags that you want to remove (e.g., script, style)
        remove_tags = ['script', 'style']
        
        # Remove unwanted tags from the document
        for tag in soup(remove_tags):
            tag.decompose()

        # Remove all comments from the document
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()  # Remove comment


        # Iterate over all elements and remove attributes while preserving tags and text
        for element in soup.find_all(True):  # True finds all tags
            element.attrs = {}  # Remove all attributes but keep the tags and their text content

        # Return the modified HTML structure as a string
        return str(soup.body)

if __name__ == "__main__":
    __DUMPER_('source_dest.db')
    __DUMPER_('llm_relevance.db')
    __DUMPER_('url_to_html.db')
    __DUMPER_('url_to_menu.db')
    __DUMPER_('embedding_relevance.db')
    # print(filter_html_for_menu())