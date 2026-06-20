"""User Functions"""  # Version 2 of User functions - Fixed for Neon Cloud URL compatibility

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, field_validator
from movieRec.config import load_config
import psycopg2
import json


class MoviePreferences(BaseModel):
    """Represents a user's movie preferences."""

    movie_interests_titles: List[str] = ([])  # List of movie titles the user has shown interest in
    liked_genres: List[str] = []
    model_config = ConfigDict(from_attributes=True)

    # validator to catch incoming data and convert it to lowercase
    @field_validator("movie_interests_titles", "liked_genres", mode="before")
    @classmethod
    def normalize_preferences(cls, v: List[str]) -> List[str]:
        if isinstance(v, list):
            return [str(pref).lower().strip() for pref in v]
        return v

    # convert Movie Preferences object to JSON string
    def to_json(self) -> str:
        """Convert the MoviePreferences object to JSON string."""
        return self.model_dump_json(indent=4)


class User(BaseModel):
    """Represents a user."""

    user_id: Optional[int] = None
    user_name: str
    preferences: MoviePreferences
    model_config = ConfigDict(from_attributes=True)

    def to_json(self) -> str:
        """Convert the User object to JSON string."""
        return self.model_dump_json(indent=4)


# FIXED: Safe, URL-compatible connection function matching connect.py logic
def get_safe_connection():
    config = load_config()
    if isinstance(config, str):
        return psycopg2.connect(config)
    else:
        return psycopg2.connect(**config)


class UserFunctions:
    def __init__(self):
        # We no longer keep a single self.connection running forever!
        pass

    def close_connection(self):
        """Maintained for backwards compatibility with legacy call blocks."""
        pass

    def get_user_by_name(self, user_name: str) -> Optional[User]:
        """Retrieves a user by name."""
        conn = get_safe_connection()
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT user_id, user_name, preferences FROM user_data WHERE user_name = %s",
                        (user_name,),
                    )
                    row = cursor.fetchone()
                    if row:
                        # Handle raw dict vs JSON string structures gracefully
                        pref_data = (
                            row[2] if isinstance(row[2], dict) else json.loads(row[2])
                        )
                        return User(
                            user_id=row[0],
                            user_name=row[1],
                            preferences=MoviePreferences.model_validate(pref_data),
                        )
            return None
        finally:
            conn.close()

    def create_new_user(self, user_name: str) -> User:
        """Creates a new user in the database."""
        if user_name is None:
            raise ValueError("Error: user_name cannot be None. Failed to create user.")

        conn = get_safe_connection()
        try:
            with conn:
                with conn.cursor() as cursor:
                    empty_preferences = MoviePreferences()
                    cursor.execute(
                        "INSERT INTO user_data(user_name, preferences) VALUES (%s, %s) RETURNING user_id",
                        (user_name, empty_preferences.to_json()),
                    )
                    user_id = cursor.fetchone()[0]
                    conn.commit()
            print(f"New user created with ID: {user_id}")
            return User(
                user_id=user_id, user_name=user_name, preferences=empty_preferences
            )
        finally:
            conn.close()

    def get_user(self, current_user_id: int) -> Optional[User]:
        """Retrieves a user by ID."""
        conn = get_safe_connection()
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT user_id, user_name, preferences FROM user_data WHERE user_id = %s",
                        (current_user_id,),
                    )
                    row = cursor.fetchone()
                    if row:
                        pref_data = (
                            row[2] if isinstance(row[2], dict) else json.loads(row[2])
                        )
                        user = User(
                            user_id=row[0],
                            user_name=row[1],
                            preferences=MoviePreferences.model_validate(pref_data),
                        )
                        print(
                            f"User found: {user.user_name}, preferences: {user.preferences}"
                        )
                        return user
                    else:
                        print(f"No user found with ID: {current_user_id}")
                        return None
        finally:
            conn.close()

    def update_user_preferences(
        self, user_id: int, new_preferences: MoviePreferences
    ) -> Optional[User]:
        """Updates a user's preferences by merging incoming arrays with existing ones."""
        existing_user = self.get_user(user_id)
        if not existing_user:
            print(f"Cannot update preferences. No user found with ID: {user_id}")
            return None

        existing_preferences = existing_user.preferences
        new_titles = [
            str(t).lower().strip() for t in new_preferences.movie_interests_titles if t
        ]
        new_genres = [str(g).lower().strip() for g in new_preferences.liked_genres if g]

        existing_titles = [
            str(t).lower().strip()
            for t in existing_preferences.movie_interests_titles
            if t
        ]
        existing_genres = [
            str(g).lower().strip() for g in existing_preferences.liked_genres if g
        ]

        updated_preferences = MoviePreferences(
            movie_interests_titles=list(set(new_titles + existing_titles)),
            liked_genres=list(set(new_genres + existing_genres)),
        )

        conn = get_safe_connection()
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE user_data SET preferences = %s WHERE user_id = %s",
                        (updated_preferences.to_json(), user_id),
                    )
                    conn.commit()
            return User(
                user_id=user_id,
                user_name=existing_user.user_name,
                preferences=updated_preferences,
            )
        finally:
            conn.close()

    def remove_preferences(
        self, user_id: int, preferences_to_remove: MoviePreferences
    ) -> Optional[User]:
        """Removes specified preferences from a user's existing preferences."""
        existing_user = self.get_user(user_id)
        if not existing_user:
            print(f"Cannot remove preferences. No user found with ID: {user_id}")
            return None

        existing_preferences = existing_user.preferences
        remove_titles = {
            str(t).lower().strip()
            for t in preferences_to_remove.movie_interests_titles
            if t
        }
        remove_genres = {
            str(g).lower().strip() for g in preferences_to_remove.liked_genres if g
        }

        updated_preferences = MoviePreferences(
            movie_interests_titles=[
                title
                for title in existing_preferences.movie_interests_titles
                if str(title).lower().strip() not in remove_titles
            ],
            liked_genres=[
                genre
                for genre in existing_preferences.liked_genres
                if str(genre).lower().strip() not in remove_genres
            ],
        )

        conn = get_safe_connection()
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE user_data SET preferences = %s WHERE user_id = %s",
                        (updated_preferences.to_json(), user_id),
                    )
                    conn.commit()
            return User(
                user_id=user_id,
                user_name=existing_user.user_name,
                preferences=updated_preferences,
            )
        finally:
            conn.close()

    def remove_users(self, user_ids: List[int]) -> None:
        """Removes users from the database."""
        conn = get_safe_connection()
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM user_data WHERE user_id = ANY(%s)", (user_ids,)
                    )
                    conn.commit()
            print(f"Removed users with IDs: {user_ids}")
        finally:
            conn.close()


if __name__ == "__main__":
    # Test suite
    uf = UserFunctions()
    user = uf.get_user_by_name("Alex")
    if user:
        print(f"Test Successful. Found User: {user.user_name}")
    else:
        print("Test complete. User functions are operational.")
