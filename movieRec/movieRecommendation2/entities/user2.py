"""User Functions""" #Version 2 of User functions
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, field_validator
from movieRec.config import load_config
import psycopg2

class MoviePreferences(BaseModel):
    """Represents a user's movie preferences."""
    movie_interests_titles: List[str] = [] # List of movie titles the user has shown interest in
    liked_genres: List[str] = []
    model_config = ConfigDict(from_attributes=True)
    
    # validator to catch incoming data and convert it to lowercase
    @field_validator("movie_interests_titles", "liked_genres", mode="before")
    @classmethod
    def normalize_preferences(cls, v: List[str]) -> List[str]:
        if isinstance(v, list):
            # Converts "Sci-Fi", "SCI-FI", or "sci-fi" to "sci-fi"
            # .strip() also removes any accidental spaces like "sci-fi "
            return [str(pref).lower().strip() for pref in v]
        return v
    
    #convert Movie Preferences object to JSON string
    def to_json(self) -> str:
        """Convert the MoviePreferences object to JSON string.
        Returns:
            a JSON string representing the MoviePreferences object."""
        return self.model_dump_json(indent=4)

class User(BaseModel):
    """Represents a user."""
    user_id: Optional[int] = None
    user_name: str
    preferences: MoviePreferences 
    model_config = ConfigDict(from_attributes=True)

    def to_json(self) -> str:
        """Convert the User object to JSON string.
        Returns:
            a JSON string representing the User object."""
        return self.model_dump_json(indent=4)

# create connection
def create_connection():
    config = load_config()
    return psycopg2.connect(**config)

# normal python functions to interact with database and retrieve user info, not part of the User class
class UserFunctions:
    def __init__(self):
        self.connection = create_connection()

    def _ensure_connection(self):
        """Reconnects if connection is broken"""
        if self.connection.closed:
            print("Connection was closed. Reconnecting...")
            self.connection = create_connection()

    def close_connection(self):
        """Closes the database connection if open."""
        if self.connection and not self.connection.closed:
            self.connection.close()
            print("Database connection closed.")

    # called by get_or_create_user(), tool called in sayHello()
    def get_user_by_name(self, user_name: str) -> Optional[User]:
        """Retrieves a user by name. Used when user returns to chat and provides their name."""
        self._ensure_connection()
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT user_id, user_name, preferences FROM user_data WHERE user_name = %s",
                (user_name,)
        )
            row = cursor.fetchone()
            if row:
                return User(
                    user_id=row[0],
                    user_name=row[1],
                    preferences=MoviePreferences.model_validate(row[2])
                )
            return None

    # MAIN ENTRY POINT FOR AGENT, not anymore
    def get_or_create_user(self, user_name: str) -> tuple[User, bool]:
        """Gets existing user or creates a new user. This is the main entry point of the agent.
        Args:
            user_name: name of user to get or create.
        Returns:
            A tuple of (User, is_new_user); agent uses is_new_user to decide greeting."""
        existing_user = self.get_user_by_name(user_name)
        if existing_user:
            return existing_user, False
        else:
            new_user = self.create_new_user(user_name)
            return new_user, True

    # called by get_or_create_user() if user doesn't exist, tool called in sayHello()
    def create_new_user(self, user_name: str) -> User:
        """Creates a new user in the database
        Args:
            user_name: The name of the new user.
        Returns:
            The User object for the newly created user."""
        self._ensure_connection()
        with self.connection.cursor() as cursor:
            empty_preferences = MoviePreferences()
            if user_name is not None:
                cursor.execute(
            "INSERT INTO user_data(user_name, preferences) VALUES (%s, %s) RETURNING user_id",
            (user_name, empty_preferences.to_json())  
        )
            else:
                return "Error: user_name cannot be None. Failed to create user."
            user_id = cursor.fetchone()[0]
            self.connection.commit()
            print(f"New user created with ID: {user_id}")
        return User(user_id=user_id, user_name=user_name, preferences=empty_preferences)

    #tool called in sayHello()
    def get_user(self, current_user_id: int) -> Optional[User]:
        """Retrieves a user by ID.
        Args:
            current_user_id: The ID of the user to retrieve.
        Returns:
            The User object if found, None otherwise."""
        self._ensure_connection()
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT user_id, user_name, preferences FROM user_data WHERE user_id = %s", (current_user_id,))
            row = cursor.fetchone()
            if row:
                user = User(
                    user_id=row[0],
                    user_name=row[1],
                    preferences=MoviePreferences.model_validate(row[2])
                )
                print(f"User found: {user.user_name}, preferences: {user.preferences}")
                return user
            else:
                print(f"No user found with ID: {current_user_id}")
                return None

    def update_user_preferences(self, user_id: int, new_preferences: MoviePreferences) -> Optional[User]:
        """Updates a user's preferences.
        Args:
            user_id: the id of the user to update.
            new_preferences: the new MoviePreferences to set for the user.
        returns:
            The updated User object if the update was successful, None otherwise."""
        self._ensure_connection()
        existing_user = self.get_user(user_id) #displays the existing preferences in the console before updating, for debugging purposes
        if not existing_user:
            print(f"Cannot update preferences. No user found with ID: {user_id}")
            return None

        existing_preferences = existing_user.preferences
        # 1. Lowercase incoming new preferences safely
        new_titles = [str(t).lower().strip() for t in new_preferences.movie_interests_titles if t]
        new_genres = [str(g).lower().strip() for g in new_preferences.liked_genres if g]
        
        # 2. Lowercase existing database preferences just in case there's legacy dirty data
        existing_titles = [str(t).lower().strip() for t in existing_preferences.movie_interests_titles if t]
        existing_genres = [str(g).lower().strip() for g in existing_preferences.liked_genres if g]

        # 3. Merge and remove duplicates using set()
        updated_preferences = MoviePreferences(
            movie_interests_titles=list(set(new_titles + existing_titles)),
            liked_genres=list(set(new_genres + existing_genres))
        )

        with self.connection.cursor() as cursor:
            cursor.execute(
                "UPDATE user_data SET preferences = %s WHERE user_id = %s",
                (updated_preferences.to_json(), user_id)
            )
            self.connection.commit()
        existing_user = self.get_user(user_id) #displays the updated preferences in the console after updating, for debugging purposes
        return User(user_id=user_id, user_name=existing_user.user_name, preferences=updated_preferences)

    def remove_preferences(self, user_id: int, preferences_to_remove: MoviePreferences) -> Optional[User]:
        """Removes specified preferences from a user's existing preferences.'
        Args:
            user_id: The ID of the user to remove preferences from.
            preferences_to_remove: the MoviePreferences to remove from the user's existing preferences.
        Returns:
            updated User object if successful, None otherwise."""

        self._ensure_connection()
        existing_user = self.get_user(user_id) #displays the existing preferences in the console before removing preferences, for debugging purposes
        if not existing_user:
            print(f"Cannot remove preferences. No user found with ID: {user_id}")
            return None
        existing_preferences = existing_user.preferences
        # 1. Normalize target lists for case-insensitive matching
        remove_titles = {str(t).lower().strip() for t in preferences_to_remove.movie_interests_titles if t}
        remove_genres = {str(g).lower().strip() for g in preferences_to_remove.liked_genres if g}
        
        # 2. Filter out elements using a lowercased check
        updated_preferences = MoviePreferences(
            movie_interests_titles=[
                title for title in existing_preferences.movie_interests_titles 
                if str(title).lower().strip() not in remove_titles
            ],
            liked_genres=[
                genre for genre in existing_preferences.liked_genres 
                if str(genre).lower().strip() not in remove_genres
            ]
        )   
        with self.connection.cursor() as cursor:
            cursor.execute(
                "UPDATE user_data SET preferences = %s WHERE user_id = %s",
                (updated_preferences.to_json(), user_id)
            )
            self.connection.commit()
        existing_user = self.get_user(user_id) #displays the updated preferences in the console after removing preferences, for debugging purposes
        return User(user_id=user_id, user_name=existing_user.user_name, preferences=updated_preferences)

    def remove_users(self, user_ids: List[int]) -> None:
        """Removes users from the database. This is a utility function for testing purposes.
        Args:
            user_ids: A list of user IDs to remove from the database."""
        self._ensure_connection()
        with self.connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM user_data WHERE user_id = ANY(%s)",
                (user_ids,)
            )
            self.connection.commit()
            print(f"Removed users with IDs: {user_ids}")

if __name__ == "__main__":
    # Example usage
    uf = UserFunctions() #creates new connection to database
    try:
        user, is_new_user = uf.get_or_create_user("Alex")
        print(user.user_name)
        # print(user.preferences.movie_interests_titles) #['La La land', 'The Matrix', 'Inception', 'The Devil wears Prada']
        # print(f"Is new user: {is_new_user}")

        # uf.get_user(2)

        # uf.remove_preferences(user.user_id, MoviePreferences(liked_genres=["Slice of Life"]))

        # uf.remove_users([1,2,3])
        # uf.get_user(1)
        # uf.get_user(2)
        # uf.get_user(3)

    finally:
        uf.close_connection()

# agent-facing tools: get_user_by_name, create_new_user, get_user
# did not use: get_or_create_user(), update_user_preferences(), remove_preferences()
# internal helper functions: get_user_by_name(), create_new_user(), ensure_connection(), create_connection()
# utility/testing only: remove_users()
