import mysql.connector
from mysql.connector import errorcode

class MySQLManager:
    """
    A class to manage MySQL database connections and operations.
    """
    def __init__(self, host, user, password, database=None):
        """
        Initializes the MySQLManager.

        Args:
            host (str): The database host.
            user (str): The database user.
            password (str): The user's password.
            database (str, optional): The database name. Defaults to None.
        """
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.connection = None
        self.cursor = None

    def connect(self):
        """
        Establishes a connection to the MySQL server and optionally to a database.
        """
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            self.cursor = self.connection.cursor()
            return True, "Connection successful"
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                return False, "Something is wrong with your user name or password"
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                return False, "Database does not exist"
            else:
                return False, str(err)

    def close(self):
        """
        Closes the database connection.
        """
        if self.connection and self.connection.is_connected():
            self.cursor.close()
            self.connection.close()

    def execute_query(self, query, params=None):
        """
        Executes a SQL query.

        Args:
            query (str): The SQL query to execute.
            params (tuple, optional): The parameters to pass to the query. Defaults to None.

        Returns:
            list: The result of the query, if any.
        """
        try:
            self.cursor.execute(query, params or ())
            if query.strip().upper().startswith("SELECT"):
                return self.cursor.fetchall()
            else:
                self.connection.commit()
                return None
        except mysql.connector.Error as err:
            return f"Error: {err}"

    def create_database_if_not_exists(self):
        """
        Creates the database if it does not already exist.
        """
        try:
            # Connect to MySQL server without specifying a database
            temp_connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password
            )
            temp_cursor = temp_connection.cursor()
            temp_cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{self.database}`")
            temp_cursor.close()
            temp_connection.close()
            return True, f"Database '{self.database}' created or already exists."
        except mysql.connector.Error as err:
            return False, f"Failed to create database: {err}"

    def get_table_columns(self, table_name):
        """
        Retrieves the column names of a specified table.

        Args:
            table_name (str): The name of the table.

        Returns:
            list: A list of column names, or an error string.
        """
        if not self.connection or not self.connection.is_connected():
            return "Error: Not connected to a database."
        try:
            # Use a fresh cursor for this operation to avoid conflicts
            cursor = self.connection.cursor()
            cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
            columns = [row[0] for row in cursor.fetchall()]
            cursor.close()
            return columns
        except mysql.connector.Error as err:
            return f"Error: {err}"

    def add_column_to_table(self, table_name, column_name, column_type="VARCHAR(255)"):
        """
        Adds a new column to a specified table if it doesn't exist.

        Args:
            table_name (str): The name of the table.
            column_name (str): The name of the new column.
            column_type (str): The data type of the new column.
        """
        if not self.connection or not self.connection.is_connected():
            return False, "Error: Not connected to a database."
        try:
            # Check if column exists
            columns = self.get_table_columns(table_name)
            if isinstance(columns, str) and columns.startswith("Error:"):
                # Table might not exist, let's try to create it.
                # A simple CREATE TABLE for now. A more robust solution might be needed.
                self.execute_query(f"CREATE TABLE IF NOT EXISTS `{table_name}` (id INT AUTO_INCREMENT PRIMARY KEY)")

            # Re-check columns after potential table creation
            columns = self.get_table_columns(table_name)
            if column_name not in columns:
                cursor = self.connection.cursor()
                cursor.execute(f"ALTER TABLE `{table_name}` ADD COLUMN `{column_name}` {column_type}")
                cursor.close()
                self.connection.commit()
                return True, f"Column '{column_name}' added to table '{table_name}'."
            else:
                return True, f"Column '{column_name}' already exists in table '{table_name}'."
        except mysql.connector.Error as err:
            return False, f"Error adding column: {err}"
