import weakref
import pymysql
from hashlib import md5

from _utils._util import util_logger

class CustomDBManager:
    def __init__(self, system, uid, pwd, library, table_name, logg=None) -> None:
        self.logging = logg if logg else util_logger

        # Register the object to execute "_on_delete" upon garbage collection
        self._finalizer = weakref.finalize(self, self._on_delete)

        self.logging.info("Creating connection")

        # Establish the database connection
        self.conn = pymysql.connect(
            host=system,
            user=uid,
            password=pwd,
            database=library
        )

        self.logging.info("Creating cursor")
        self.cu = self.conn.cursor()
        self.conn.autocommit = True
        self.cu.fast_executemany = True

        self.logging.info(f"Current table name: {table_name}")
        self.table_name = table_name
        self.library = library

    def push_blob_to_db(self, table_name, blob, hash_key):
        """
        Inserts a blob into the specified table with the associated hash_key.

        Args:
            table_name (str): The name of the table to insert the blob into.
            blob (bytes): The blob data to insert.
            hash_key (str): The hash key associated with the blob.
        """
        if self.table_exists(table_name):
            self.set_table(table_name)
        else:
            self.logging.info('SQL TABLE NOT FOUND')
            self.logging.info('Constructing SQL query to generate new table')
            sql_query = self.generate_table_from_name(table_name)
            self.logging.info('Creating new table')
            self.wrapped_execute(sql_query)
    
        # Start of Selection
        query = f"""
            INSERT INTO {self.library}.{self.table_name} (HASH_KEY, BLOBBED)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE BLOBBED = VALUES(BLOBBED)
        """

        hash_key = md5(hash_key.encode('utf-8')).hexdigest()

        self.cu.execute(query, (hash_key, blob))
        if self.cu.rowcount == 2:
            self.logging.warning(f"Collision detected for HASH_KEY: {hash_key}. Existing data overwritten.")
        self.commit()

    def pull_blob_from_db(self, hash_key):
        """
        Retrieves the blob data associated with the given hash_key from the database.

        Args:
            hash_key (str): The hash key identifying the blob.

        Returns:
            bytes or None: The retrieved blob data, or None if not found.
        """

        if not self.table_exists(self.table_name):
            self.logging.info(f"Table '{self.table_name}' does not exist in the '{self.library}' schema.")
            return None

        hash_key = md5(hash_key.encode('utf-8'), usedforsecurity=False).hexdigest()

        query = f"SELECT BLOBBED FROM {self.library}.{self.table_name} WHERE HASH_KEY = %s"
        self.cu.execute(query, (hash_key,))
        result = self.cu.fetchone()
        if result:
            return result[0]
        else:
            self.logging.info(f"No data found for HASH_KEY: {hash_key}")
            return None

    def table_exists(self, table_name):
        """
        Checks if a table exists within the specified library/schema.

        Args:
            table_name (str): The name of the table to check.

        Returns:
            bool: True if the table exists, False otherwise.
        """
        query = f"SELECT table_name FROM information_schema.tables WHERE table_name = '{table_name}' AND table_schema = '{self.library}'"
        self.cu.execute(query)
        table_exists = self.cu.fetchone()
        if table_exists:
            self.logging.info(f"The table '{table_name}' exists in the '{self.library}' schema.")
            return True
        else:
            self.logging.info(f"The table '{table_name}' does not exist in the '{self.library}' schema.")
            return False

    def generate_table_from_name(self, table_name):
        """
        Generates a SQL query to create a new table with the specified name.

        Args:
            table_name (str): The name of the table to create.

        Returns:
            str: The SQL CREATE TABLE statement.
        """
        query = f"CREATE TABLE {self.library}.{table_name} ("
        query += '''
            HASH_KEY VARCHAR(512) NOT NULL UNIQUE PRIMARY KEY,
            ROW_CHANGE_TIMESTAMP TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL,
            BLOBBED LONGBLOB
        )'''
        return query

    def wrapped_execute(self, query, data=None):
        """
        Executes a SQL query with optional data.

        Args:
            query (str): The SQL query to execute.
            data (tuple or list of tuples, optional): The data to pass with the query.
            blob (bool, optional): Indicates if the data includes a blob.

        Returns:
            list or None: The fetched data if applicable, else None.
        """
        self.logging.info('Executing query')
        self.logging.info(f'Query: {query}')
        if data:

            self.cu.executemany(query, data)
        else:
            self.cu.execute(query)
        
        self.commit()
        self.logging.info('Query executed successfully')
        
        if self.cu.description:
            return self.fetch_all()
        return None

    def fetch_all(self):
        """
        Fetches all rows from the last executed query.

        Returns:
            list: A list of fetched rows.
        """
        results = []
        for row in self.cu.fetchall():
            results.append(row)
        return results

    def set_table(self, new_table):
        """
        Sets the current table to a new table and updates column information.

        Args:
            new_table (str): The name of the new table to set.
        """
        if self.table_name != new_table:
            self.table_name = new_table
            self.get_columns()

    def commit(self):
        """
        Commits the current transaction.
        """
        self.conn.commit()

    def close(self):
        """
        Closes the database connection.
        """
        self.logging.info('Closing connection')
        self.conn.close()

    def _on_delete(self):
        """
        Finalizer to ensure the connection is closed when the object is garbage collected.
        """
        self.logging.info('Finalizer triggered: Closing connection')
        self.close()
